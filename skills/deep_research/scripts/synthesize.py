"""Nemotron synthesis for DeepResearchReport.

Mirrors the calling convention in backend/synthesis.py but is standalone
(no backend imports) so it can run from the skills directory.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

import httpx

log = logging.getLogger(__name__)

NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"

ASPECTS = [
    "mechanism",
    "indications",
    "contraindications",
    "adverse_events",
    "interactions",
    "pharmacokinetics",
]

SYSTEM_PROMPT = """\
You are a clinical pharmacology expert synthesizing research findings about a drug.
You will receive search results for a specific pharmacological aspect of a drug and must produce
a concise, accurate summary suitable for a clinical decision-support tool.

Always return STRICT JSON with this schema:
{
  "summary": "<2-4 sentence factual summary of this aspect>",
  "citations": [
    {"title": "...", "url": "...", "quote": "<short relevant excerpt>"}
  ]
}

Cite only the sources provided. If the results are insufficient for a confident summary, state that clearly in the summary field. Return ONLY the JSON object with no surrounding text.
"""


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
    # Strip markdown fences if model wraps in ```json
    if content.startswith("```"):
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.rstrip("`").strip()
    return json.loads(content)


def _fallback_finding(aspect: str, results: list[dict]) -> dict[str, Any]:
    """Rule-based fallback when Nemotron is unreachable."""
    snippets = " ".join(r.get("description", "") for r in results[:3])
    summary = (snippets[:400] + "...") if len(snippets) > 400 else snippets or f"No data found for {aspect}."
    citations = [{"title": r["title"], "url": r["url"], "quote": r.get("description", "")[:150]}
                 for r in results[:3]]
    return {"aspect": aspect, "summary": summary, "citations": citations}


def synthesize_drug(drug: str, evidence: dict[str, list[dict]], model: str, api_key: str) -> dict[str, Any]:
    """Build a DeepResearchReport dict from per-aspect search results.

    `evidence` maps aspect name → list of Brave result dicts.
    """
    findings = []
    for aspect in ASPECTS:
        results = evidence.get(aspect, [])
        if not results:
            continue

        user_prompt = (
            f"Drug: {drug}\n"
            f"Aspect: {aspect}\n\n"
            f"Search results:\n"
            + json.dumps(results, indent=2)
        )

        try:
            raw = _chat_json(model, api_key, SYSTEM_PROMPT, user_prompt)
            finding = {
                "aspect": aspect,
                "summary": str(raw.get("summary", "")).strip() or f"No summary produced for {aspect}.",
                "citations": raw.get("citations", [])[:5],
            }
        except Exception as e:  # noqa: BLE001
            log.warning("synthesis fallback for %s: %s", aspect, e)
            finding = _fallback_finding(aspect, results)

        findings.append(finding)

    # Executive summary — synthesize from all aspects combined
    all_snippets = " ".join(f.get("summary", "") for f in findings)
    exec_user = (
        f"Drug: {drug}\n\n"
        f"Per-aspect summaries:\n{all_snippets[:2000]}\n\n"
        "Write a 2-4 sentence executive summary suitable for a clinical pharmacist."
    )
    try:
        exec_raw = _chat_json(model, api_key, SYSTEM_PROMPT, exec_user)
        exec_summary = str(exec_raw.get("summary", "")).strip()
    except Exception as e:  # noqa: BLE001
        log.warning("executive summary fallback: %s", e)
        exec_summary = all_snippets[:400] or f"Research summary for {drug}."

    return {
        "report_type": "deep_research",
        "schema_version": "1.0",
        "drug": drug,
        "generated_at": datetime.utcnow().isoformat(),
        "executive_summary": exec_summary,
        "findings": findings,
    }
