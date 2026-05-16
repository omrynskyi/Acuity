"""Parallel fan-out across the core source agents (BE-11 prep).

Pulled out of `langgraph_app.py` so it can be unit-tested and reused by the
synthesis tests without spinning up the whole graph.
"""

from __future__ import annotations

import asyncio
from typing import Iterable

import httpx

from backend.schemas import SourceFindings
from backend.sources.openfda_faers import query_faers
from backend.sources.openfda_label import query_openfda_label
from backend.sources.twosides import query_twosides


async def fanout_pair(
    drug_a: str,
    drug_b: str,
    *,
    client: httpx.AsyncClient | None = None,
    event_sink: asyncio.Queue | None = None,
) -> list[SourceFindings]:
    """Run the core source agents concurrently for one drug pair."""
    owned = client is None
    if owned:
        client = httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=4.0))

    async def _run_source(name: str, coro) -> SourceFindings:
        result = await coro
        if event_sink is not None:
            await event_sink.put(("source_result", {
                "pair": [drug_a, drug_b],
                "source": name,
                "coverage": result.coverage.value,
                "n_findings": len(result.findings),
            }))
        return result

    try:
        results = await asyncio.gather(
            _run_source("openfda_label", query_openfda_label(drug_a, drug_b, client=client)),
            _run_source("openfda_faers", query_faers(drug_a, drug_b, client=client)),
            _run_source("decagon", query_twosides(drug_a, drug_b)),
            return_exceptions=False,
        )
        return list(results)
    finally:
        if owned:
            await client.aclose()


async def fanout_pairs(
    pairs: Iterable[tuple[str, str]],
    *,
    concurrency: int = 4,
    event_sink: asyncio.Queue | None = None,
) -> dict[tuple[str, str], list[SourceFindings]]:
    """Run fan-out for multiple pairs with a concurrency cap.

    The cap keeps us under OpenFDA's 240 req/min unauth limit on a 6-drug
    (15-pair) regimen: 15 pairs × 3 sources × 2 calls ≈ 90 outbound, which is
    fine in one minute but bursts can trigger 429s.
    """
    sem = asyncio.Semaphore(concurrency)
    out: dict[tuple[str, str], list[SourceFindings]] = {}

    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=4.0)) as client:
        async def run(pair: tuple[str, str]) -> None:
            async with sem:
                out[pair] = await fanout_pair(pair[0], pair[1], client=client, event_sink=event_sink)

        await asyncio.gather(*(run(p) for p in pairs))
    return out
