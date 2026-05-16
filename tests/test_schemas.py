"""Schema lock tests — ensure the JOINT-01 contract holds.

These tests are the canary: if someone changes the schema in a breaking way
the test suite will fail. Per CLAUDE.md the schema is locked after H4.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.schemas import (
    Confidence,
    Coverage,
    Evidence,
    Finding,
    NormalizedDrug,
    Severity,
    SeverityHint,
    SourceFindings,
    SynthesizedInteraction,
)


def test_source_findings_normalizes_drug_pair_order_and_case() -> None:
    sf = SourceFindings(
        source="openfda_label",
        drug_pair=("Warfarin", "Aspirin"),
        queried_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
        findings=[],
        coverage=Coverage.NO_DATA,
        confidence=Confidence.LOW,
    )
    assert sf.drug_pair == ("aspirin", "warfarin")


def test_source_findings_rejects_extra_fields() -> None:
    with pytest.raises(Exception):
        SourceFindings(
            source="openfda_label",
            drug_pair=("a", "b"),
            queried_at=datetime.now(timezone.utc),
            findings=[],
            coverage=Coverage.NO_DATA,
            confidence=Confidence.LOW,
            mystery_field=1,  # type: ignore[call-arg]
        )


def test_finding_severity_hint_vocab() -> None:
    f = Finding(type="interaction", description="x", severity_hint=SeverityHint.MAJOR)
    assert f.severity_hint == SeverityHint.MAJOR
    with pytest.raises(Exception):
        Finding(type="interaction", description="x", severity_hint="lethal")  # type: ignore[arg-type]


def test_synthesized_interaction_severity_vocab() -> None:
    s = SynthesizedInteraction(
        drug_pair=("a", "b"),
        severity=Severity.MAJOR,
        headline="x",
        reasoning="y",
    )
    assert s.severity == Severity.MAJOR
    assert s.predicted_but_unverified is False


def test_drug_pair_key_is_order_independent() -> None:
    from backend.schemas import DrugPair

    a = NormalizedDrug(input_name="Warfarin", rxcui="11289", generic_name="warfarin", found=True)
    b = NormalizedDrug(input_name="Aspirin", rxcui="1191", generic_name="aspirin", found=True)
    assert DrugPair(a=a, b=b).key == DrugPair(a=b, b=a).key


def test_evidence_defaults_are_none() -> None:
    e = Evidence()
    assert (e.raw_excerpt, e.frequency, e.probability, e.source_url) == (None, None, None, None)
