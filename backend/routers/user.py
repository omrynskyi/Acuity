"""User-data routes — profile, regimen, and session history.

All routes require a valid PAT sent as the ``x-api-key`` header.
The PAT is validated by looking it up in the ``profiles`` table; the returned
profile row is injected into every handler via ``Depends(get_profile_from_pat)``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from backend import db
from backend.schemas import (
    InteractionRow,
    ProfileOut,
    RegimenEntry,
    SessionSummary,
)

log = logging.getLogger(__name__)
router = APIRouter()


# --------------------------------------------------------------------------- #
# Auth dependency
# --------------------------------------------------------------------------- #

async def get_profile_from_pat(x_api_key: str = Header(...)) -> dict:
    profile = await asyncio.to_thread(db.get_profile_by_pat, x_api_key)
    if not profile:
        raise HTTPException(status_code=401, detail="invalid PAT")
    return profile


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #

@router.get("/profile", response_model=ProfileOut)
async def get_profile(profile: dict = Depends(get_profile_from_pat)) -> dict:
    return profile


class ProfilePatch(dict):
    pass


from pydantic import BaseModel


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    doctor: Optional[str] = None
    doctor_email: Optional[str] = None


@router.patch("/profile", response_model=ProfileOut)
async def update_profile(
    body: ProfileUpdateRequest,
    profile: dict = Depends(get_profile_from_pat),
) -> dict:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=422, detail="no fields to update")
    try:
        updated = await asyncio.to_thread(db.update_profile_fields, profile["id"], patch)
    except Exception as e:
        log.exception("update_profile failed")
        raise HTTPException(status_code=500, detail=str(e))
    return updated


# --------------------------------------------------------------------------- #
# Regimen (active medication list)
# --------------------------------------------------------------------------- #

@router.get("/medicines", response_model=list[RegimenEntry])
async def list_medicines(profile: dict = Depends(get_profile_from_pat)) -> list:
    return await asyncio.to_thread(db.get_regimen, profile["id"])


class AddMedicineRequest(BaseModel):
    drug: str
    dose: Optional[str] = None
    frequency: Optional[str] = None


@router.post("/medicines", response_model=RegimenEntry, status_code=201)
async def add_medicine(
    body: AddMedicineRequest,
    profile: dict = Depends(get_profile_from_pat),
) -> dict:
    try:
        entry = await asyncio.to_thread(
            db.add_regimen_entry, profile["id"], body.drug, body.dose, body.frequency
        )
    except Exception as e:
        log.exception("add_medicine failed")
        raise HTTPException(status_code=500, detail=str(e))
    return entry


class UpdateMedicineRequest(BaseModel):
    dose: Optional[str] = None
    frequency: Optional[str] = None


@router.patch("/medicines/{entry_id}", response_model=RegimenEntry)
async def update_medicine(
    entry_id: str,
    body: UpdateMedicineRequest,
    profile: dict = Depends(get_profile_from_pat),
) -> dict:
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=422, detail="no fields to update")
    try:
        updated = await asyncio.to_thread(
            db.update_regimen_entry, profile["id"], entry_id, patch
        )
    except Exception as e:
        log.exception("update_medicine failed")
        raise HTTPException(status_code=500, detail=str(e))
    return updated


@router.delete("/medicines/{entry_id}", status_code=204)
async def remove_medicine(
    entry_id: str,
    profile: dict = Depends(get_profile_from_pat),
) -> None:
    try:
        await asyncio.to_thread(db.soft_delete_regimen, profile["id"], entry_id)
    except Exception as e:
        log.exception("remove_medicine failed")
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------------------------------------------------------- #
# Session / report history
# --------------------------------------------------------------------------- #

@router.get("/sessions", response_model=list[SessionSummary])
async def list_sessions(
    limit: int = 20,
    profile: dict = Depends(get_profile_from_pat),
) -> list:
    return await asyncio.to_thread(db.list_user_sessions, profile["id"], limit)


@router.get("/sessions/{session_id}", response_model=dict)
async def get_session(
    session_id: str,
    profile: dict = Depends(get_profile_from_pat),
) -> dict:
    sess = await asyncio.to_thread(db.get_user_session, profile["id"], session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    return sess


@router.get("/sessions/{session_id}/interactions", response_model=list[InteractionRow])
async def get_interactions(
    session_id: str,
    profile: dict = Depends(get_profile_from_pat),
) -> list:
    rows = await asyncio.to_thread(db.get_session_interactions, profile["id"], session_id)
    if rows is None:
        raise HTTPException(status_code=404, detail="session not found")
    return rows
