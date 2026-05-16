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


# --------------------------------------------------------------------------- #
# User-data queries (called by backend/routers/user.py)
# All queries are scoped by profile_id — no user can see another user's rows.
# --------------------------------------------------------------------------- #

def update_profile_fields(profile_id: str, patch: dict) -> dict:
    res = _client().table("profiles").update(patch).eq("id", profile_id).execute()
    return res.data[0]


def get_regimen(profile_id: str) -> list[dict]:
    res = (
        _client().table("regimen")
        .select("*")
        .eq("profile_id", profile_id)
        .is_("removed_at", "null")
        .order("sort_order")
        .execute()
    )
    return res.data


def add_regimen_entry(profile_id: str, drug: str, dose: str | None, frequency: str | None) -> dict:
    res = _client().table("regimen").insert({
        "profile_id": profile_id,
        "input_name": drug,
        "dose": dose,
        "frequency": frequency,
        "found": False,
        "brand_names": [],
    }).execute()
    return res.data[0]


def soft_delete_regimen(profile_id: str, entry_id: str) -> None:
    from datetime import datetime, timezone
    _client().table("regimen").update(
        {"removed_at": datetime.now(timezone.utc).isoformat()}
    ).eq("id", entry_id).eq("profile_id", profile_id).execute()


def update_regimen_entry(profile_id: str, entry_id: str, patch: dict) -> dict:
    res = (
        _client().table("regimen")
        .update(patch)
        .eq("id", entry_id)
        .eq("profile_id", profile_id)
        .execute()
    )
    return res.data[0]


def list_user_sessions(profile_id: str, limit: int = 20) -> list[dict]:
    res = (
        _client().table("sessions")
        .select("id,new_drug,drugs_checked,overall_severity,generated_at,created_at")
        .eq("profile_id", profile_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


def get_user_session(profile_id: str, session_id: str) -> dict | None:
    res = (
        _client().table("sessions")
        .select("*")
        .eq("id", session_id)
        .eq("profile_id", profile_id)
        .maybe_single()
        .execute()
    )
    return res.data


def get_session_interactions(profile_id: str, session_id: str) -> list[dict]:
    sess = get_user_session(profile_id, session_id)
    if not sess:
        return []
    res = (
        _client().table("interactions")
        .select("*")
        .eq("session_id", session_id)
        .order("sort_order")
        .execute()
    )
    return res.data


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
