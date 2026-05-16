"""Brave Search web source agent.

Queries the Brave Search API for drug interaction information for a given
drug pair. Uses BRAVE_API_KEY and BRAVE_API_ENDPOINT env vars.

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

_DEFAULT_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_MAX_RESULTS = 5

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
    for item in data.get("web", {}).get("results", [])[:_MAX_RESULTS]:
        title = item.get("title", "")
        description = item.get("description", "")
        url = item.get("url", "")

        combined = f"{title} {description}"
        sev = _severity_from_text(combined)
        excerpt = description[:280] if description else title[:280]

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
) -> SourceFindings:
    """Run a Brave web search for the drug pair interaction."""
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        log.info("BRAVE_API_KEY not set; skipping brave_search for %s/%s", drug_a, drug_b)
        return SourceFindings(
            source="brave_search",
            drug_pair=(drug_a, drug_b),
            queried_at=datetime.now(timezone.utc),
            findings=[],
            coverage=Coverage.NO_DATA,
            confidence=Confidence.LOW,
        )

    endpoint = os.environ.get("BRAVE_API_ENDPOINT", _DEFAULT_ENDPOINT)
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {
        "q": f"{drug_a} {drug_b} drug interaction side effects",
        "count": _MAX_RESULTS,
        "search_lang": "en",
        "safesearch": "moderate",
    }

    owned = client is None
    if owned:
        client = httpx.AsyncClient(timeout=_TIMEOUT)

    try:
        resp = await client.get(endpoint, headers=headers, params=params)
    except httpx.HTTPError as e:
        log.warning("brave search error for %s/%s: %s", drug_a, drug_b, e)
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
        log.warning("brave returned HTTP %s for %s/%s", resp.status_code, drug_a, drug_b)
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
