"""RxNorm normalization (BE-04).

Free, no auth. Brand → ingredient resolved via a chained call when the
initial lookup returns a non-ingredient TTY. Returns the locked
`NormalizedDrug` schema.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

import httpx

from backend.schemas import NormalizedDrug

log = logging.getLogger(__name__)

RXNORM_BASE = "https://rxnav.nlm.nih.gov/REST"
_TIMEOUT = httpx.Timeout(8.0, connect=4.0)

_FORM_SUFFIX_RE = re.compile(r"\s*\([^)]*\)")

# Extended-release / pack-size tokens often appended to brand names that RxNorm
# doesn't index. Strip these and retry when the full name returns no match.
_ER_TOKENS_RE = re.compile(
    r"\b(xr|er|sr|xl|cr|cd|la|ir|dr|ec|fc|28\s*day|21\s*day)\b",
    re.IGNORECASE,
)


async def _lookup_rxcui(client: httpx.AsyncClient, name: str) -> Optional[str]:
    """First-pass RxCUI lookup. Returns None when nothing matches."""
    r = await client.get(f"{RXNORM_BASE}/rxcui.json", params={"name": name})
    r.raise_for_status()
    ids = r.json().get("idGroup", {}).get("rxnormId") or []
    return ids[0] if ids else None


async def _get_properties(client: httpx.AsyncClient, rxcui: str) -> Optional[dict]:
    r = await client.get(f"{RXNORM_BASE}/rxcui/{rxcui}/properties.json")
    r.raise_for_status()
    return r.json().get("properties")


async def _ingredient_of(client: httpx.AsyncClient, rxcui: str) -> Optional[dict]:
    """For a non-ingredient RxCUI (brand, multi-ingredient, etc.), follow the
    chain to its primary ingredient (TTY=IN)."""
    r = await client.get(f"{RXNORM_BASE}/rxcui/{rxcui}/related.json", params={"tty": "IN"})
    r.raise_for_status()
    groups = r.json().get("relatedGroup", {}).get("conceptGroup") or []
    for g in groups:
        if g.get("tty") == "IN" and g.get("conceptProperties"):
            return g["conceptProperties"][0]
    return None


async def _brand_names_for(client: httpx.AsyncClient, ingredient_rxcui: str) -> list[str]:
    """List of brand names for an ingredient. Best-effort; empty on error."""
    try:
        r = await client.get(
            f"{RXNORM_BASE}/rxcui/{ingredient_rxcui}/related.json", params={"tty": "BN"}
        )
        r.raise_for_status()
        groups = r.json().get("relatedGroup", {}).get("conceptGroup") or []
        for g in groups:
            if g.get("tty") == "BN":
                names = [c.get("name") for c in g.get("conceptProperties") or [] if c.get("name")]
                # Cap to keep payload manageable.
                return sorted(set(names))[:8]
    except httpx.HTTPError as e:
        log.warning("rxnorm BN lookup failed for %s: %s", ingredient_rxcui, e)
    return []


async def normalize_drug(name: str, *, client: Optional[httpx.AsyncClient] = None) -> NormalizedDrug:
    """Free-text drug name → NormalizedDrug.

    Always returns a NormalizedDrug — `found=False` indicates the input did
    not resolve in RxNorm. Source agents handle this gracefully (coverage=no_data).
    """
    name_clean = (name or "").strip()
    if not name_clean:
        return NormalizedDrug(input_name=name, found=False)

    # Strip dosage-form parentheticals like "(Oral Pill)", "(Tablet)" before querying
    name_query = _FORM_SUFFIX_RE.sub("", name_clean).strip() or name_clean

    owned_client = client is None
    if owned_client:
        client = httpx.AsyncClient(timeout=_TIMEOUT)

    try:
        try:
            rxcui = await _lookup_rxcui(client, name_query)
            if not rxcui:
                # Retry after stripping ER/XR/pack-size tokens (e.g. "Mucinex XR" → "Mucinex")
                stripped = _ER_TOKENS_RE.sub("", name_query).strip()
                if stripped and stripped.lower() != name_query.lower():
                    rxcui = await _lookup_rxcui(client, stripped)
                    if rxcui:
                        log.info("rxnorm fallback resolved %r via stripped name %r", name_clean, stripped)
        except httpx.HTTPError as e:
            log.warning("rxnorm lookup failed for %r: %s", name_clean, e)
            return NormalizedDrug(input_name=name, found=False)

        if not rxcui:
            return NormalizedDrug(input_name=name, found=False)

        props = await _get_properties(client, rxcui)
        if props and props.get("tty") == "IN":
            ingredient = props
        else:
            ingredient = await _ingredient_of(client, rxcui) or props or {}

        ingredient_rxcui = ingredient.get("rxcui")
        generic = (ingredient.get("name") or "").lower() or None

        brands = []
        if ingredient_rxcui:
            brands = await _brand_names_for(client, ingredient_rxcui)

        return NormalizedDrug(
            input_name=name,
            rxcui=ingredient_rxcui or rxcui,
            generic_name=generic,
            brand_names=brands,
            found=bool(ingredient_rxcui or rxcui),
        )
    finally:
        if owned_client:
            await client.aclose()


async def normalize_regimen(names: list[str]) -> list[NormalizedDrug]:
    """Normalize a list of drug names concurrently."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        return await asyncio.gather(*[normalize_drug(n, client=client) for n in names])
