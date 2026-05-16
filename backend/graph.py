"""LangGraph orchestration (BE-11).

Pipeline:
    intake → fanout (parallel per pair × source) → synthesis (per pair) → report

LangGraph here is the orchestration shell — the actual concurrency for the
fan-out lives in `backend.fanout.fanout_pairs` (asyncio.gather under a
semaphore). LangGraph's per-node graph state makes the pipeline easy to
inspect from the frontend and trivial to add new nodes to (e.g. an attack
detector before the network calls).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from itertools import combinations
from typing import Any, AsyncGenerator, TypedDict

from langgraph.graph import END, StateGraph

from backend.fanout import fanout_pairs
from backend.memory import memory_for
from backend.report import build_report
from backend.schemas import (
    NormalizedDrug,
    RegimenReport,
    SourceFindings,
    SynthesizedInteraction,
)
from backend.sources.rxnorm import normalize_regimen
from backend.synthesis import synthesize_pair

log = logging.getLogger(__name__)


class AcuityState(TypedDict, total=False):
    """The graph's mutable state. Frontend renders it node-by-node."""

    session_id: str
    raw_regimen: list[str]
    regimen: list[NormalizedDrug]
    pairs: list[tuple[str, str]]
    new_pairs: list[tuple[str, str]]
    cached_pairs: list[tuple[str, str]]
    source_findings: dict[tuple[str, str], list[SourceFindings]]
    syntheses: list[SynthesizedInteraction]
    report: RegimenReport
    started_at: datetime
    durations_ms: dict[str, int]


# --------------------------------------------------------------------------- #
# Nodes
# --------------------------------------------------------------------------- #

async def intake_node(state: AcuityState) -> AcuityState:
    """Normalize free-text drug names and generate the pair list."""
    t0 = datetime.now(timezone.utc)
    raw = state.get("raw_regimen") or []
    normalized = await normalize_regimen(raw)

    # Build pairs over recognised drugs only; unknown ones are surfaced in
    # the regimen list but excluded from interaction checks.
    keys = [d.generic_name or d.input_name.lower() for d in normalized if d.found]
    pairs = list(combinations(sorted(set(keys)), 2))

    durations = state.get("durations_ms") or {}
    durations["intake_ms"] = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    return {
        **state,
        "regimen": normalized,
        "pairs": pairs,
        "started_at": state.get("started_at") or t0,
        "durations_ms": durations,
    }


async def memory_node(state: AcuityState) -> AcuityState:
    """Split pairs into new vs cached via the per-session memory store."""
    t0 = datetime.now(timezone.utc)
    mem = memory_for(state["session_id"])
    pairs = state["pairs"]
    new_pairs, cached_pairs, cached_syntheses = mem.partition(pairs)
    durations = state["durations_ms"]
    durations["memory_ms"] = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    return {
        **state,
        "new_pairs": new_pairs,
        "cached_pairs": cached_pairs,
        "syntheses": list(cached_syntheses),
        "durations_ms": durations,
    }


async def fanout_node(state: AcuityState) -> AcuityState:
    """Run the three source agents for each new pair, in parallel."""
    t0 = datetime.now(timezone.utc)
    new_pairs = state["new_pairs"]
    if new_pairs:
        findings = await fanout_pairs(new_pairs, concurrency=4)
    else:
        findings = {}
    durations = state["durations_ms"]
    durations["fanout_ms"] = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    return {**state, "source_findings": findings, "durations_ms": durations}


async def synthesis_node(state: AcuityState) -> AcuityState:
    """Synthesize per-pair verdicts. Parallel across pairs."""
    t0 = datetime.now(timezone.utc)
    mem = memory_for(state["session_id"])
    findings = state["source_findings"]
    pairs = state["new_pairs"]

    new_syntheses = await asyncio.gather(
        *(synthesize_pair(p, findings.get(p, [])) for p in pairs)
    )
    mem.store_many(new_syntheses)

    durations = state["durations_ms"]
    durations["synthesis_ms"] = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

    return {
        **state,
        "syntheses": state["syntheses"] + list(new_syntheses),
        "durations_ms": durations,
    }


async def report_node(state: AcuityState) -> AcuityState:
    """Aggregate into a RegimenReport."""
    t0 = datetime.now(timezone.utc)
    mem = memory_for(state["session_id"])
    # Persist the regimen so follow-up queries can compute deltas.
    mem.set_regimen(state["regimen"])

    report = await build_report(
        regimen=state["regimen"],
        pair_results=state["syntheses"],
        new_pairs=state["new_pairs"],
        cached_pairs=state["cached_pairs"],
    )
    durations = state["durations_ms"]
    durations["report_ms"] = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    durations["total_ms"] = int(
        (datetime.now(timezone.utc) - state["started_at"]).total_seconds() * 1000
    )
    return {**state, "report": report, "durations_ms": durations}


# --------------------------------------------------------------------------- #
# Graph factory
# --------------------------------------------------------------------------- #

def build_graph() -> Any:
    """Build and compile the Acuity graph. Cached at module load by caller."""
    g = StateGraph(AcuityState)
    g.add_node("intake", intake_node)
    g.add_node("memory", memory_node)
    g.add_node("fanout", fanout_node)
    g.add_node("synthesis", synthesis_node)
    g.add_node("report", report_node)
    g.set_entry_point("intake")
    g.add_edge("intake", "memory")
    g.add_edge("memory", "fanout")
    g.add_edge("fanout", "synthesis")
    g.add_edge("synthesis", "report")
    g.add_edge("report", END)
    return g.compile()


_GRAPH = None


def graph() -> Any:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


async def run_analysis(session_id: str, drugs: list[str]) -> AcuityState:
    """Convenience runner used by the FastAPI endpoint and tests."""
    init: AcuityState = {
        "session_id": session_id,
        "raw_regimen": drugs,
        "durations_ms": {},
    }
    return await graph().ainvoke(init)


async def run_analysis_streaming(
    session_id: str,
    drugs: list[str],
) -> AsyncGenerator[tuple[str, dict], None]:
    """Async generator that runs the pipeline and yields (event_type, payload) as each stage completes."""
    state: AcuityState = {
        "session_id": session_id,
        "raw_regimen": drugs,
        "durations_ms": {},
        "started_at": datetime.now(timezone.utc),
    }

    # Stage 1: intake
    try:
        state = await intake_node(state)
    except Exception as e:
        yield ("error", {"detail": str(e), "stage": "intake"})
        return
    yield ("intake_done", {
        "regimen": [d.model_dump() for d in state["regimen"]],
        "pairs": [list(p) for p in state["pairs"]],
        "duration_ms": state["durations_ms"].get("intake_ms"),
    })

    # Stage 2: memory
    try:
        state = await memory_node(state)
    except Exception as e:
        yield ("error", {"detail": str(e), "stage": "memory"})
        return
    yield ("memory_result", {
        "total_pairs": len(state["pairs"]),
        "new_pairs": [list(p) for p in state["new_pairs"]],
        "cached_pairs": [list(p) for p in state["cached_pairs"]],
        "duration_ms": state["durations_ms"].get("memory_ms"),
    })

    # Emit cached syntheses immediately so the frontend can update right away
    for synth in state.get("syntheses", []):
        yield ("synthesis_result", {**synth.model_dump(), "cached": True, "duration_ms": 0})

    # Stage 3: fanout — stream per-source events as each agent completes
    new_pairs = state.get("new_pairs", [])
    try:
        if new_pairs:
            fanout_queue: asyncio.Queue = asyncio.Queue()
            fanout_task = asyncio.create_task(
                fanout_pairs(new_pairs, concurrency=4, event_sink=fanout_queue)
            )
            expected_events = len(new_pairs) * 3  # 3 sources per pair
            for _ in range(expected_events):
                ev_type, payload = await fanout_queue.get()
                yield (ev_type, payload)
            findings = await fanout_task
        else:
            findings = {}
    except Exception as e:
        yield ("error", {"detail": str(e), "stage": "fanout"})
        return

    durations = state["durations_ms"]
    state = {**state, "source_findings": findings, "durations_ms": durations}

    # Stage 4: synthesis — run all pairs in parallel, yield each result as it finishes
    if new_pairs:
        findings = state["source_findings"]
        queue: asyncio.Queue = asyncio.Queue()
        new_syntheses: list[SynthesizedInteraction] = []

        async def _run_pair(pair: tuple[str, str]) -> None:
            try:
                t0 = datetime.now(timezone.utc)
                result = await synthesize_pair(pair, findings.get(pair, []))
                ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
                await queue.put((pair, result, ms, None))
            except Exception as exc:
                await queue.put((pair, None, 0, exc))

        tasks = [asyncio.create_task(_run_pair(p)) for p in new_pairs]
        t_synth = datetime.now(timezone.utc)
        for _ in range(len(tasks)):
            pair, synth, ms, err = await queue.get()
            if err:
                yield ("error", {"detail": str(err), "stage": "synthesis", "pair": list(pair)})
            else:
                new_syntheses.append(synth)
                yield ("synthesis_result", {**synth.model_dump(), "cached": False, "duration_ms": ms})
        await asyncio.gather(*tasks, return_exceptions=True)

        mem = memory_for(session_id)
        mem.store_many(new_syntheses)
        durations = state["durations_ms"]
        durations["synthesis_ms"] = int((datetime.now(timezone.utc) - t_synth).total_seconds() * 1000)
        state = {**state, "syntheses": state.get("syntheses", []) + new_syntheses, "durations_ms": durations}

    # Stage 5: report
    try:
        state = await report_node(state)
    except Exception as e:
        yield ("error", {"detail": str(e), "stage": "report"})
        return
    yield ("report_done", {
        "session_id": session_id,
        "report": state["report"].model_dump(),
        "durations_ms": state["durations_ms"],
    })
