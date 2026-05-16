"""Supabase persistence layer.

The backend owns all writes; the frontend reads directly via the anon key.
store_session() is designed to be called as asyncio.create_task() so it never
blocks the API response.
"""

from __future__ import annotations

import asyncio
import logging
import os
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
