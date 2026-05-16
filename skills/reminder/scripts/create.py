#!/usr/bin/env python3
"""Reminder create — schedule a Telegram reminder via system crontab.

Usage:
    python skills/reminder/scripts/create.py \
        --date "2026-05-17T09:00:00" \
        --frequency daily \
        --content "Take your metformin"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

REMINDERS_DIR = Path("/session/reminders")
SEND_SCRIPT = Path(__file__).resolve().parent / "send.py"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create a NemoClaw-isolated Telegram reminder")
    p.add_argument("--date", required=True, help="ISO 8601 first-fire datetime, e.g. 2026-05-17T09:00:00")
    p.add_argument("--frequency", required=True, choices=["once", "daily", "weekly", "monthly"])
    p.add_argument("--content", required=True, help="Message text to send")
    return p.parse_args()


def _cron_expr(dt: datetime, frequency: str) -> str:
    """Build a crontab expression for the given datetime and frequency."""
    minute = dt.minute
    hour = dt.hour
    day = dt.day
    month = dt.month
    weekday = dt.weekday()  # 0=Monday
    # cron weekday: 0=Sunday, so shift
    cron_weekday = (weekday + 1) % 7

    if frequency == "once":
        return f"{minute} {hour} {day} {month} *"
    elif frequency == "daily":
        return f"{minute} {hour} * * *"
    elif frequency == "weekly":
        return f"{minute} {hour} * * {cron_weekday}"
    elif frequency == "monthly":
        return f"{minute} {hour} {day} * *"
    else:
        raise ValueError(f"Unknown frequency: {frequency}")


def _get_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout
    # crontab -l exits 1 when no crontab exists — that's fine
    if "no crontab" in result.stderr.lower() or result.returncode == 1:
        return ""
    raise RuntimeError(f"crontab -l failed: {result.stderr.strip()}")


def _set_crontab(content: str) -> None:
    result = subprocess.run(["crontab", "-"], input=content, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"crontab write failed: {result.stderr.strip()}")


def main() -> None:
    args = parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        print("ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set", file=sys.stderr)
        sys.exit(1)

    try:
        fire_at = datetime.fromisoformat(args.date)
    except ValueError as e:
        print(f"ERROR: invalid --date '{args.date}': {e}", file=sys.stderr)
        sys.exit(1)

    reminder_id = str(uuid.uuid4())
    REMINDERS_DIR.mkdir(parents=True, exist_ok=True)

    state = {
        "id": reminder_id,
        "created_at": datetime.utcnow().isoformat(),
        "next_fire_at": fire_at.isoformat(),
        "frequency": args.frequency,
        "content": args.content,
        "chat_id": chat_id,
    }
    (REMINDERS_DIR / f"{reminder_id}.json").write_text(json.dumps(state, indent=2))

    try:
        cron_expr = _cron_expr(fire_at, args.frequency)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    cron_line = f"{cron_expr} python {SEND_SCRIPT} {reminder_id}"

    try:
        existing = _get_crontab()
        new_crontab = existing.rstrip("\n") + f"\n{cron_line}\n"
        _set_crontab(new_crontab)
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(reminder_id)


if __name__ == "__main__":
    main()
