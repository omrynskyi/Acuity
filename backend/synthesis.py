"""Synthesis agent (BE-08).

Takes a list of SourceFindings for one drug pair and returns a single
`SynthesizedInteraction`. The primary path calls
`nvidia/nemotron-3-super-120b-a12b` with the prompt in `prompts/synthesis.md`.

When Nemotron is unreachable (no API key set, e.g. local dev outside the
NemoClaw sandbox) the agent falls back to a deterministic rule-based
synthesizer. The fallback is good enough to keep the pipeline runnable for
testing but is NOT the demo path — BE-09's prompt iteration assumes the LLM
path.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from pathlib import Path
from typing import Iterable

from backend.llm import SUPER_MODEL, LLMUnavailable, chat_json
from backend.schemas import (
    Citation,
    Coverage,
    Finding,
    Severity,
    SeverityHint,
    SourceFindings,
    SourceName,
    SynthesizedInteraction,
)

log = logging.getLogger(__name__)


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "synthesis.md"


def _system_prompt() -> str:
    """Load the synthesis prompt, stripping the user-facing markdown shell.

    The prompt file is structured for humans to read; we strip the trailing
    'End of system prompt.' line but keep everything else verbatim so prompt
    edits in BE-09 don't require code changes.
    """
    return PROMPT_PATH.read_text().strip()


def _render_findings(pair: tuple[str, str], sources: list[SourceFindings]) -> str:
    """Render the per-pair source findings into the user-prompt JSON block."""
    payload = {
        "drug_pair": list(pair),
        "sources": [
            {
                "source": s.source,
                "coverage": s.coverage.value,
                "confidence": s.confidence.value,
                "findings": [
                    {
                        "index": i,
                        "type": f.type,
                        "description": f.description,
                        "severity_hint": f.severity_hint.value if f.severity_hint else None,
                        "evidence": {
                            "raw_excerpt": f.evidence.raw_excerpt,
                            "frequency": f.evidence.frequency,
                            "probability": f.evidence.probability,
                        },
                    }
                    for i, f in enumerate(s.findings)
                ],
            }
            for s in sources
        ],
    }
    return (
        "Synthesize a verdict for the drug pair below using ONLY the source "
        "findings provided. Return strict JSON per the schema.\n\n"
        + json.dumps(payload, indent=2, default=str)
    )


_AGREEMENT_VALUES = {"agree", "disagree", "single_source", "no_data"}


def _coerce_severity(raw: object) -> Severity:
    """Lenient severity coercion: handles leading colons, whitespace,
    casing variants, and mid-string severity keywords."""
    if not isinstance(raw, str):
        return Severity.NO_CONCERN
    cleaned = raw.strip().lstrip(":").strip().lower()
    try:
        return Severity(cleaned)
    except ValueError:
        pass
    for sev in Severity:
        if sev.value in cleaned:
            return sev
    return Severity.NO_CONCERN


def _coerce_agreement(raw: object) -> str:
    if isinstance(raw, str):
        v = raw.strip().lstrip(":").strip().lower()
        if v in _AGREEMENT_VALUES:
            return v
    return "no_data"


def _parse_llm_output(
    pair: tuple[str, str], data: dict, sources: list[SourceFindings]
) -> SynthesizedInteraction:
    """Validate and coerce the model's JSON into SynthesizedInteraction.

    Tolerates leading colons, missing keys, and minor formatting noise the
    model occasionally emits. Drops bogus citations rather than failing the
    whole synthesis.
    """
    citations_raw = data.get("citations") or []
    cites: list[Citation] = []
    by_source = {s.source: s for s in sources}
    for c in citations_raw:
        if not isinstance(c, dict):
            continue
        src = c.get("source")
        idx = c.get("finding_index")
        quote = c.get("quote") or ""
        if src not in by_source:
            continue
        if not isinstance(idx, int) or idx < 0 or idx >= len(by_source[src].findings):
            continue
        cites.append(Citation(source=src, finding_index=idx, quote=str(quote)[:400]))

    return SynthesizedInteraction(
        drug_pair=pair,
        severity=_coerce_severity(data.get("severity")),
        headline=(str(data.get("headline") or "")).strip() or "No interaction signal.",
        reasoning=(str(data.get("reasoning") or "")).strip()
        or "No reasoning produced; treat with caution.",
        citations=cites,
        predicted_but_unverified=bool(data.get("predicted_but_unverified", False)),
        sources_agreement=_coerce_agreement(data.get("sources_agreement")),
    )


# --------------------------------------------------------------------------- #
# Deterministic fallback synthesizer
# --------------------------------------------------------------------------- #

_HINT_RANK = {None: 0, SeverityHint.MINOR: 1, SeverityHint.MODERATE: 2, SeverityHint.MAJOR: 3}
_RANK_TO_SEV = {
    0: Severity.NO_CONCERN,
    1: Severity.MINOR,
    2: Severity.MODERATE,
    3: Severity.MAJOR,
}


def _agreement(hints: Iterable[SeverityHint | None]) -> str:
    hint_list = list(hints)
    distinct_ranks = sorted({_HINT_RANK[h] for h in hint_list if h is not None})
    if not distinct_ranks:
        return "no_data"
    if len(distinct_ranks) == 1:
        return "agree" if len(hint_list) > 1 else "single_source"
    return "disagree" if (max(distinct_ranks) - min(distinct_ranks)) >= 2 else "agree"


def _fallback_synthesize(
    pair: tuple[str, str], sources: list[SourceFindings]
) -> SynthesizedInteraction:
    """Rule-based synthesizer for dev when Nemotron is offline.

    Aggregation policy:
      • Take the highest severity_hint across all findings.
      • If only one source produced findings, mark predicted_but_unverified.
      • Citations point at the highest-severity finding from each source.
    """
    all_hints: list[SeverityHint | None] = []
    contributing: list[SourceFindings] = []
    for s in sources:
        if s.findings:
            contributing.append(s)
            all_hints.extend(f.severity_hint for f in s.findings)

    if not contributing:
        return SynthesizedInteraction(
            drug_pair=pair,
            severity=Severity.NO_CONCERN,
            headline="No interaction signal across the queried sources.",
            reasoning=(
                "All three sources returned without flagging an interaction "
                "for this pair. Absence of signal is informative but not "
                "equivalent to safety; clinical judgment still applies."
            ),
            citations=[],
            sources_agreement="no_data",
        )

    top_rank = max(_HINT_RANK[h] for h in all_hints) if all_hints else 0
    severity = _RANK_TO_SEV[top_rank]

    citations: list[Citation] = []
    for s in contributing:
        # Pick the strongest finding from this source.
        best_idx, _ = max(
            ((i, _HINT_RANK[f.severity_hint]) for i, f in enumerate(s.findings)),
            key=lambda x: x[1],
        )
        f = s.findings[best_idx]
        citations.append(
            Citation(
                source=s.source,
                finding_index=best_idx,
                quote=(f.evidence.raw_excerpt or f.description)[:300],
            )
        )

    agreement = _agreement(all_hints)
    contributing_sources: set[SourceName] = {s.source for s in contributing}
    silent_with_coverage = any(
        s.source not in contributing_sources and s.coverage == Coverage.FULL
        for s in sources
    )

    headline_map = {
        Severity.MAJOR: f"Major interaction signal between {pair[0]} and {pair[1]}.",
        Severity.MODERATE: f"Moderate interaction signal between {pair[0]} and {pair[1]}.",
        Severity.MINOR: f"Mild interaction signal between {pair[0]} and {pair[1]}.",
    }
    headline = headline_map.get(severity, f"Limited signal for {pair[0]} + {pair[1]}.")

    reasoning_lines = [
        f"Sources contributing findings: {', '.join(sorted(contributing_sources))}.",
        f"Strongest single-source severity hint: {SeverityHint(_RANK_TO_SEV[top_rank].value).value if top_rank else 'none'}.",
        f"Cross-source agreement: {agreement}.",
    ]
    if silent_with_coverage and len(contributing_sources) < len(sources):
        reasoning_lines.append(
            "At least one source covered the pair with no signal; "
            "marking as predicted_but_unverified."
        )

    return SynthesizedInteraction(
        drug_pair=pair,
        severity=severity,
        headline=headline,
        reasoning=" ".join(reasoning_lines),
        citations=citations,
        predicted_but_unverified=(
            silent_with_coverage and len(contributing_sources) < len(sources)
        ),
        sources_agreement=agreement,
    )


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

async def synthesize_pair(
    pair: tuple[str, str],
    sources: list[SourceFindings],
    *,
    force_fallback: bool = False,
) -> SynthesizedInteraction:
    """Synthesize a single drug pair's verdict.

    Always returns a `SynthesizedInteraction`. Falls back to the rule-based
    synthesizer when Nemotron is unreachable.
    """
    if force_fallback:
        return _fallback_synthesize(pair, sources)

    try:
        raw = await chat_json(
            model=SUPER_MODEL,
            system=_system_prompt(),
            user=_render_findings(pair, sources),
            temperature=0.1,
            max_tokens=900,
        )
    except LLMUnavailable as e:
        log.info("synthesis fallback: %s", e)
        return _fallback_synthesize(pair, sources)
    except Exception as e:  # noqa: BLE001
        log.warning("synthesis LLM call failed (%s); using fallback", e)
        return _fallback_synthesize(pair, sources)

    try:
        return _parse_llm_output(pair, raw, sources)
    except Exception as e:  # noqa: BLE001
        log.warning("synthesis parse failed (%s); using fallback", e)
        return _fallback_synthesize(pair, sources)
