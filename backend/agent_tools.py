"""Tool registry for the autonomous research agent.

Each entry wraps an existing source function so the LLM can pick tools by
name and pass arguments as JSON. No source files are modified.
"""

from __future__ import annotations

from typing import Any

from backend.schemas import SourceFindings
from backend.sources.arxiv_search import query_arxiv
from backend.sources.brave_search import query_brave
from backend.sources.openfda_faers import query_faers
from backend.sources.openfda_label import query_openfda_label
from backend.sources.twosides import query_twosides


async def _tavily_search(drug_a: str, drug_b: str, query: str | None = None) -> SourceFindings:
    return await query_brave(drug_a, drug_b, query_override=query)


async def _arxiv_search(drug_a: str, drug_b: str, query: str | None = None) -> SourceFindings:
    # query_arxiv doesn't accept query_override; pass generic names as-is.
    # If custom terms provided, use them as the drug name slots for the title search.
    if query:
        parts = query.split()
        a = parts[0] if parts else drug_a
        b = parts[1] if len(parts) > 1 else drug_b
        return await query_arxiv(a, b)
    return await query_arxiv(drug_a, drug_b)


async def _fda_label(drug_a: str, drug_b: str, drug: str | None = None) -> SourceFindings:
    a = drug or drug_a
    return await query_openfda_label(a, drug_b)


async def _faers_events(drug_a: str, drug_b: str, **_: Any) -> SourceFindings:
    return await query_faers(drug_a, drug_b)


async def _twosides_lookup(drug_a: str, drug_b: str, **_: Any) -> SourceFindings:
    return await query_twosides(drug_a, drug_b)


# Tool registry: name → async callable(drug_a, drug_b, **kwargs) → SourceFindings
TOOLS: dict[str, Any] = {
    "tavily_search": _tavily_search,
    "arxiv_search": _arxiv_search,
    "fda_label": _fda_label,
    "faers_events": _faers_events,
    "twosides_lookup": _twosides_lookup,
}

# Human-readable schema shown to the research agent LLM.
TOOL_SCHEMA: list[dict] = [
    {
        "name": "tavily_search",
        "description": "Web search for clinical articles and drug interaction evidence.",
        "args": {"query": "str — custom search query, e.g. 'warfarin sertraline bleeding risk'"},
    },
    {
        "name": "arxiv_search",
        "description": "Search peer-reviewed papers on arXiv for drug interaction studies.",
        "args": {"query": "str — e.g. 'ibuprofen sertraline serotonin'"},
    },
    {
        "name": "fda_label",
        "description": "Pull the FDA prescribing label for a specific drug to find interaction warnings.",
        "args": {"drug": "str — generic ingredient name, e.g. 'warfarin'"},
    },
    {
        "name": "faers_events",
        "description": "Query the FDA Adverse Event Reporting System for co-reported adverse events.",
        "args": {},
    },
    {
        "name": "twosides_lookup",
        "description": "Look up known polypharmacy side effects in the TWOSIDES/Decagon database.",
        "args": {},
    },
]
