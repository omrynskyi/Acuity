"""Supabase persistence layer.

The backend owns all writes; the frontend reads directly via the anon key.
store_session() is designed to be called as asyncio.create_task() so it never
blocks the API response.
"""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from supabase import Client, create_client

log = logging.getLogger(__name__)

_SEVERITY_RANK = {"contraindicated": 0, "major": 1, "moderate": 2, "minor": 3, "no_concern": 4}


@lru_cache(maxsize=1)
def _client() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_KEY"],
    )


def _get_demo_profile_id() -> str:
    res = _client().table("profiles").select("id").limit(1).single().execute()
    return res.data["id"]


# Cache after first lookup
_profile_id: str | None = None


def _ensure_profile_id() -> str:
    global _profile_id
    if _profile_id is None:
        _profile_id = _get_demo_profile_id()
    return _profile_id


def _do_store(session_id: str, new_drug: str, drugs_checked: list[str], report_dict: dict, profile_id: str | None = None) -> None:
    sb = _client()
    profile_id = profile_id or _ensure_profile_id()

    interactions = report_dict.get("interactions", [])
    worst = min(interactions, key=lambda ix: _SEVERITY_RANK.get(ix["severity"], 99), default=None)
    overall_severity = worst["severity"] if worst else "no_concern"

    sb.table("sessions").upsert(
        {
            "id": session_id,
            "profile_id": profile_id,
            "new_drug": new_drug,
            "drugs_checked": drugs_checked,
            "report": report_dict,
            "overall_severity": overall_severity,
            "generated_at": report_dict["generated_at"],
        },
        on_conflict="id",
    ).execute()

    if interactions:
        sb.table("interactions").delete().eq("session_id", session_id).execute()
        rows = [
            {
                "session_id": session_id,
                "drug_a": ix["drug_pair"][0],
                "drug_b": ix["drug_pair"][1],
                "severity": ix["severity"],
                "headline": ix["headline"],
                "reasoning": ix.get("reasoning"),
                "sources_agreement": ix.get("sources_agreement", "no_data"),
                "predicted_but_unverified": ix.get("predicted_but_unverified", False),
                "citations": ix.get("citations", []),
                "sort_order": i,
            }
            for i, ix in enumerate(interactions)
        ]
        sb.table("interactions").insert(rows).execute()


def get_regimen_for_profile(profile_id: str) -> list[dict]:
    """Return active (not removed) regimen rows for a profile, ordered by sort_order."""
    res = (
        _client()
        .table("regimen")
        .select("*")
        .eq("profile_id", profile_id)
        .is_("removed_at", "null")
        .order("sort_order")
        .execute()
    )
    return res.data or []


def get_profile_by_user_id(user_id: str) -> dict | None:
    res = _client().table("profiles").select("*").eq("user_id", user_id).maybe_single().execute()
    return res.data


def get_profile_by_pat(token: str) -> dict | None:
    res = _client().table("profiles").select("*").eq("pat", token).maybe_single().execute()
    return res.data


def generate_pat_for_user(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    _client().table("profiles").update({"pat": token}).eq("user_id", user_id).execute()
    return token


def create_profile(user_id: str, name: str, age: int, sex: str, height: str, weight: str) -> dict:
    """Create a profile row using the service role key (bypasses RLS)."""
    res = _client().table("profiles").insert({
        "user_id": user_id,
        "name": name,
        "age": age,
        "sex": sex or None,
        "height": height or None,
        "weight": weight or None,
        "doctor": "",
        "doctor_email": "",
    }).execute()
    return res.data[0]


def _do_cache_synthesis(
    pair_key: str,
    drug_a: str,
    drug_b: str,
    synthesis_dict: dict,
    ttl_days: int | None,
) -> None:
    expires_at = (
        (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
        if ttl_days is not None
        else None
    )
    _client().table("interaction_cache").upsert(
        {
            "pair_key": pair_key,
            "drug_a": drug_a,
            "drug_b": drug_b,
            "synthesis": synthesis_dict,
            "expires_at": expires_at,
        },
        on_conflict="pair_key",
    ).execute()


async def cache_synthesis(
    pair_key: str,
    drug_a: str,
    drug_b: str,
    synthesis_dict: dict,
    ttl_days: int | None = None,
) -> None:
    """Persist a synthesized interaction. Fire-and-forget via asyncio.create_task()."""
    try:
        await asyncio.to_thread(_do_cache_synthesis, pair_key, drug_a, drug_b, synthesis_dict, ttl_days)
    except Exception:
        log.exception("interaction_cache write failed — result still returned to client")


async def get_cached_syntheses_batch(pair_keys: list[str]) -> dict[str, dict]:
    """Batch-fetch cached syntheses by pair key. Returns {pair_key: synthesis_dict}."""
    if not pair_keys:
        return {}
    try:
        return await asyncio.to_thread(_do_get_cached_syntheses_simple, pair_keys)
    except Exception:
        log.exception("interaction_cache read failed — treating all pairs as uncached")
        return {}


def _do_get_cached_syntheses_simple(pair_keys: list[str]) -> dict[str, dict]:
    res = (
        _client()
        .table("interaction_cache")
        .select("pair_key, synthesis")
        .in_("pair_key", pair_keys)
        .execute()
    )
    result: dict[str, dict] = {}
    for row in res.data or []:
        result[row["pair_key"]] = row["synthesis"]
    return result


async def store_session(
    session_id: str,
    new_drug: str,
    drugs_checked: list[str],
    report_dict: dict,
    profile_id: str | None = None,
) -> None:
    """Persist a completed analysis. Fire-and-forget via asyncio.create_task()."""
    try:
        await asyncio.to_thread(_do_store, session_id, new_drug, drugs_checked, report_dict, profile_id)
    except Exception:
        log.exception("Supabase store_session failed — analysis result still returned to client")
