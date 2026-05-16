"""TWOSIDES source agent (BE-07), backed by SNAP Decagon.

The "TWOSIDES leg" of the fan-out queries the SNAP Decagon CSV (Zitnik et
al., *Bioinformatics* 2018) — a curated extract of the canonical TWOSIDES
2018 release. Findings carry `source="twosides"` so the locked schema
(`backend/schemas.py:SourceName`) is preserved; underneath it's real data.

Flow:
    1. Normalize each input drug via RxNorm → ingredient name.
    2. Resolve ingredient name → Decagon CID via `lookup_cid_for_name`.
    3. Query Decagon for pair effects; rank a representative spread.
    4. Emit Coverage / Confidence based on CID resolution + effect content.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.schemas import (
    Confidence,
    Coverage,
    Evidence,
    Finding,
    SeverityHint,
    SourceFindings,
)
from backend.sources.decagon_db import (
    PolypharmacyEffect,
    known_drug_names,
    lookup_cid_for_name,
    query_pair_effects,
    rank_effects,
)
from backend.sources.rxnorm import normalize_drug

_MAX_FINDINGS = 4
_DECAGON_URL = "https://snap.stanford.edu/decagon/"


def _to_finding(
    effect: PolypharmacyEffect, *, name_a: str, name_b: str
) -> Finding:
    return Finding(
        type="predicted_effect",
        description=(
            f"{effect.effect_name} reported for this pair in the SNAP "
            f"Decagon TWOSIDES extract (UMLS:{effect.umls_cui})."
        ),
        severity_hint=SeverityHint(effect.severity_hint),
        evidence=Evidence(
            raw_excerpt=(
                f"Decagon: {name_a} + {name_b} → {effect.effect_name} "
                f"(UMLS:{effect.umls_cui})"
            ),
            frequency=None,    # Decagon dedups; no rate available.
            probability=None,  # No PRR in Decagon — do not fabricate one.
            source_url=_DECAGON_URL,
        ),
    )


async def query_twosides(drug_a: str, drug_b: str) -> SourceFindings:
    """Run the TWOSIDES/Decagon source agent for the unordered pair."""
    norm_a = await normalize_drug(drug_a)
    norm_b = await normalize_drug(drug_b)

    name_a = (norm_a.generic_name or norm_a.input_name or drug_a).strip()
    name_b = (norm_b.generic_name or norm_b.input_name or drug_b).strip()

    cid_a = lookup_cid_for_name(name_a) or lookup_cid_for_name(drug_a)
    cid_b = lookup_cid_for_name(name_b) or lookup_cid_for_name(drug_b)

    no_data = SourceFindings(
        source="twosides",
        drug_pair=(drug_a, drug_b),
        queried_at=datetime.now(timezone.utc),
        findings=[],
        coverage=Coverage.NO_DATA,
        confidence=Confidence.LOW,
    )

    if not cid_a or not cid_b:
        return no_data
    if not known_drug_names():
        return no_data

    effects = query_pair_effects(cid_a, cid_b, limit=200)
    picked = rank_effects(effects, max_findings=_MAX_FINDINGS)
    findings = [_to_finding(e, name_a=name_a, name_b=name_b) for e in picked]

    if not findings:
        # Both drugs known to Decagon but never co-observed → meaningful
        # "no signal at this pair", not absence of evidence.
        coverage = Coverage.FULL
        confidence = Confidence.MEDIUM
    else:
        coverage = Coverage.FULL
        any_major = any(f.severity_hint == SeverityHint.MAJOR for f in findings)
        confidence = Confidence.HIGH if any_major else Confidence.MEDIUM

    return SourceFindings(
        source="twosides",
        drug_pair=(drug_a, drug_b),
        queried_at=datetime.now(timezone.utc),
        findings=findings,
        coverage=coverage,
        confidence=confidence,
    )
