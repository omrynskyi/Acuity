"""ArXiv paper research source agent.

Searches the arXiv Atom API for peer-reviewed papers about drug-drug
interactions for a given pair. Returns SourceFindings with up to 3 results.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

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

ARXIV_API = "http://export.arxiv.org/api/query"
_NS = {"atom": "http://www.w3.org/2005/Atom"}
_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
_MAX_RESULTS = 3

_MAJOR_TERMS = ("fatal", "contraindicated", "severe", "life-threatening", "death")
_MODERATE_TERMS = ("avoid", "caution", "significant", "increased risk", "monitor")


def _severity_from_text(text: str) -> Optional[SeverityHint]:
    low = text.lower()
    if any(t in low for t in _MAJOR_TERMS):
        return SeverityHint.MAJOR
    if any(t in low for t in _MODERATE_TERMS):
        return SeverityHint.MODERATE
    return SeverityHint.MINOR


def _parse_entries(xml_bytes: bytes, drug_a: str, drug_b: str) -> list[Finding]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        log.warning("arxiv xml parse error: %s", e)
        return []

    findings: list[Finding] = []
    for entry in root.findall("atom:entry", _NS)[:_MAX_RESULTS]:
        title_el = entry.find("atom:title", _NS)
        summary_el = entry.find("atom:summary", _NS)
        link_el = entry.find("atom:id", _NS)

        title = (title_el.text or "").strip() if title_el is not None else ""
        summary = (summary_el.text or "").strip() if summary_el is not None else ""
        url = (link_el.text or "").strip() if link_el is not None else ""

        combined = f"{title} {summary}"
        sev = _severity_from_text(combined)
        excerpt = summary[:280] if summary else title[:280]

        findings.append(
            Finding(
                type="interaction",
                description=f"ArXiv paper: {title}",
                severity_hint=sev,
                evidence=Evidence(
                    raw_excerpt=excerpt or None,
                    source_url=url or None,
                ),
            )
        )
    return findings


async def query_arxiv(
    drug_a: str,
    drug_b: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> SourceFindings:
    """Search arXiv for papers on the drug pair interaction."""
    owned = client is None
    if owned:
        client = httpx.AsyncClient(timeout=_TIMEOUT)

    query = f'all:"{drug_a}" AND all:"{drug_b}" AND all:"drug interaction"'
    params = {
        "search_query": query,
        "start": 0,
        "max_results": _MAX_RESULTS,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    try:
        resp = await client.get(ARXIV_API, params=params)
    except httpx.HTTPError as e:
        log.warning("arxiv fetch error for %s/%s: %s", drug_a, drug_b, e)
        return SourceFindings(
            source="arxiv",
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
        log.warning("arxiv returned HTTP %s for %s/%s", resp.status_code, drug_a, drug_b)
        return SourceFindings(
            source="arxiv",
            drug_pair=(drug_a, drug_b),
            queried_at=datetime.now(timezone.utc),
            findings=[],
            coverage=Coverage.NO_DATA,
            confidence=Confidence.LOW,
        )

    findings = _parse_entries(resp.content, drug_a, drug_b)
    coverage = Coverage.FULL if findings else Coverage.NO_DATA
    confidence = Confidence.MEDIUM if findings else Confidence.LOW

    return SourceFindings(
        source="arxiv",
        drug_pair=(drug_a, drug_b),
        queried_at=datetime.now(timezone.utc),
        findings=findings,
        coverage=coverage,
        confidence=confidence,
    )
