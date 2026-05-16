"""DEPRECATED — superseded by scripts/build_decagon.py.

This script seeded a small hand-authored TWOSIDES SQLite for development
before we landed the real SNAP Decagon extract. Kept for emergency fallback
only — production builds use `scripts/build_decagon.py --all` and write to
`data/decagon.sqlite`. Do not invoke this in the normal demo pipeline.

# TODO(synthetic-data): every row inserted by this script is hand-authored
# by Person A. The pairs and conditions reflect real clinical pharmacology,
# but the PRR / A / mean_reporting_frequency numbers are illustrative.
# Marker kept so a grep still catches the fallback path.

We attempted to download the canonical TWOSIDES dump (Tatonetti Lab, Nature
Biotech 2018). All public mirrors return 404 and the nsides AWS bucket needs
credentials. Per TASKS.md BE-03's documented fallback ("fall back to mocking
the third source with a small hardcoded lookup table for the demo cases"),
we seed the database with values drawn from published TWOSIDES analyses and
clinical pharmacology references for the regimen we plan to demo. The schema
mirrors the public TWOSIDES tsv exactly, so swapping in the full dataset
later is a single file replacement.

Run: `python scripts/build_twosides.py`
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "twosides.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS twosides (
    drug_1_rxnorm_id        TEXT NOT NULL,
    drug_1_concept_name     TEXT NOT NULL,
    drug_2_rxnorm_id        TEXT NOT NULL,
    drug_2_concept_name     TEXT NOT NULL,
    condition_meddra_id     TEXT,
    condition_concept_name  TEXT NOT NULL,
    A                       INTEGER,
    B                       INTEGER,
    C                       INTEGER,
    D                       INTEGER,
    PRR                     REAL,
    PRR_error               REAL,
    mean_reporting_frequency REAL,
    PRIMARY KEY (drug_1_rxnorm_id, drug_2_rxnorm_id, condition_concept_name)
);
CREATE INDEX IF NOT EXISTS idx_pair ON twosides(drug_1_rxnorm_id, drug_2_rxnorm_id);
CREATE INDEX IF NOT EXISTS idx_pair_rev ON twosides(drug_2_rxnorm_id, drug_1_rxnorm_id);
"""

# (rxcui, generic name) for the demo regimen.
WARFARIN     = ("11289",  "warfarin")
ASPIRIN      = ("1191",   "aspirin")
IBUPROFEN    = ("5640",   "ibuprofen")
FLUOXETINE   = ("4493",   "fluoxetine")
TRAMADOL     = ("10689",  "tramadol")
METFORMIN    = ("6809",   "metformin")
LISINOPRIL   = ("29046",  "lisinopril")
ATORVASTATIN = ("83367",  "atorvastatin")
SIMVASTATIN  = ("36567",  "simvastatin")
CLOPIDOGREL  = ("32968",  "clopidogrel")
OMEPRAZOLE   = ("7646",   "omeprazole")

# TODO(synthetic-data): the rows below are hand-authored, not extracted from
# the real TWOSIDES dataset. The drug pairs and condition names are correct
# clinical pharmacology; the PRR / A / mean_reporting_frequency values are
# illustrative. Replace this whole list with a real TWOSIDES extract before
# presenting.
#
# Each row: (drug_a, drug_b, condition, A, B, C, D, PRR, PRR_err, mean_freq)
# Values reflect realistic TWOSIDES-style signal strengths for these pairs;
# they are illustrative for the demo, not for clinical use.
ROWS = [
    # Warfarin + Aspirin → bleeding cluster. Major, well-established.
    (*WARFARIN, *ASPIRIN, "Gastrointestinal haemorrhage",   1842, 6210, 1840, 998212, 6.41, 0.04, 0.229),
    (*WARFARIN, *ASPIRIN, "Haematuria",                      612, 7440,  890, 999362, 3.92, 0.05, 0.076),
    (*WARFARIN, *ASPIRIN, "Epistaxis",                       498, 7554,  610, 999642, 4.11, 0.06, 0.062),
    (*WARFARIN, *ASPIRIN, "Intracranial haemorrhage",        128, 7924,  142, 1000110, 4.55, 0.10, 0.016),

    # Warfarin + Ibuprofen → also bleeding, GI focus.
    (*WARFARIN, *IBUPROFEN, "Gastrointestinal haemorrhage",  922, 5430, 2102, 998850, 4.21, 0.05, 0.145),
    (*WARFARIN, *IBUPROFEN, "Anaemia",                       412, 5940, 1488, 999464, 2.66, 0.06, 0.065),

    # Aspirin + Ibuprofen → blunting + GI; classic competitive pharmacology.
    (*ASPIRIN, *IBUPROFEN,  "Gastrointestinal haemorrhage", 1322, 6890, 1844, 998250, 3.81, 0.04, 0.161),
    (*ASPIRIN, *IBUPROFEN,  "Dyspepsia",                     680, 7532,  912, 999180, 2.92, 0.05, 0.083),

    # Fluoxetine + Tramadol → serotonin syndrome. The subtle case.
    (*FLUOXETINE, *TRAMADOL, "Serotonin syndrome",           412, 5300,   88, 999000, 8.81, 0.07, 0.072),
    (*FLUOXETINE, *TRAMADOL, "Seizure",                      188, 5524,  340, 998748, 3.10, 0.09, 0.033),
    (*FLUOXETINE, *TRAMADOL, "Hyperreflexia",                 92, 5620,   38, 999050, 7.20, 0.18, 0.016),

    # Metformin + Lisinopril → real but modest; hypoglycaemia and renal signals.
    (*METFORMIN, *LISINOPRIL, "Hypoglycaemia",                312, 7800,  840, 998248, 1.92, 0.07, 0.038),
    (*METFORMIN, *LISINOPRIL, "Renal impairment",             238, 7874,  720, 998368, 1.66, 0.08, 0.029),
    (*METFORMIN, *LISINOPRIL, "Lactic acidosis",               42, 8070,   88, 999000, 2.45, 0.21, 0.005),

    # Atorvastatin + Clopidogrel → CYP3A4 competition; classic disagreement case
    # (early reports flagged it, later meta-analyses softened the signal).
    (*ATORVASTATIN, *CLOPIDOGREL, "Myocardial infarction",    268, 7820,  490, 998622, 1.81, 0.08, 0.033),
    (*ATORVASTATIN, *CLOPIDOGREL, "Stent thrombosis",          88, 8000,  124, 998988, 2.40, 0.16, 0.011),

    # Simvastatin + Clopidogrel → similar to above, used as alt comparator.
    (*SIMVASTATIN, *CLOPIDOGREL, "Myocardial infarction",     188, 7900,  490, 998622, 1.45, 0.10, 0.023),
    (*SIMVASTATIN, *CLOPIDOGREL, "Rhabdomyolysis",             32, 8056,   48, 999064, 2.78, 0.24, 0.004),

    # Clopidogrel + Omeprazole → FDA labeled interaction (CYP2C19); good
    # NemoClaw demo data (the FDA label is loud, FAERS is moderate, TWOSIDES
    # signal is real but not extreme).
    (*CLOPIDOGREL, *OMEPRAZOLE, "Myocardial infarction",      324, 7680,  490, 998622, 2.18, 0.07, 0.040),
    (*CLOPIDOGREL, *OMEPRAZOLE, "Acute coronary syndrome",    188, 7816,  290, 998822, 2.34, 0.10, 0.023),
]


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    con.executemany(
        """
        INSERT INTO twosides (
            drug_1_rxnorm_id, drug_1_concept_name,
            drug_2_rxnorm_id, drug_2_concept_name,
            condition_concept_name, A, B, C, D,
            PRR, PRR_error, mean_reporting_frequency
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ROWS,
    )
    con.commit()
    count = con.execute("SELECT COUNT(*) FROM twosides").fetchone()[0]
    pairs = con.execute(
        "SELECT COUNT(DISTINCT drug_1_rxnorm_id || '-' || drug_2_rxnorm_id) FROM twosides"
    ).fetchone()[0]
    con.close()
    print(f"wrote {count} rows across {pairs} drug pairs to {DB_PATH}")


if __name__ == "__main__":
    main()
