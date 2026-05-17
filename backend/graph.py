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
    Coverage,
    NormalizedDrug,
    RegimenReport,
    SourceFindings,
    SynthesizedInteraction,
)
from backend.sources.arxiv_search import query_arxiv
from backend.sources.brave_search import query_brave
from backend.sources.rxnorm import normalize_regimen
from backend.synthesis import synthesize_pair

log = logging.getLogger(__name__)


class AcuityState(TypedDict, total=False):
    """The graph's mutable state. Frontend renders it node-by-node."""

    session_id: str
    raw_regimen: list[str]
    target_drug: str  # when set, only pairs involving this drug are checked
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
    # Deduplicate by rxcui so that e.g. "Cocaine" and "Cocaine (nasal)" — same
    # ingredient, different form — don't produce a self-pair.
    seen: dict[str, str] = {}  # rxcui-or-name → canonical key
    alias_to_key: dict[str, str] = {}
    for d in normalized:
        if not d.found:
            continue
        dedup_key = d.rxcui or (d.generic_name or d.input_name.lower())
        name_key = d.generic_name or d.input_name.lower()
        if dedup_key not in seen:
            seen[dedup_key] = name_key
        canonical_key = seen[dedup_key]
        alias_to_key[d.input_name.strip().lower()] = canonical_key
        if d.generic_name:
            alias_to_key[d.generic_name.strip().lower()] = canonical_key
        for brand in d.brand_names:
            brand_key = brand.strip().lower()
            if brand_key:
                alias_to_key[brand_key] = canonical_key
    keys = list(seen.values())
    all_pairs = list(combinations(sorted(set(keys)), 2))

    # If a target_drug is specified (e.g. adding one new drug to a regimen),
    # only check pairs that involve that drug rather than every C(n,2) pair.
    target = (state.get("target_drug") or "").strip().lower()
    if target:
        target_keys = {target}
        canonical_target = alias_to_key.get(target)
        if canonical_target:
            target_keys.add(canonical_target)
        pairs = [p for p in all_pairs if any(name in target_keys for name in p)]
    else:
        pairs = all_pairs

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
    """Split pairs into new vs cached.

    Cache is intentionally disabled for now so every run does live fanout and
    synthesis, which keeps the streaming UI active while we debug.
    """
    t0 = datetime.now(timezone.utc)
    pairs = state["pairs"]
    durations = state["durations_ms"]
    durations["memory_ms"] = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    return {
        **state,
        "new_pairs": pairs,
        "cached_pairs": [],
        "syntheses": [],
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
    findings = state["source_findings"]
    pairs = state["new_pairs"]

    new_syntheses = await asyncio.gather(
        *(synthesize_pair(p, findings.get(p, [])) for p in pairs)
    )

    durations = state["durations_ms"]
    durations["synthesis_ms"] = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

    return {
        **state,
        "syntheses": state["syntheses"] + list(new_syntheses),
        "durations_ms": durations,
    }


async def arxiv_node(state: AcuityState) -> AcuityState:
    """Search arXiv for peer-reviewed papers on each new drug pair."""
    t0 = datetime.now(timezone.utc)
    new_pairs = state["new_pairs"]
    findings: dict[tuple[str, str], list[SourceFindings]] = dict(state.get("source_findings") or {})
    if new_pairs:
        results = await asyncio.gather(
            *(query_arxiv(p[0], p[1]) for p in new_pairs),
            return_exceptions=True,
        )
        for pair, result in zip(new_pairs, results):
            if isinstance(result, SourceFindings):
                findings.setdefault(pair, []).append(result)
            else:
                log.warning("arxiv error for %s: %s", pair, result)
    durations = state["durations_ms"]
    durations["arxiv_ms"] = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    return {**state, "source_findings": findings, "durations_ms": durations}


_MIN_PAIR_FINDINGS = 3  # run extra Brave search when a pair has fewer total findings


async def _augment_sparse_pairs(
    pairs: list[tuple[str, str]],
    findings: dict[tuple[str, str], list[SourceFindings]],
) -> dict[tuple[str, str], list[SourceFindings]]:
    """For pairs with few findings across all sources, run an extra Brave search."""
    sparse = [
        p for p in pairs
        if sum(len(sf.findings) for sf in findings.get(p, [])) < _MIN_PAIR_FINDINGS
    ]
    if not sparse:
        return findings

    log.info("Running extra Brave search for %d sparse pair(s)", len(sparse))
    extra_results = await asyncio.gather(
        *(
            query_brave(
                p[0], p[1],
                query_override=f"{p[0]} {p[1]} clinical pharmacology mechanism adverse reaction",
            )
            for p in sparse
        ),
        return_exceptions=True,
    )
    findings = dict(findings)
    for pair, extra in zip(sparse, extra_results):
        if not isinstance(extra, SourceFindings) or not extra.findings:
            continue
        sf_list = list(findings.get(pair, []))
        brave_idx = next((i for i, sf in enumerate(sf_list) if sf.source == "brave_search"), None)
        if brave_idx is not None:
            orig = sf_list[brave_idx]
            merged_findings = orig.findings + extra.findings
            sf_list[brave_idx] = SourceFindings(
                source=orig.source,
                drug_pair=orig.drug_pair,
                queried_at=orig.queried_at,
                findings=merged_findings,
                coverage=Coverage.FULL,
                confidence=orig.confidence,
            )
        else:
            sf_list.append(extra)
        findings[pair] = sf_list
    return findings


async def brave_search_node(state: AcuityState) -> AcuityState:
    """Run a Brave web search for each new drug pair; augment sparse pairs."""
    t0 = datetime.now(timezone.utc)
    new_pairs = state["new_pairs"]
    findings: dict[tuple[str, str], list[SourceFindings]] = dict(state.get("source_findings") or {})
    if new_pairs:
        results = await asyncio.gather(
            *(query_brave(p[0], p[1]) for p in new_pairs),
            return_exceptions=True,
        )
        for pair, result in zip(new_pairs, results):
            if isinstance(result, SourceFindings):
                findings.setdefault(pair, []).append(result)
            else:
                log.warning("brave search error for %s: %s", pair, result)
        findings = await _augment_sparse_pairs(new_pairs, findings)
    durations = state["durations_ms"]
    durations["brave_ms"] = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)
    return {**state, "source_findings": findings, "durations_ms": durations}


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
        source_findings=state.get("source_findings"),
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
    g.add_node("arxiv", arxiv_node)
    g.add_node("brave_search", brave_search_node)
    g.add_node("synthesis", synthesis_node)
    g.add_node("report", report_node)
    g.set_entry_point("intake")
    g.add_edge("intake", "memory")
    g.add_edge("memory", "fanout")
    g.add_edge("fanout", "arxiv")
    g.add_edge("arxiv", "brave_search")
    g.add_edge("brave_search", "synthesis")
    g.add_edge("synthesis", "report")
    g.add_edge("report", END)
    return g.compile()


_GRAPH = None


def graph() -> Any:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


async def run_analysis(session_id: str, drugs: list[str], *, target_drug: str | None = None) -> AcuityState:
    """Convenience runner used by the FastAPI endpoint and tests."""
    init: AcuityState = {
        "session_id": session_id,
        "raw_regimen": drugs,
        "durations_ms": {},
    }
    if target_drug:
        init["target_drug"] = target_drug
    return await graph().ainvoke(init)


async def run_analysis_streaming(
    session_id: str,
    drugs: list[str],
    *,
    target_drug: str | None = None,
) -> AsyncGenerator[tuple[str, dict], None]:
    """Async generator that runs the pipeline and yields (event_type, payload) as each stage completes."""
    state: AcuityState = {
        "session_id": session_id,
        "raw_regimen": drugs,
        "durations_ms": {},
        "started_at": datetime.now(timezone.utc),
    }
    if target_drug:
        state["target_drug"] = target_drug

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

    # Stage 3b: arxiv — search for peer-reviewed papers per pair
    try:
        state = await arxiv_node(state)
    except Exception as e:
        yield ("error", {"detail": str(e), "stage": "arxiv"})
        return
    for pair in new_pairs:
        sf_list = state["source_findings"].get(pair, [])
        arxiv_sf = next((sf for sf in sf_list if sf.source == "arxiv"), None)
        if arxiv_sf:
            yield ("source_result", {
                "pair": list(pair),
                "source": "arxiv",
                "coverage": arxiv_sf.coverage.value,
                "n_findings": len(arxiv_sf.findings),
            })

    # Stage 3c: brave_search — web search per pair
    try:
        state = await brave_search_node(state)
    except Exception as e:
        yield ("error", {"detail": str(e), "stage": "brave_search"})
        return
    for pair in new_pairs:
        sf_list = state["source_findings"].get(pair, [])
        brave_sf = next((sf for sf in sf_list if sf.source == "brave_search"), None)
        if brave_sf:
            yield ("source_result", {
                "pair": list(pair),
                "source": "brave_search",
                "coverage": brave_sf.coverage.value,
                "n_findings": len(brave_sf.findings),
            })

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
