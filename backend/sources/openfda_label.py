"""OpenFDA Label source agent (BE-05).

For a drug pair, fetches each drug's prescribing label and asks Nemotron
nano to extract any interaction signal between them. Returns SourceFindings.

Pure-text fallback (regex + keyword scan) is used when Nemotron is
unavailable so dev can run offline. The fallback is documented inline; it
is not as nuanced as the model and should not be relied on for the demo.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Optional

import httpx

from backend.llm import NANO_MODEL, LLMUnavailable, chat_json
from backend.schemas import (
    Confidence,
    Coverage,
    Evidence,
    Finding,
    SeverityHint,
    SourceFindings,
)

log = logging.getLogger(__name__)

OPENFDA_LABEL = "https://api.fda.gov/drug/label.json"
_TIMEOUT = httpx.Timeout(12.0, connect=4.0)

# Sections we feed to the model. Keep label payloads small to control tokens.
_LABEL_FIELDS = [
    "boxed_warning",
    "contraindications",
    "drug_interactions",
    "warnings_and_cautions",
]
_FIELD_CHAR_CAP = 12000


_NANO_SYSTEM = (
    "You are a clinical pharmacology assistant. Given two drug names and the "
    "prescribing label of one of them, decide whether the label flags an "
    "interaction with the OTHER drug. Be conservative: only flag when the "
    "label explicitly names the other drug, its drug class, or a clearly "
    "implied co-administration risk. Reply with strict JSON of the shape: "
    '{"interaction": true|false, "severity_hint": "major|moderate|minor", '
    '"excerpt": "verbatim quote from the label, <= 280 chars", '
    '"description": "one sentence in plain clinician language"}. '
    'If no interaction is flagged, return {"interaction": false}.'
)


async def _fetch_label(client: httpx.AsyncClient, drug_name: str) -> Optional[dict]:
    """Fetch one drug's most recent label. Returns the result dict or None."""
    params = {
        "search": f"openfda.generic_name:{drug_name.lower()}",
        "limit": 1,
    }
    try:
        r = await client.get(OPENFDA_LABEL, params=params)
    except httpx.HTTPError as e:
        log.warning("openfda label fetch error for %s: %s", drug_name, e)
        return None
    if r.status_code == 404:
        return None
    if r.status_code == 429:
        log.warning("openfda label rate-limited for %s", drug_name)
        return None
    try:
        r.raise_for_status()
    except httpx.HTTPError as e:
        log.warning("openfda label http error for %s: %s", drug_name, e)
        return None
    results = r.json().get("results") or []
    return results[0] if results else None


def _slice(label: dict) -> dict[str, str]:
    """Reduce the full label to the sections we care about, capped in size."""
    out: dict[str, str] = {}
    for field in _LABEL_FIELDS:
        val = label.get(field)
        if isinstance(val, list):
            val = " ".join(str(x) for x in val)
        if isinstance(val, str) and val.strip():
            out[field] = val[:_FIELD_CHAR_CAP]
    return out


# --------------------------------------------------------------------------- #
# LLM probe and keyword fallback
# --------------------------------------------------------------------------- #

async def _llm_probe(
    drug_a: str, drug_b: str, sections: dict[str, str], client: httpx.AsyncClient
) -> Optional[dict]:
    """Ask nano-30b whether drug_a's label flags an interaction with drug_b."""
    label_text = "\n\n".join(f"## {k}\n{v}" for k, v in sections.items())
    user = (
        f"Drug A (label below): {drug_a}\n"
        f"Drug B (other drug): {drug_b}\n\n"
        f"Drug A's label sections:\n{label_text}"
    )
    try:
        return await chat_json(
            model=NANO_MODEL,
            system=_NANO_SYSTEM,
            user=user,
            max_tokens=2048,
            client=client,
        )
    except LLMUnavailable:
        return None
    except Exception as e:  # network or parse errors — fall back, don't crash
        log.warning("nano label probe failed (%s); falling back to keyword scan", e)
        return None


_SEVERITY_KEYWORDS = {
    SeverityHint.MAJOR: ("contraindicated", "boxed warning", "fatal", "do not use", "severe"),
    SeverityHint.MODERATE: ("avoid", "caution", "increase", "increased risk", "monitor"),
    SeverityHint.MINOR: ("may", "occasionally", "rarely"),
}


def _keyword_scan(
    drug_a: str, drug_b: str, sections: dict[str, str]
) -> Optional[dict]:
    """Deterministic fallback: search for drug_b name in drug_a label sections."""
    needle = re.compile(rf"\b{re.escape(drug_b.lower())}\b", re.IGNORECASE)
    hit_section = None
    hit_excerpt = None
    for section, text in sections.items():
        m = needle.search(text)
        if m:
            hit_section = section
            start = max(0, m.start() - 100)
            end = min(len(text), m.end() + 180)
            hit_excerpt = text[start:end].strip()
            break
    if not hit_excerpt:
        return None
    sev = SeverityHint.MODERATE
    lowered = hit_excerpt.lower()
    for level, words in _SEVERITY_KEYWORDS.items():
        if any(w in lowered for w in words):
            sev = level
            break
    return {
        "interaction": True,
        "severity_hint": sev.value,
        "excerpt": hit_excerpt[:280],
        "description": f"Label section '{hit_section}' mentions {drug_b}.",
    }


# --------------------------------------------------------------------------- #
# Public source-agent entry point
# --------------------------------------------------------------------------- #

async def query_openfda_label(
    drug_a: str,
    drug_b: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> SourceFindings:
    """Run the label source agent for the unordered pair (drug_a, drug_b)."""

    owned = client is None
    if owned:
        client = httpx.AsyncClient(timeout=_TIMEOUT)
    try:
        label_a, label_b = await _fetch_label(client, drug_a), await _fetch_label(client, drug_b)

        findings: list[Finding] = []
        directions = [
            ("a", drug_a, drug_b, label_a),
            ("b", drug_b, drug_a, label_b),
        ]
        any_label_present = label_a is not None or label_b is not None

        for _, owner, other, label in directions:
            if not label:
                continue
            sections = _slice(label)
            if not sections:
                continue

            probe = await _llm_probe(owner, other, sections, client)
            used_fallback = False
            if not probe:
                probe = _keyword_scan(owner, other, sections)
                used_fallback = True
            if not probe or not probe.get("interaction"):
                continue

            severity_hint = probe.get("severity_hint")
            try:
                sev_enum = SeverityHint(severity_hint) if severity_hint else None
            except ValueError:
                sev_enum = None

            url = label.get("openfda", {}).get("application_number")
            source_url = (
                f"https://api.fda.gov/drug/label.json?search=openfda.generic_name:{owner.lower()}"
            )
            findings.append(
                Finding(
                    type="interaction",
                    description=(
                        probe.get("description")
                        or f"{owner} label flags interaction with {other}."
                    )
                    + (" [keyword fallback]" if used_fallback else ""),
                    severity_hint=sev_enum,
                    evidence=Evidence(
                        raw_excerpt=probe.get("excerpt") or None,
                        source_url=source_url,
                    ),
                )
            )

        labels_found = sum(1 for x in (label_a, label_b) if x is not None)
        if labels_found == 2:
            coverage = Coverage.FULL
        elif labels_found == 1:
            coverage = Coverage.PARTIAL
        else:
            coverage = Coverage.NO_DATA

        if findings and any(f.severity_hint == SeverityHint.MAJOR for f in findings):
            confidence = Confidence.HIGH
        elif findings:
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.HIGH if labels_found == 2 else Confidence.LOW

        return SourceFindings(
            source="openfda_label",
            drug_pair=(drug_a, drug_b),
            queried_at=datetime.now(timezone.utc),
            findings=findings,
            coverage=coverage,
            confidence=confidence,
        )
    finally:
        if owned:
            await client.aclose()
