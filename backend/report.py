"""Report assembly (BE-10).

Take a list of `SynthesizedInteraction` and produce a `RegimenReport`
sorted by severity with an overall summary and a patient-facing rewrite.

The patient-friendly version uses nano-30b when available; falls back to a
simple plain-language template otherwise.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable

from backend.llm import NANO_MODEL, LLMUnavailable, chat
from backend.schemas import (
    NormalizedDrug,
    RegimenReport,
    Severity,
    SynthesizedInteraction,
)

log = logging.getLogger(__name__)


_SEVERITY_ORDER = {
    Severity.CONTRAINDICATED: 0,
    Severity.MAJOR: 1,
    Severity.MODERATE: 2,
    Severity.MINOR: 3,
    Severity.NO_CONCERN: 4,
}


def _sort_key(s: SynthesizedInteraction) -> tuple[int, str]:
    return (_SEVERITY_ORDER[s.severity], s.drug_pair[0] + s.drug_pair[1])


def _overall_summary(interactions: list[SynthesizedInteraction]) -> str:
    counts = {s: 0 for s in Severity}
    for i in interactions:
        counts[i.severity] += 1
    n_total = len(interactions)
    n_real = n_total - counts[Severity.NO_CONCERN]
    pieces: list[str] = []
    if counts[Severity.CONTRAINDICATED]:
        pieces.append(f"{counts[Severity.CONTRAINDICATED]} contraindicated")
    if counts[Severity.MAJOR]:
        pieces.append(f"{counts[Severity.MAJOR]} major")
    if counts[Severity.MODERATE]:
        pieces.append(f"{counts[Severity.MODERATE]} moderate")
    if counts[Severity.MINOR]:
        pieces.append(f"{counts[Severity.MINOR]} minor")
    if not pieces:
        return f"No interaction signal across {n_total} evaluated pairs."
    summary = ", ".join(pieces)
    return (
        f"{n_real} interaction(s) flagged across {n_total} evaluated pairs: "
        f"{summary}."
    )


_PATIENT_SYSTEM = (
    "Rewrite a clinician-facing drug-interaction summary into plain language "
    "for a patient. Keep it factual; do not add new clinical claims or "
    "recommendations. Use 'you' framing. Do not include drug doses or "
    "medical jargon. 4 sentences max. No bullets, no headers, no preamble — "
    "just the rewritten paragraph."
)


async def _patient_summary(clinician_summary: str, interactions: list[SynthesizedInteraction]) -> str:
    """Plain-language summary; falls back to a deterministic template."""
    if not interactions:
        return "Your medication list does not show any obvious interactions in the sources we checked."

    detail_lines = []
    for i in interactions:
        if i.severity == Severity.NO_CONCERN:
            continue
        detail_lines.append(
            f"- {i.drug_pair[0]} + {i.drug_pair[1]} ({i.severity.value}): {i.headline}"
        )
    body = clinician_summary + "\n\nPair details:\n" + "\n".join(detail_lines)

    try:
        raw = await chat(
            model=NANO_MODEL,
            system=_PATIENT_SYSTEM,
            user=body,
            temperature=0.2,
            max_tokens=300,
            timeout=60.0,
        )
        text = (raw or "").strip()
        if text:
            return text
    except LLMUnavailable:
        log.info("patient summary fallback: no NEMO_API_KEY")
    except Exception as e:  # noqa: BLE001
        log.warning("patient summary LLM call failed: %s", e)

    # Deterministic fallback — readable, but flat.
    flagged = [i for i in interactions if i.severity != Severity.NO_CONCERN]
    if not flagged:
        return "Your medications look broadly safe together based on the sources we checked."
    leader = flagged[0]
    return (
        f"Some of your medication pairings need attention. The most important "
        f"is {leader.drug_pair[0]} together with {leader.drug_pair[1]}: "
        f"{leader.headline.lower()} "
        f"{len(flagged) - 1} other pairing(s) are flagged at lower severity. "
        "Please review with your prescriber before changing any medication."
    )


_CORE_SOURCES = ("openfda_label", "openfda_faers", "decagon")


async def build_report(
    regimen: list[NormalizedDrug],
    pair_results: Iterable[SynthesizedInteraction],
    *,
    new_pairs: list[tuple[str, str]] | None = None,
    cached_pairs: list[tuple[str, str]] | None = None,
    source_findings: dict | None = None,
) -> RegimenReport:
    """Aggregate per-pair synthesis output into a `RegimenReport`."""
    interactions = sorted(pair_results, key=_sort_key)
    overall = _overall_summary(interactions)
    patient = await _patient_summary(overall, interactions)

    # Sources from citations (works for non-no_concern results)
    consulted: set[str] = {c.source for i in interactions for c in i.citations}

    # Sources actually queried for new pairs — include even if NO_DATA
    if source_findings:
        for sf_list in source_findings.values():
            for sf in sf_list:
                consulted.add(sf.source)

    # For cached pairs the source_findings are gone, but the core three sources
    # were always queried when the pair was first computed.
    if cached_pairs:
        consulted.update(_CORE_SOURCES)

    sources_consulted = sorted(consulted)
    return RegimenReport(
        regimen=regimen,
        generated_at=datetime.now(timezone.utc),
        overall_summary=overall,
        interactions=interactions,
        new_pairs=new_pairs or [],
        cached_pairs=cached_pairs or [],
        patient_friendly_summary=patient,
        sources_consulted=sources_consulted,
    )
