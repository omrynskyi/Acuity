#!/usr/bin/env python3
"""ArXiv Search skill — search peer-reviewed papers for a drug pair or free-form query.

Usage:
    python skills/arxiv_search/scripts/arxiv_search.py --drug-a "warfarin" --drug-b "aspirin"
    python skills/arxiv_search/scripts/arxiv_search.py --query "metformin drug interaction renal"
    python skills/arxiv_search/scripts/arxiv_search.py --drug-a "warfarin" --drug-b "aspirin" --max-results 10 --out /tmp/results.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "WARNING"), stream=sys.stderr)
log = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
_NS = {"atom": "http://www.w3.org/2005/Atom"}
_DEFAULT_MAX = 5

_SYNTHESIS_SYSTEM = """\
You are a clinical pharmacology expert reviewing peer-reviewed research papers about a drug-drug interaction.
Given a list of arXiv paper titles and abstracts, produce a concise clinical synthesis.

Return STRICT JSON:
{
  "clinical_summary": "<2-4 sentence summary of what the literature says about this interaction>",
  "severity_signal": "major|moderate|minor|none|unclear",
  "key_findings": ["<finding 1>", "<finding 2>", "..."],
  "citations": [{"title": "...", "arxiv_id": "...", "url": "...", "quote": "<short excerpt <=150 chars>"}]
}

Cite only the papers provided. Return ONLY the JSON object with no surrounding text.
"""


# --------------------------------------------------------------------------- #
# ArXiv query
# --------------------------------------------------------------------------- #

def _build_query(drug_a: str | None, drug_b: str | None, query: str | None) -> str:
    if query:
        return query
    assert drug_a and drug_b
    return f'all:"{drug_a}" AND all:"{drug_b}" AND all:"drug interaction"'


def _parse_feed(xml_bytes: bytes) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        log.error("arxiv xml parse error: %s", e)
        return []

    papers = []
    for entry in root.findall("atom:entry", _NS):
        arxiv_id_el = entry.find("atom:id", _NS)
        title_el = entry.find("atom:title", _NS)
        summary_el = entry.find("atom:summary", _NS)
        published_el = entry.find("atom:published", _NS)

        raw_id = (arxiv_id_el.text or "").strip() if arxiv_id_el is not None else ""
        arxiv_id = raw_id.split("/abs/")[-1] if "/abs/" in raw_id else raw_id

        authors = [
            (a.find("atom:name", _NS).text or "").strip()
            for a in entry.findall("atom:author", _NS)
            if a.find("atom:name", _NS) is not None
        ]

        published_raw = (published_el.text or "").strip() if published_el is not None else ""
        published = published_raw[:10] if published_raw else ""

        papers.append({
            "arxiv_id": arxiv_id,
            "title": (title_el.text or "").strip() if title_el is not None else "",
            "authors": authors,
            "published": published,
            "abstract": (summary_el.text or "").strip() if summary_el is not None else "",
            "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else raw_id,
        })
    return papers


def search_arxiv(search_query: str, max_results: int) -> list[dict[str, Any]]:
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }
    with httpx.Client(timeout=20.0) as client:
        resp = client.get(ARXIV_API, params=params)
    if resp.status_code != 200:
        print(f"ERROR: arXiv returned HTTP {resp.status_code}", file=sys.stderr)
        sys.exit(2)
    return _parse_feed(resp.content)


# --------------------------------------------------------------------------- #
# Nemotron synthesis (optional)
# --------------------------------------------------------------------------- #

def _chat_json(model: str, api_key: str, system: str, user: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.1,
        "max_tokens": 700,
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(f"{NVIDIA_BASE}/chat/completions", headers=headers, json=payload)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.rstrip("`").strip()
    return json.loads(content)


def _fallback_synthesis(papers: list[dict[str, Any]]) -> dict[str, Any]:
    snippets = [p["abstract"][:200] for p in papers[:3] if p["abstract"]]
    summary = " ".join(snippets)[:400] or "Insufficient abstract data for synthesis."
    return {
        "clinical_summary": summary,
        "severity_signal": "unclear",
        "key_findings": [p["title"] for p in papers[:3]],
        "citations": [
            {"title": p["title"], "arxiv_id": p["arxiv_id"], "url": p["url"], "quote": p["abstract"][:150]}
            for p in papers[:3]
        ],
    }


def synthesize(
    papers: list[dict[str, Any]],
    drug_a: str | None,
    drug_b: str | None,
    query: str | None,
    model: str,
    api_key: str,
) -> dict[str, Any]:
    subject = f"{drug_a} + {drug_b}" if drug_a and drug_b else (query or "drug interaction")
    user_prompt = (
        f"Subject: {subject}\n\n"
        "Papers:\n"
        + json.dumps(
            [{"title": p["title"], "arxiv_id": p["arxiv_id"], "url": p["url"], "abstract": p["abstract"][:500]}
             for p in papers],
            indent=2,
        )
    )
    try:
        return _chat_json(model, api_key, _SYNTHESIS_SYSTEM, user_prompt)
    except Exception as e:
        log.warning("nemotron synthesis failed (%s); using fallback", e)
        return _fallback_synthesis(papers)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Search arXiv for peer-reviewed drug interaction papers."
    )
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--drug-a", metavar="DRUG_A", help="First drug name (use with --drug-b)")
    group.add_argument("--query", metavar="QUERY", help="Free-form arXiv search query")
    p.add_argument("--drug-b", metavar="DRUG_B", help="Second drug name (required with --drug-a)")
    p.add_argument("--max-results", type=int, default=_DEFAULT_MAX,
                   help=f"Max papers to return (default: {_DEFAULT_MAX})")
    p.add_argument("--synthesize", action="store_true",
                   help="Synthesize results with Nemotron (requires NVIDIA_API_KEY)")
    p.add_argument("--out", metavar="PATH", help="Write JSON to file instead of stdout")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.drug_a and not args.drug_b:
        print("ERROR: --drug-b is required when --drug-a is specified", file=sys.stderr)
        sys.exit(1)

    drug_a = args.drug_a
    drug_b = args.drug_b
    query = args.query

    search_query = _build_query(drug_a, drug_b, query)
    papers = search_arxiv(search_query, args.max_results)

    synthesis: dict[str, Any] | None = None
    if args.synthesize:
        api_key = os.environ.get("NVIDIA_API_KEY", "")
        if not api_key:
            print("ERROR: NVIDIA_API_KEY is required for --synthesize", file=sys.stderr)
            sys.exit(1)
        model = os.environ.get("NEMOTRON_SUPER_MODEL", "nvidia/nemotron-3-super-120b-a12b")
        synthesis = synthesize(papers, drug_a, drug_b, query, model, api_key)

    report: dict[str, Any] = {
        "report_type": "arxiv_search",
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query": search_query,
        "total_results": len(papers),
        "papers": papers,
    }
    if drug_a and drug_b:
        report["drug_a"] = drug_a
        report["drug_b"] = drug_b
    if synthesis is not None:
        report["synthesis"] = synthesis

    output = json.dumps(report, indent=2)

    if args.out:
        Path(args.out).write_text(output)
        print(args.out)
    else:
        print(output)


if __name__ == "__main__":
    main()
