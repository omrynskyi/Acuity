"""Tavily web search source agent (replaces Brave Search).

Queries the Tavily Search API for drug interaction information for a given
drug pair. Uses TAVILY_API_KEY env var.

Falls back gracefully to NO_DATA if the API key is unset.
"""

from __future__ import annotations

import logging
import os
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

_ENDPOINT = "https://api.tavily.com/search"
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_MAX_RESULTS = 8

_MAJOR_TERMS = ("fatal", "contraindicated", "severe", "life-threatening", "death", "do not use")
_MODERATE_TERMS = ("avoid", "caution", "significant", "increased risk", "monitor", "warfarin")


def _severity_from_text(text: str) -> SeverityHint:
    low = text.lower()
    if any(t in low for t in _MAJOR_TERMS):
        return SeverityHint.MAJOR
    if any(t in low for t in _MODERATE_TERMS):
        return SeverityHint.MODERATE
    return SeverityHint.MINOR


def _parse_results(data: dict, drug_a: str, drug_b: str) -> list[Finding]:
    findings: list[Finding] = []
    for item in data.get("results", [])[:_MAX_RESULTS]:
        title = item.get("title", "")
        content = item.get("content", "")
        url = item.get("url", "")

        combined = f"{title} {content}"
        sev = _severity_from_text(combined)
        excerpt = content[:280] if content else title[:280]

        findings.append(
            Finding(
                type="interaction",
                description=f"Web result: {title}",
                severity_hint=sev,
                evidence=Evidence(
                    raw_excerpt=excerpt or None,
                    source_url=url or None,
                ),
            )
        )
    return findings


async def query_brave(
    drug_a: str,
    drug_b: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
    query_override: Optional[str] = None,
) -> SourceFindings:
    """Run a Tavily web search for the drug pair interaction."""
    api_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key:
        log.info("TAVILY_API_KEY not set; skipping web search for %s/%s", drug_a, drug_b)
        return SourceFindings(
            source="brave_search",
            drug_pair=(drug_a, drug_b),
            queried_at=datetime.now(timezone.utc),
            findings=[],
            coverage=Coverage.NO_DATA,
            confidence=Confidence.LOW,
        )

    query = query_override or f"{drug_a} {drug_b} drug interaction side effects"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "basic",
        "max_results": _MAX_RESULTS,
        "include_answer": False,
    }

    owned = client is None
    if owned:
        client = httpx.AsyncClient(timeout=_TIMEOUT)

    try:
        resp = await client.post(_ENDPOINT, json=payload)
    except httpx.HTTPError as e:
        log.warning("tavily search error for %s/%s: %s", drug_a, drug_b, e)
        return SourceFindings(
            source="brave_search",
            drug_pair=(drug_a, drug_b),
            queried_at=datetime.now(timezone.utc),
            findings=[],
            coverage=Coverage.NO_DATA,
            confidence=Confidence.LOW,
        )
    finally:
        if owned:
            await client.aclose()

    if resp.status_code != 200:
        log.warning("tavily returned HTTP %s for %s/%s", resp.status_code, drug_a, drug_b)
        return SourceFindings(
            source="brave_search",
            drug_pair=(drug_a, drug_b),
            queried_at=datetime.now(timezone.utc),
            findings=[],
            coverage=Coverage.NO_DATA,
            confidence=Confidence.LOW,
        )

    findings = _parse_results(resp.json(), drug_a, drug_b)
    coverage = Coverage.FULL if findings else Coverage.NO_DATA
    confidence = Confidence.MEDIUM if findings else Confidence.LOW

    return SourceFindings(
        source="brave_search",
        drug_pair=(drug_a, drug_b),
        queried_at=datetime.now(timezone.utc),
        findings=findings,
        coverage=coverage,
        confidence=confidence,
    )
