"""Decagon SQLite + source-agent tests.

The DB-backed cases skip cleanly when data/decagon.sqlite hasn't been built
(CI-friendly). The severity-rubric and ranker tests run pure-Python and
always execute.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.sources.decagon_db import (
    DEFAULT_DB,
    PolypharmacyEffect,
    known_drug_names,
    lookup_cid_for_name,
    query_pair_effects,
    rank_effects,
    severity_for,
)

_db_present = DEFAULT_DB.exists()
requires_db = pytest.mark.skipif(
    not _db_present,
    reason="data/decagon.sqlite missing; run scripts/build_decagon.py --all",
)


# --------------------------------------------------------------------------- #
# Severity rubric — pure-Python
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "name, expected",
    [
        ("haemorrhage intracranial", "major"),
        ("Intracranial haemorrhage", "major"),
        ("serotonin syndrome", "major"),
        ("Stevens-Johnson syndrome", "major"),
        ("Anaemia", "moderate"),
        ("hypoglycaemia", "moderate"),
        ("nausea", "minor"),
        ("Cough", "minor"),
        ("totally novel condition X", "moderate"),  # default
    ],
)
def test_severity_rubric_buckets_known_terms(name: str, expected: str) -> None:
    assert severity_for(name) == expected


# --------------------------------------------------------------------------- #
# Ranker — pure-Python
# --------------------------------------------------------------------------- #

def _eff(name: str) -> PolypharmacyEffect:
    # Effect_name's hash is used for fake UMLS CUI so dedup works in tests.
    return PolypharmacyEffect(
        cid_a="CID000000001",
        cid_b="CID000000002",
        umls_cui=f"C{abs(hash(name)) % 9999999:07d}",
        effect_name=name,
    )


def test_ranker_quota_is_two_major_one_moderate_one_minor() -> None:
    effects = [
        _eff("haemorrhage intracranial"),
        _eff("ventricular fibrillation"),
        _eff("Embolism pulmonary"),
        _eff("hyperkalaemia"),
        _eff("Anaemia"),
        _eff("nausea"),
        _eff("dizziness"),
    ]
    picked = rank_effects(effects)
    sevs = [p.severity_hint for p in picked]
    assert sevs.count("major") == 2
    assert sevs.count("moderate") == 1
    assert sevs.count("minor") == 1


def test_ranker_drops_short_shorthand_names() -> None:
    # "Mod" should be dropped even though severity_for("Mod") → "moderate".
    effects = [_eff("Mod"), _eff("hyperkalaemia")]
    picked = rank_effects(effects)
    names = [p.effect_name for p in picked]
    assert "Mod" not in names
    assert "hyperkalaemia" in names


def test_ranker_prefers_longer_more_specific_names() -> None:
    effects = [
        _eff("embolism"),                  # 8 chars, major
        _eff("haemorrhage intracranial"),  # 24 chars, major — should win
    ]
    picked = rank_effects(effects, max_findings=1)
    assert picked[0].effect_name == "haemorrhage intracranial"


# --------------------------------------------------------------------------- #
# DB-backed — skip when SQLite missing
# --------------------------------------------------------------------------- #

@requires_db
def test_pair_effect_table_loaded() -> None:
    import sqlite3

    con = sqlite3.connect(DEFAULT_DB)
    try:
        n = con.execute("SELECT COUNT(*) FROM pair_effect").fetchone()[0]
    finally:
        con.close()
    assert n > 4_000_000, f"expected >4M rows, got {n:,}"


@requires_db
def test_drug_map_resolves_demo_regimen() -> None:
    assert lookup_cid_for_name("warfarin") == "CID000006691"
    assert lookup_cid_for_name("aspirin") == "CID000002244"
    assert lookup_cid_for_name("ibuprofen") == "CID000003672"


@requires_db
def test_drug_map_brand_synonyms_resolve() -> None:
    # "coumadin" is a curated synonym for warfarin's orphaned Decagon CID.
    assert lookup_cid_for_name("coumadin") == "CID000006691"


@requires_db
def test_warfarin_aspirin_returns_bleeding_effect() -> None:
    cid_w = lookup_cid_for_name("warfarin")
    cid_a = lookup_cid_for_name("aspirin")
    assert cid_w and cid_a
    effects = query_pair_effects(cid_w, cid_a)
    assert effects, "expected >=1 effect for warfarin+aspirin"
    blood_terms = ("haemorrhage", "hemorrhage", "bleed")
    assert any(
        any(t in e.effect_name.lower() for t in blood_terms) for e in effects
    ), "no bleeding-related effect found for warfarin+aspirin"


@requires_db
def test_known_drug_names_nonempty() -> None:
    assert len(known_drug_names()) > 5000
