#!/usr/bin/env python3
"""Analyze skill — call Acuity's drug-interaction API and print the RegimenReport to stdout.

Modes
-----
--drug <name>      POST /api/analyze/drug   (non-streaming)
                   Check one new drug against the user's saved regimen.
--onboarding       POST /api/analyze/onboarding/stream  (SSE → collects report_done)
                   Check every pair in the saved regimen (post-onboarding full sweep).

Usage
-----
    python3 analyze.py --drug "aspirin"
    python3 analyze.py --drug "aspirin" --session-id abc123
    python3 analyze.py --onboarding
    python3 analyze.py --onboarding --session-id abc123
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

import httpx


def _load_dotenv() -> None:
    # Non-interactive bash shells (e.g. the OpenClaw exec tool's `bash -c`) do not
    # source ~/.bashrc, so interactively-exported vars are invisible there. Read
    # ~/.openclaw/.env into os.environ for any keys not already set.
    candidates = [
        pathlib.Path.home() / ".openclaw" / ".env",
        pathlib.Path("/sandbox/.openclaw/.env"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):].lstrip()
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
        break


_load_dotenv()

API_BASE = "https://acuity.onrender.com"
TIMEOUT = 120.0  # pipeline can take time on cold start
SETTINGS_URL = "https://tryacuity.vercel.app/settings"
SET_PAT_CMD = "python3 /sandbox/.openclaw/skills/auth/scripts/set_pat.py --pat <token>"


def _print_login_prompt(reason: str) -> None:
    print(
        f"NOT AUTHENTICATED: {reason}\n"
        f"  1. Generate a Personal Access Token at {SETTINGS_URL}\n"
        f"  2. Save it with: {SET_PAT_CMD}",
        file=sys.stderr,
    )


def _auth_headers() -> dict[str, str]:
    pat = os.environ.get("ACUITY_PAT", "")
    if not pat:
        _print_login_prompt("ACUITY_PAT is not set.")
        sys.exit(1)
    return {"x-api-key": pat}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Acuity drug-interaction analyze skill")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--drug", help="New drug name to check against the saved regimen")
    group.add_argument("--onboarding", action="store_true",
                       help="Check every drug pair in the saved regimen (full sweep)")
    p.add_argument("--session-id", dest="session_id", default=None,
                   help="Reuse an existing session for memory continuity")
    return p.parse_args()


def _handle_error(resp: httpx.Response, url: str) -> None:
    if resp.status_code in (401, 403):
        _print_login_prompt(f"the stored ACUITY_PAT was rejected (HTTP {resp.status_code}).")
        sys.exit(2)
    if resp.status_code >= 400:
        print(f"ERROR: API returned HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(2)


def run_drug(drug: str, session_id: str | None) -> None:
    """POST /api/analyze/drug — non-streaming single-drug check."""
    url = f"{API_BASE}/api/analyze/drug"
    payload: dict = {"drug": drug}
    if session_id:
        payload["session_id"] = session_id

    try:
        with httpx.Client(timeout=TIMEOUT, headers=_auth_headers()) as client:
            resp = client.post(url, json=payload)
    except httpx.ConnectError as e:
        print(f"ERROR: could not connect to {url}: {e}", file=sys.stderr)
        sys.exit(2)
    except httpx.HTTPError as e:
        print(f"ERROR: HTTP error calling {url}: {e}", file=sys.stderr)
        sys.exit(2)

    _handle_error(resp, url)
    body = resp.json()
    report = body.get("report", body)
    print(json.dumps(report, indent=2, default=str))


def run_onboarding(session_id: str | None) -> None:
    """POST /api/analyze/onboarding/stream — SSE, collect report_done event."""
    url = f"{API_BASE}/api/analyze/onboarding/stream"
    payload: dict = {}
    if session_id:
        payload["session_id"] = session_id

    event_type: str = ""
    report = None

    try:
        with httpx.Client(timeout=TIMEOUT, headers=_auth_headers()) as client:
            with client.stream("POST", url, json=payload) as resp:
                if resp.status_code in (401, 403):
                    _print_login_prompt(
                        f"the stored ACUITY_PAT was rejected (HTTP {resp.status_code})."
                    )
                    sys.exit(2)
                if resp.status_code >= 400:
                    body = resp.read().decode()
                    print(f"ERROR: API returned HTTP {resp.status_code}: {body}", file=sys.stderr)
                    sys.exit(2)

                for line in resp.iter_lines():
                    line = line.strip()
                    if line.startswith("event:"):
                        event_type = line[len("event:"):].strip()
                    elif line.startswith("data:"):
                        data_str = line[len("data:"):].strip()
                        if event_type == "error":
                            print(f"ERROR: server error event: {data_str}", file=sys.stderr)
                            sys.exit(2)
                        if event_type == "report_done":
                            try:
                                payload_data = json.loads(data_str)
                                report = payload_data.get("report", payload_data)
                            except json.JSONDecodeError:
                                pass
                        event_type = ""
    except httpx.ConnectError as e:
        print(f"ERROR: could not connect to {url}: {e}", file=sys.stderr)
        sys.exit(2)
    except httpx.HTTPError as e:
        print(f"ERROR: HTTP error calling {url}: {e}", file=sys.stderr)
        sys.exit(2)

    if report is None:
        print("ERROR: stream ended without a report_done event", file=sys.stderr)
        sys.exit(2)

    print(json.dumps(report, indent=2, default=str))


def main() -> None:
    args = parse_args()
    if args.onboarding:
        run_onboarding(args.session_id)
    else:
        run_drug(args.drug, args.session_id)


if __name__ == "__main__":
    main()
