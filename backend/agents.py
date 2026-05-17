"""Autonomous research and quality-check agents for Acuity.

Three components:
  repair_drug_name  — LLM-driven fallback when RxNorm can't resolve an input.
  quality_check_agent — grades evidence sufficiency for one drug pair.
  research_agent    — picks the next tool call to fill evidence gaps.
  research_pair     — per-pair orchestrator that runs the full agentic loop.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from backend.agent_tools import TOOL_SCHEMA, TOOLS
from backend.fanout import fanout_pair
from backend.llm import NANO_MODEL, LLMUnavailable, chat_json, emit_agent_decision
from backend.schemas import SourceFindings

log = logging.getLogger(__name__)

MAX_FOLLOWUP_ROUNDS = 3


# ─────────────────────────────────────────────────────────────────────────────
# Drug-name repair
# ─────────────────────────────────────────────────────────────────────────────

import re as _re

_STRENGTH_RE = _re.compile(
    r"\b(\d+[./]\d+\s*(mg|mcg|mg/ml)?|\d+\s*(mg|mcg|g|ml|iu|%)|"
    r"\d+[-\s]?(day|days|tablet|tab|cap|capsule|pack|week|hr|hour)s?\b)",
    _re.IGNORECASE,
)

_NAME_REPAIR_SYSTEM = (
    "You are a pharmacology expert. Given a user-typed drug name that did not "
    "resolve in RxNorm, return the most likely generic ingredient name in lowercase. "
    "For combination products return the primary pharmacologically significant ingredient. "
    "Never return null for a recognizable brand or drug name.\n\n"
    "Examples:\n"
    '  "junel fe 1/20 28 day" -> {"generic": "norethindrone"}\n'
    '  "ortho tri-cyclen lo" -> {"generic": "norgestimate"}\n'
    '  "mucinex xr" -> {"generic": "guaifenesin"}\n'
    '  "tylenol extra strength" -> {"generic": "acetaminophen"}\n'
    '  "advil pm" -> {"generic": "ibuprofen"}\n'
    '  "zzyzx unknown123" -> {"generic": null}\n\n'
    'Return strict JSON only: {"generic": "<name>"} or {"generic": null}.'
)


async def repair_drug_name(raw: str) -> str | None:
    """Ask the LLM for the generic ingredient name when RxNorm returns nothing."""
    # Heuristic pre-clean: strip strength tokens and try the shorter form
    cleaned = _STRENGTH_RE.sub("", raw).strip().strip("-").strip()
    if cleaned and cleaned.lower() != raw.lower():
        from backend.sources.rxnorm import normalize_drug
        try:
            retry = await normalize_drug(cleaned)
            if retry.found:
                return (retry.generic_name or cleaned).lower()
        except Exception:
            pass

    try:
        result = await chat_json(
            model=NANO_MODEL,
            system=_NAME_REPAIR_SYSTEM,
            user=f'Drug name entered by user: "{raw}"',
            max_tokens=1024,
            timeout=30.0,
        )
        return (result.get("generic") or "").strip().lower() or None
    except (LLMUnavailable, Exception) as e:
        log.debug("repair_drug_name failed for %r: %s", raw, e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Quality-check agent
# ─────────────────────────────────────────────────────────────────────────────

_QUALITY_CHECK_SYSTEM = (
    "You are reviewing drug-interaction evidence for a single drug pair. "
    "Decide whether the gathered findings are sufficient to write a confident "
    "severity verdict with citations. "
    "Sufficient means: at least one source has a concrete severity signal (major/moderate/minor) "
    "AND at least one citation-quality excerpt exists. "
    'Return strict JSON: {"verdict": "sufficient"|"needs_more", "gaps": ["..."], "reason": "..."}. '
    '"gaps" is a short list describing what is missing, e.g. '
    '["no FDA label data", "no clinical citation", "sources disagree on mechanism"]. '
    'Return an empty gaps list when verdict is "sufficient".'
)


async def quality_check_agent(
    pair: tuple[str, str],
    findings: list[SourceFindings],
) -> dict:
    """Grade evidence sufficiency. Returns dict with verdict/gaps/reason."""
    drug_a, drug_b = pair
    sources_summary = []
    for sf in findings:
        sources_summary.append({
            "source": sf.source,
            "coverage": sf.coverage.value,
            "n_findings": len(sf.findings),
            "excerpts": [
                f.evidence.raw_excerpt[:120] if f.evidence and f.evidence.raw_excerpt else f.description[:120]
                for f in sf.findings[:3]
            ],
        })

    user_msg = (
        f"Drug pair: {drug_a} / {drug_b}\n"
        f"Evidence gathered:\n{json.dumps(sources_summary, indent=2)}"
    )

    try:
        result = await chat_json(
            model=NANO_MODEL,
            system=_QUALITY_CHECK_SYSTEM,
            user=user_msg,
            max_tokens=2048,
            timeout=45.0,
        )
        if result.get("verdict") not in ("sufficient", "needs_more"):
            result["verdict"] = "sufficient"
        return result
    except (LLMUnavailable, Exception) as e:
        log.debug("quality_check_agent failed for %s/%s: %s", drug_a, drug_b, e)
        # Default to sufficient so pipeline doesn't stall
        return {"verdict": "sufficient", "gaps": [], "reason": f"quality check unavailable: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# Research agent
# ─────────────────────────────────────────────────────────────────────────────

_RESEARCH_AGENT_SYSTEM = (
    "You are a drug-interaction research agent. Given a drug pair, gaps identified "
    "by a quality-check agent, and the history of tool calls already made, choose "
    "ONE tool from the registry to fill the most important gap. "
    "Do not repeat a tool that was already called with identical arguments. "
    "If no further action would help, return done. "
    "Return strict JSON: "
    '{"tool": "<name>", "args": {<tool_args>}, "why": "<one sentence reason>"} '
    'or {"tool": "done", "why": "<reason>"}.'
)


async def research_agent(
    pair: tuple[str, str],
    gaps: list[str],
    history: list[dict],
    findings: list[SourceFindings],
) -> dict | None:
    """Pick the next tool to call. Returns None on failure (treat as done)."""
    drug_a, drug_b = pair
    tool_list = json.dumps(TOOL_SCHEMA, indent=2)
    history_summary = json.dumps(
        [{"tool": h["tool"], "args": h.get("args", {})} for h in history], indent=2
    )

    user_msg = (
        f"Drug pair: {drug_a} / {drug_b}\n"
        f"Gaps: {json.dumps(gaps)}\n"
        f"History of calls already made:\n{history_summary}\n"
        f"Available tools:\n{tool_list}"
    )

    try:
        result = await chat_json(
            model=NANO_MODEL,
            system=_RESEARCH_AGENT_SYSTEM,
            user=user_msg,
            max_tokens=2048,
            timeout=45.0,
        )
        if "tool" not in result:
            return None
        return result
    except (LLMUnavailable, Exception) as e:
        log.debug("research_agent failed for %s/%s: %s", drug_a, drug_b, e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Per-pair orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def research_pair(
    pair: tuple[str, str],
    event_sink: asyncio.Queue | None = None,
) -> list[SourceFindings]:
    """Run the full agentic research loop for one drug pair.

    1. Initial parallel fanout (fast baseline).
    2. Quality-check agent grades sufficiency.
    3. If needs_more → research agent picks next tool → execute → repeat.
    Caps at MAX_FOLLOWUP_ROUNDS follow-up rounds.
    """
    drug_a, drug_b = pair

    def _emit(stage: str, payload: dict) -> None:
        decision = {"stage": stage, "pair": [drug_a, drug_b], "timestamp": datetime.now(timezone.utc).isoformat(), **payload}
        emit_agent_decision(decision)
        if event_sink is not None:
            event_sink.put_nowait(("agent_decision", decision))

    # Step 1: parallel fanout (reuses existing fanout_pair)
    findings: list[SourceFindings] = await fanout_pair(drug_a, drug_b)

    history: list[dict] = []

    for round_num in range(MAX_FOLLOWUP_ROUNDS):
        # Step 2: quality check
        verdict = await quality_check_agent(pair, findings)
        _emit("quality_check", {
            "verdict": verdict.get("verdict"),
            "gaps": verdict.get("gaps", []),
            "reason": verdict.get("reason", ""),
            "round": round_num,
        })

        if verdict.get("verdict") == "sufficient":
            break

        gaps = verdict.get("gaps", [])

        # Step 3: research agent picks next action
        next_call = await research_agent(pair, gaps, history, findings)

        if next_call is None or next_call.get("tool") == "done":
            _emit("research_step", {"tool": "done", "why": (next_call or {}).get("why", "agent gave up"), "round": round_num})
            break

        tool_name = next_call.get("tool", "")
        tool_args = next_call.get("args") or {}
        why = next_call.get("why", "")

        _emit("research_step", {"tool": tool_name, "args": tool_args, "why": why, "round": round_num})

        if tool_name not in TOOLS:
            log.warning("research_agent returned unknown tool %r for %s/%s", tool_name, drug_a, drug_b)
            break

        try:
            result: SourceFindings = await TOOLS[tool_name](drug_a, drug_b, **tool_args)
            findings.append(result)
            if event_sink is not None:
                event_sink.put_nowait(("source_result", {
                    "pair": [drug_a, drug_b],
                    "source": result.source,
                    "coverage": result.coverage.value,
                    "n_findings": len(result.findings),
                }))
        except Exception as e:
            log.warning("tool %r failed for %s/%s: %s", tool_name, drug_a, drug_b, e)

        history.append(next_call)
    else:
        # Loop cap reached
        _emit("loop_cap_reached", {"rounds": MAX_FOLLOWUP_ROUNDS})

    return findings
