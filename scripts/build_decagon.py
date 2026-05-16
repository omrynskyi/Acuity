"""Build data/decagon.sqlite from SNAP's bio-decagon-combo.csv.

Replaces scripts/build_twosides.py. The output is a SQLite with two tables:

    pair_effect (cid_a, cid_b, umls_cui, effect_name)
        ~4.65M rows, observed polypharmacy side effects from Zitnik et al.,
        Decagon (Bioinformatics 2018), https://snap.stanford.edu/decagon/.

    drug_map (name_lower, cid)
        Name -> Decagon CID lookup. Built from PubChem batch synonyms +
        Title, filtered to drug-name-shaped strings, with a small curated
        override for orphaned legacy CIDs (e.g. warfarin CID 6691 has lost
        its PubChem synonyms but is still in Decagon under that CID).

Run:
    python scripts/build_decagon.py                  # CSV load only (~60 s)
    python scripts/build_decagon.py --build-drug-map # PubChem bridge (~30 s)
    python scripts/build_decagon.py --all            # both

Idempotent: reruns recreate pair_effect from CSV; drug_map is rebuilt
in-place when --build-drug-map is passed.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
import tarfile
import time
from pathlib import Path
from typing import Iterable

import httpx

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / "bio-decagon-combo.csv"
TARBALL = Path("/home/ubuntu/bio-decagon-combo.tar.gz")
DB_PATH = DATA_DIR / "decagon.sqlite"

EXPECTED_HEADER = ["STITCH 1", "STITCH 2", "Polypharmacy Side Effect", "Side Effect Name"]

PUBCHEM_BATCH = 100
PUBCHEM_RATE_PER_SEC = 4.0  # PubChem documents 5/s; leave headroom.

# Decagon CIDs that PubChem has since orphaned (Title/synonyms empty) but
# which still resolve clinically. Add new entries as the build report surfaces
# more orphans; the script prints them at the end.
CURATED_LEGACY_NAMES: dict[str, list[str]] = {
    "CID000006691": ["warfarin", "coumadin", "jantoven"],
}

SCHEMA = """
DROP TABLE IF EXISTS pair_effect;
CREATE TABLE pair_effect (
    cid_a       TEXT NOT NULL,
    cid_b       TEXT NOT NULL,
    umls_cui    TEXT NOT NULL,
    effect_name TEXT NOT NULL,
    PRIMARY KEY (cid_a, cid_b, umls_cui)
);
CREATE INDEX idx_pair ON pair_effect (cid_a, cid_b);
"""

DRUG_MAP_SCHEMA = """
DROP TABLE IF EXISTS drug_map;
CREATE TABLE drug_map (
    name_lower TEXT NOT NULL,
    cid        TEXT NOT NULL,
    PRIMARY KEY (name_lower, cid)
);
CREATE INDEX idx_drug_map_cid  ON drug_map (cid);
CREATE INDEX idx_drug_map_name ON drug_map (name_lower);
"""


# --------------------------------------------------------------------------- #
# CSV load
# --------------------------------------------------------------------------- #

def ensure_csv_extracted() -> None:
    if CSV_PATH.exists():
        return
    if not TARBALL.exists():
        sys.exit(f"missing tarball: {TARBALL}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with tarfile.open(TARBALL, "r:gz") as tf:
        tf.extractall(DATA_DIR)
    if not CSV_PATH.exists():
        sys.exit(f"extracted but {CSV_PATH} missing — tarball layout changed?")


def load_pair_effect(con: sqlite3.Connection, batch_size: int = 10_000) -> int:
    con.executescript(SCHEMA)
    with CSV_PATH.open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        if header != EXPECTED_HEADER:
            sys.exit(f"CSV header changed: {header!r} != {EXPECTED_HEADER!r}")
        cur = con.cursor()
        cur.execute("BEGIN")
        buf: list[tuple[str, str, str, str]] = []
        n = 0
        for row in reader:
            if len(row) != 4:
                continue
            cid_a, cid_b, cui, name = row
            buf.append((cid_a, cid_b, cui, name))
            if len(buf) >= batch_size:
                cur.executemany(
                    "INSERT OR IGNORE INTO pair_effect "
                    "(cid_a, cid_b, umls_cui, effect_name) VALUES (?,?,?,?)",
                    buf,
                )
                n += len(buf)
                buf.clear()
        if buf:
            cur.executemany(
                "INSERT OR IGNORE INTO pair_effect "
                "(cid_a, cid_b, umls_cui, effect_name) VALUES (?,?,?,?)",
                buf,
            )
            n += len(buf)
        con.commit()
    return n


# --------------------------------------------------------------------------- #
# Drug-map build
# --------------------------------------------------------------------------- #

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9\-' ]{2,59}$")
_BAD_SUBSTR = ("(", ")", "[", "]", "{", "}", ",", ";", "/")


def looks_like_drug_name(s: str) -> bool:
    if not s or any(c in s for c in _BAD_SUBSTR):
        return False
    if not _NAME_RE.match(s):
        return False
    # Skip CAS-style "50-78-2" — but our regex already excludes leading digit.
    # Skip pure all-digit-after-letter chains like 'X1234567'.
    if sum(c.isdigit() for c in s) > 3:
        return False
    return True


def decagon_cids(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT cid_a AS c FROM pair_effect "
        "UNION SELECT cid_b FROM pair_effect ORDER BY c"
    ).fetchall()
    return [r[0] for r in rows]


def to_int_cid(padded: str) -> int:
    # "CID000006691" -> 6691
    return int(padded[3:])


def from_int_cid(n: int) -> str:
    return f"CID{n:09d}"


def fetch_pubchem_batch(client: httpx.Client, int_cids: list[int]) -> dict[int, list[str]]:
    """Returns {cid_int: [name1, name2, ...]} drawn from Title + Synonyms.

    Skips empties; caller decides whether they're orphans.
    """
    out: dict[int, list[str]] = {c: [] for c in int_cids}
    joined = ",".join(str(c) for c in int_cids)

    # Title first — single canonical name per CID. Some legacy CIDs have it.
    try:
        r = client.get(
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{joined}/property/Title/JSON",
            timeout=20,
        )
        if r.status_code == 200:
            for entry in r.json().get("PropertyTable", {}).get("Properties", []):
                cid = entry.get("CID")
                title = entry.get("Title")
                if cid and title and not title.startswith("CID "):
                    out[cid].append(title)
    except httpx.HTTPError:
        pass

    # Then synonyms — adds aliases. PubChem returns up to ~hundreds per CID.
    try:
        r = client.get(
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{joined}/synonyms/JSON",
            timeout=30,
        )
        if r.status_code == 200:
            for entry in r.json().get("InformationList", {}).get("Information", []):
                cid = entry.get("CID")
                if not cid:
                    continue
                for syn in entry.get("Synonym", []) or []:
                    if syn and syn not in out[cid]:
                        out[cid].append(syn)
    except httpx.HTTPError:
        pass

    return out


def build_drug_map(con: sqlite3.Connection) -> tuple[int, list[str]]:
    """Populates drug_map. Returns (rows_inserted, orphan_cids)."""
    con.executescript(DRUG_MAP_SCHEMA)
    cids = decagon_cids(con)
    int_cids = [to_int_cid(c) for c in cids]
    name_to_cid: set[tuple[str, str]] = set()
    orphans: list[str] = []

    with httpx.Client(headers={"User-Agent": "Acuity/decagon-build"}) as client:
        last = 0.0
        for i in range(0, len(int_cids), PUBCHEM_BATCH):
            chunk = int_cids[i : i + PUBCHEM_BATCH]
            # Simple rate limit.
            elapsed = time.monotonic() - last
            min_gap = 1.0 / PUBCHEM_RATE_PER_SEC
            if elapsed < min_gap:
                time.sleep(min_gap - elapsed)
            last = time.monotonic()

            result = fetch_pubchem_batch(client, chunk)
            for cid_int, names in result.items():
                padded = from_int_cid(cid_int)
                kept = [n for n in names if looks_like_drug_name(n)]
                if not kept:
                    orphans.append(padded)
                    continue
                for nm in kept:
                    name_to_cid.add((nm.strip().lower(), padded))

            print(
                f"  batch {i // PUBCHEM_BATCH + 1:>3} / "
                f"{(len(int_cids) + PUBCHEM_BATCH - 1) // PUBCHEM_BATCH}  "
                f"({len(name_to_cid)} names so far, {len(orphans)} orphans)",
                flush=True,
            )

    # Apply curated overrides — these win for orphans, but also augment.
    for padded, names in CURATED_LEGACY_NAMES.items():
        for nm in names:
            name_to_cid.add((nm.strip().lower(), padded))
        if padded in orphans:
            orphans.remove(padded)

    cur = con.cursor()
    cur.executemany(
        "INSERT OR IGNORE INTO drug_map (name_lower, cid) VALUES (?, ?)",
        sorted(name_to_cid),
    )
    con.commit()
    return len(name_to_cid), orphans


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #

def report(con: sqlite3.Connection) -> None:
    n_pairs = con.execute("SELECT COUNT(*) FROM pair_effect").fetchone()[0]
    n_drugs = con.execute(
        "SELECT COUNT(*) FROM (SELECT cid_a AS c FROM pair_effect "
        "UNION SELECT cid_b FROM pair_effect)"
    ).fetchone()[0]
    n_effects = con.execute(
        "SELECT COUNT(DISTINCT umls_cui) FROM pair_effect"
    ).fetchone()[0]
    print(f"pair_effect: {n_pairs:,} rows, {n_drugs} drugs, {n_effects} effect types")

    # Top-10 most common effects (sanity check).
    rows = con.execute(
        "SELECT effect_name, COUNT(*) FROM pair_effect "
        "GROUP BY effect_name ORDER BY COUNT(*) DESC LIMIT 10"
    ).fetchall()
    print("top-10 effects:")
    for name, c in rows:
        print(f"  {c:>7,}  {name}")

    # Drug-map stats.
    n_names = con.execute("SELECT COUNT(*) FROM drug_map").fetchone()[0]
    n_mapped_cids = con.execute("SELECT COUNT(DISTINCT cid) FROM drug_map").fetchone()[0]
    print(f"drug_map: {n_names:,} names spanning {n_mapped_cids} CIDs")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-drug-map", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--skip-csv-load", action="store_true",
                        help="When iterating on the drug-map step, don't reload the CSV.")
    args = parser.parse_args()

    ensure_csv_extracted()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA synchronous = NORMAL")

        if not args.skip_csv_load:
            t = time.monotonic()
            n = load_pair_effect(con)
            print(f"loaded {n:,} pair_effect rows in {time.monotonic() - t:.1f}s")
        else:
            print("skipped CSV load (--skip-csv-load)")

        if args.build_drug_map or args.all:
            t = time.monotonic()
            n_names, orphans = build_drug_map(con)
            print(f"built drug_map ({n_names:,} names) in {time.monotonic() - t:.1f}s")
            if orphans:
                print(f"orphan CIDs (no PubChem names, no curated entry): {len(orphans)}")
                print("  (first 20:)", orphans[:20])

        con.execute("VACUUM")
        con.execute("ANALYZE")
        report(con)
    finally:
        con.close()
    print(f"wrote {DB_PATH}")


if __name__ == "__main__":
    main()
