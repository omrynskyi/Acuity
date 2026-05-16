"""OpenFDA FAERS source agent (BE-06).

FAERS returns full safety case reports. We aggregate `reactionmeddrapt`
counts across all returned cases for the drug pair, then surface the top
reactions as Findings. No LLM call — the data is already structured, and
deterministic counting is faster and more honest than asking a model to
"summarize" frequencies.

Severity hint heuristic: anchored on absolute co-report frequency. Tuned to
match the published TWOSIDES noise floor (~100 co-reports = real signal).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.schemas import (
    Confidence,
    Coverage,
    Evidence,
    Finding,
    SeverityHint,
    SourceFindings,
)

log = logging.getLogger(__name__)

FAERS_URL = "https://api.fda.gov/drug/event.json"
_TIMEOUT = httpx.Timeout(15.0, connect=4.0)
_COUNT_LIMIT = 25  # Top-N reactions to consider via the count aggregation API.
_MAX_FINDINGS = 5
_MIN_FREQ = 20  # Drop reactions reported in fewer than this many co-cases.


# Common case-level signals we promote to "serious" framing in the description.
_SERIOUS_TERMS = {
    "haemorrhage", "hemorrhage", "bleeding", "syndrome", "necrosis",
    "thrombosis", "arrest", "death", "infarction", "failure", "coma",
    "seizure", "convulsion", "anaphyl",
}


def _severity_for(count: int, total_cases: int) -> Optional[SeverityHint]:
    """Map a single-reaction co-report count to severity_hint.

    FAERS reactions inherit baseline noise from sick polypharmacy patients,
    so an absolute count alone over-promotes generic symptoms (nausea,
    fatigue) when the total case count is huge. Major requires *both* a
    large absolute count and a meaningful share; otherwise we cap at
    moderate and let the synthesis agent weigh it.

    Thresholds:
      major:    count ≥ 200 AND share ≥ 20%
      moderate: count ≥ 200 OR  share ≥ 8%
      minor:    count ≥ _MIN_FREQ
    """
    if total_cases <= 0:
        return None
    share = count / total_cases
    if count >= 200 and share >= 0.20:
        return SeverityHint.MAJOR
    if count >= 200 or share >= 0.08:
        return SeverityHint.MODERATE
    if count >= _MIN_FREQ:
        return SeverityHint.MINOR
    return None


async def _fetch_reaction_counts(
    client: httpx.AsyncClient, drug_a: str, drug_b: str
) -> Optional[tuple[list[tuple[str, int]], int]]:
    """Return (top reactions, total cases) via the FAERS count aggregation.

    The `count=patient.reaction.reactionmeddrapt.exact` parameter asks OpenFDA
    to aggregate reaction frequencies across all matching cases server-side.
    Returns None on hard error.
    """
    search = (
        f"patient.drug.openfda.generic_name:{drug_a.lower()}"
        f"+AND+patient.drug.openfda.generic_name:{drug_b.lower()}"
    )

    # First call: top-N reactions across all matching cases.
    try:
        r = await client.get(
            f"{FAERS_URL}?search={search}"
            f"&count=patient.reaction.reactionmeddrapt.exact&limit={_COUNT_LIMIT}"
        )
    except httpx.HTTPError as e:
        log.warning("faers count fetch error for %s+%s: %s", drug_a, drug_b, e)
        return None
    if r.status_code == 404:
        return [], 0
    if r.status_code == 429:
        log.warning("faers rate-limited for %s+%s", drug_a, drug_b)
        return None
    if r.status_code >= 400:
        log.warning("faers count http %s for %s+%s", r.status_code, drug_a, drug_b)
        return [], 0
    results = r.json().get("results") or []
    reactions = [(row["term"], int(row["count"])) for row in results if row.get("term")]

    # Second call: total case count for the pair (limit=1; meta.results.total).
    try:
        r2 = await client.get(f"{FAERS_URL}?search={search}&limit=1")
        if r2.status_code == 200:
            total = int(r2.json().get("meta", {}).get("results", {}).get("total") or 0)
        else:
            total = 0
    except httpx.HTTPError:
        total = sum(c for _, c in reactions[:5]) or 1  # rough fallback

    return reactions, total


def _describe(term: str, count: int, total: int) -> str:
    """Plain-clinician description for a reaction co-report."""
    pct = (count / total * 100) if total else 0
    flavor = ""
    low = term.lower()
    if any(t in low for t in _SERIOUS_TERMS):
        flavor = " — serious-event category"
    return (
        f"{term.title()} co-reported in {count} of {total} cases "
        f"({pct:.0f}%){flavor}."
    )


async def query_faers(
    drug_a: str,
    drug_b: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> SourceFindings:
    """Run the FAERS source agent for the unordered pair (drug_a, drug_b)."""
    owned = client is None
    if owned:
        client = httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        fetched = await _fetch_reaction_counts(client, drug_a, drug_b)

        if fetched is None:
            return SourceFindings(
                source="openfda_faers",
                drug_pair=(drug_a, drug_b),
                queried_at=datetime.now(timezone.utc),
                findings=[],
                coverage=Coverage.NO_DATA,
                confidence=Confidence.LOW,
            )

        reactions, total = fetched

        # Promote any serious-category reaction in the top _COUNT_LIMIT into
        # the findings shortlist even if other terms are more frequent. This
        # surfaces signals like serotonin syndrome that lose the popularity
        # contest to generic terms like "headache" or "drug interaction".
        ranked = sorted(
            reactions,
            key=lambda x: (
                any(t in x[0].lower() for t in _SERIOUS_TERMS),
                x[1],
            ),
            reverse=True,
        )

        findings: list[Finding] = []
        seen: set[str] = set()
        for term, count in ranked:
            if term in seen:
                continue
            seen.add(term)
            sev = _severity_for(count, total)
            if sev is None:
                continue
            url = (
                f"{FAERS_URL}?search=patient.drug.openfda.generic_name:{drug_a.lower()}"
                f"+AND+patient.drug.openfda.generic_name:{drug_b.lower()}"
            )
            findings.append(
                Finding(
                    type="adverse_event",
                    description=_describe(term, count, total),
                    severity_hint=sev,
                    evidence=Evidence(
                        raw_excerpt=f"{term} ({count}/{total} cases)",
                        frequency=float(count),
                        source_url=url,
                    ),
                )
            )
            if len(findings) >= _MAX_FINDINGS:
                break

        if total == 0:
            coverage = Coverage.NO_DATA
            confidence = Confidence.LOW
        elif total < 50:
            coverage = Coverage.PARTIAL
            confidence = Confidence.LOW
        else:
            coverage = Coverage.FULL
            confidence = Confidence.HIGH if findings else Confidence.MEDIUM

        return SourceFindings(
            source="openfda_faers",
            drug_pair=(drug_a, drug_b),
            queried_at=datetime.now(timezone.utc),
            findings=findings,
            coverage=coverage,
            confidence=confidence,
        )
    finally:
        if owned:
            await client.aclose()
