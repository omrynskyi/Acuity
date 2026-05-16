#!/usr/bin/env python3
"""Reminder cancel — remove crontab entry and delete reminder JSON.

Usage:
    python skills/reminder/scripts/cancel.py --id <reminder_id>
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REMINDERS_DIR = Path("/session/reminders")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Cancel a reminder")
    p.add_argument("--id", dest="reminder_id", required=True, help="Reminder ID to cancel")
    return p.parse_args()


def _get_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout
    if "no crontab" in result.stderr.lower() or result.returncode == 1:
        return ""
    raise RuntimeError(f"crontab -l failed: {result.stderr.strip()}")


def _set_crontab(content: str) -> None:
    result = subprocess.run(["crontab", "-"], input=content, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"crontab write failed: {result.stderr.strip()}")


def main() -> None:
    args = parse_args()
    rid = args.reminder_id

    json_path = REMINDERS_DIR / f"{rid}.json"
    if not json_path.exists():
        print(f"ERROR: reminder {rid} not found at {json_path}", file=sys.stderr)
        sys.exit(1)

    # Remove crontab line containing this reminder id
    try:
        existing = _get_crontab()
        filtered = "\n".join(line for line in existing.splitlines() if rid not in line)
        if not filtered.strip():
            # Remove crontab entirely rather than leaving empty file
            subprocess.run(["crontab", "-r"], capture_output=True)
        else:
            _set_crontab(filtered + "\n")
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    json_path.unlink()
    print(f"cancelled {rid}")


if __name__ == "__main__":
    main()
