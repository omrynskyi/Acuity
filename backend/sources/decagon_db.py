"""Low-level Decagon SQLite query helpers.

This module replaces the old hand-authored TWOSIDES helpers. The data layer
queries `data/decagon.sqlite`, populated from SNAP's bio-decagon-combo.csv
(Zitnik et al., *Bioinformatics* 2018) by `scripts/build_decagon.py`.

The schema literal `source: "twosides"` in `backend/schemas.py` is preserved;
the TWOSIDES source agent (`backend/sources/twosides.py`) now wraps these
helpers but still emits `source="twosides"` because Decagon is itself a
curated TWOSIDES extract — the "TWOSIDES leg" of the fan-out is intact, only
the underlying data is now real instead of hand-authored.
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "decagon.sqlite"


def _db_path() -> Path:
    return Path(os.environ.get("DECAGON_DB_PATH", str(DEFAULT_DB)))


# --------------------------------------------------------------------------- #
# Severity rubric — Decagon has no PRR/count column. We bucket effects by
# keyword over the MedDRA/UMLS name. Includes British + American spellings.
# --------------------------------------------------------------------------- #

_MAJOR_KEYWORDS = (
    "haemorrhage", "hemorrhage", "infarction", "embolism", "embolus",
    "anaphylaxis", "anaphylactic",
    "serotonin syndrome", "neuroleptic malignant",
    "stevens-johnson", "stevens johnson", "toxic epidermal", "necrolysis",
    "hepatic failure", "liver failure", "renal failure", "kidney failure",
    "pancreatitis", "agranulocytosis", "neutropenia",
    "intracranial", "subarachnoid", "subdural",
    "status epilepticus",
    "ventricular fibrillation", "ventricular tachycardia", "torsade",
    "cardiac arrest", "cardiac failure", "cardiopulmonary arrest",
    "suicide", "sepsis", "septic shock", "septicaemia", "septicemia",
    "coma", "respiratory arrest", "respiratory failure",
    "rhabdomyolysis", "myocardial infarction",
)

_MODERATE_KEYWORDS = (
    "bleeding", "bleed",
    "hypertension", "hypotension",
    "tachycardia", "bradycardia", "arrhythmia",
    "seizure", "convulsion",
    "hyperkalaemia", "hyperkalemia", "hypokalaemia", "hypokalemia",
    "hyperglycaemia", "hyperglycemia", "hypoglycaemia", "hypoglycemia",
    "hyponatraemia", "hyponatremia",
    "oedema", "edema",
    "jaundice", "hepatitis",
    "depression", "psychosis", "hallucination",
    "anaemia", "anemia",
    "asthma", "bronchospasm",
    "thrombosis", "thrombocytopenia",
)

_MINOR_KEYWORDS = (
    "nausea", "headache", "dizziness", "fatigue", "asthenia",
    "rash", "pruritus", "urticaria",
    "constipation", "diarrhoea", "diarrhea",
    "dry mouth", "xerostomia",
    "sweating", "hyperhidrosis",
    "insomnia", "somnolence",
    "myalgia", "arthralgia",
    "cough", "rhinitis",
    "emesis", "vomiting",
)


def severity_for(effect_name: str) -> str:
    """Bucket an effect name into major / moderate / minor."""
    s = effect_name.lower()
    for kw in _MAJOR_KEYWORDS:
        if kw in s:
            return "major"
    for kw in _MODERATE_KEYWORDS:
        if kw in s:
            return "moderate"
    for kw in _MINOR_KEYWORDS:
        if kw in s:
            return "minor"
    return "moderate"


# --------------------------------------------------------------------------- #
# Data types
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class PolypharmacyEffect:
    """One drug-pair × side-effect row from Decagon."""

    cid_a: str
    cid_b: str
    umls_cui: str
    effect_name: str

    @property
    def severity_hint(self) -> str:
        return severity_for(self.effect_name)


# --------------------------------------------------------------------------- #
# Queries
# --------------------------------------------------------------------------- #

def _connect() -> Optional[sqlite3.Connection]:
    db = _db_path()
    if not db.exists():
        return None
    con = sqlite3.connect(db)
    return con


def query_pair_effects(
    cid_a: str, cid_b: str, *, limit: int = 200
) -> list[PolypharmacyEffect]:
    """Return Decagon effects for the unordered pair (cid_a, cid_b).

    Returns [] when the pair has no Decagon coverage (either CID absent from
    the dataset, or pair never co-observed). Caller distinguishes these
    cases via `lookup_cid_for_name`.
    """
    con = _connect()
    if con is None:
        return []
    try:
        rows = con.execute(
            "SELECT cid_a, cid_b, umls_cui, effect_name FROM pair_effect "
            "WHERE (cid_a = ? AND cid_b = ?) OR (cid_a = ? AND cid_b = ?) "
            "LIMIT ?",
            (cid_a, cid_b, cid_b, cid_a, limit),
        ).fetchall()
    finally:
        con.close()
    return [PolypharmacyEffect(*r) for r in rows]


def lookup_cid_for_name(name: str) -> Optional[str]:
    """Resolve a drug name (case-insensitive) to its Decagon CID.

    `name` should be a generic ingredient name from RxNorm, but brand names
    that PubChem listed as synonyms also resolve (e.g. "coumadin" → warfarin
    CID).
    """
    if not name:
        return None
    con = _connect()
    if con is None:
        return None
    try:
        row = con.execute(
            "SELECT cid FROM drug_map WHERE name_lower = ? LIMIT 1",
            (name.strip().lower(),),
        ).fetchone()
    finally:
        con.close()
    return row[0] if row else None


def known_drug_names() -> set[str]:
    """All names that resolve to a Decagon CID."""
    con = _connect()
    if con is None:
        return set()
    try:
        rows = con.execute("SELECT name_lower FROM drug_map").fetchall()
    finally:
        con.close()
    return {r[0] for r in rows}


_MIN_NAME_CHARS = 5  # drops Decagon shorthand like "Mod" / "AFIB"


def rank_effects(
    effects: list[PolypharmacyEffect], *, max_findings: int = 4
) -> list[PolypharmacyEffect]:
    """Pick a representative spread from a long effect list.

    Aim: 2 major + 1 moderate + 1 minor. Falls through buckets when one is
    empty so we always return up to `max_findings`. Within each bucket,
    effects are deduped on UMLS CUI and then ranked by name length DESC
    (longer = more specific clinical phrase — e.g. "haemorrhage intracranial"
    beats "embolism" when both are valid majors). Names shorter than
    `_MIN_NAME_CHARS` are dropped as Decagon shorthand.
    """
    if not effects:
        return []

    buckets: dict[str, list[PolypharmacyEffect]] = {"major": [], "moderate": [], "minor": []}
    seen_cuis: set[str] = set()
    for e in effects:
        if len(e.effect_name) < _MIN_NAME_CHARS:
            continue
        if e.umls_cui in seen_cuis:
            continue
        seen_cuis.add(e.umls_cui)
        buckets[e.severity_hint].append(e)

    for bucket in buckets.values():
        bucket.sort(key=lambda e: (-len(e.effect_name), e.effect_name.lower()))

    quotas = [("major", 2), ("moderate", 1), ("minor", 1)]
    picked: list[PolypharmacyEffect] = []
    for sev, n in quotas:
        picked.extend(buckets[sev][:n])
    if len(picked) < max_findings:
        remainder: list[PolypharmacyEffect] = []
        for sev, n in quotas:
            remainder.extend(buckets[sev][n:])
        picked.extend(remainder[: max_findings - len(picked)])
    return picked[:max_findings]
