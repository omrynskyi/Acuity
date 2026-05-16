#!/usr/bin/env python3
"""Reminder send — invoked by cron at fire time to send a Telegram message.

Usage (called by crontab):
    python skills/reminder/scripts/send.py <reminder_id>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import httpx

REMINDERS_DIR = Path("/session/reminders")
LOG_FILE = REMINDERS_DIR / "_log.jsonl"
CANCEL_SCRIPT = Path(__file__).resolve().parent / "cancel.py"


def _log(entry: dict) -> None:
    REMINDERS_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: send.py <reminder_id>", file=sys.stderr)
        sys.exit(1)

    rid = sys.argv[1]
    json_path = REMINDERS_DIR / f"{rid}.json"

    if not json_path.exists():
        _log({"ts": datetime.utcnow().isoformat(), "id": rid, "status": "missing_state"})
        sys.exit(1)

    try:
        state = json.loads(json_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        _log({"ts": datetime.utcnow().isoformat(), "id": rid, "status": "read_error", "detail": str(e)})
        sys.exit(1)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = state.get("chat_id") or os.environ.get("TELEGRAM_CHAT_ID", "")
    content = state.get("content", "")
    frequency = state.get("frequency", "once")

    if not token or not chat_id:
        _log({"ts": datetime.utcnow().isoformat(), "id": rid, "status": "missing_env"})
        sys.exit(1)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json={"chat_id": chat_id, "text": content, "parse_mode": "Markdown"})
        resp.raise_for_status()
        status = "sent"
    except Exception as e:  # noqa: BLE001
        _log({"ts": datetime.utcnow().isoformat(), "id": rid, "status": "send_error", "detail": str(e)})
        sys.exit(1)

    _log({"ts": datetime.utcnow().isoformat(), "id": rid, "status": status})

    # Self-cancel once-only reminders
    if frequency == "once":
        subprocess.run([sys.executable, str(CANCEL_SCRIPT), "--id", rid], capture_output=True)
    else:
        # Update next_fire_at for informational purposes (cron handles actual scheduling)
        state["next_fire_at"] = datetime.utcnow().isoformat()
        json_path.write_text(json.dumps(state, indent=2))


if __name__ == "__main__":
    main()
