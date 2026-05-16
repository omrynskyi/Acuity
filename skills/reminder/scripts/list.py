#!/usr/bin/env python3
"""Reminder list — enumerate active reminders from /session/reminders/.

Usage:
    python skills/reminder/scripts/list.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REMINDERS_DIR = Path("/session/reminders")


def main() -> None:
    if not REMINDERS_DIR.exists():
        print("[]")
        return

    reminders = []
    for f in sorted(REMINDERS_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            reminders.append(json.loads(f.read_text()))
        except (json.JSONDecodeError, OSError) as e:
            print(f"WARNING: could not read {f}: {e}", file=sys.stderr)

    print(json.dumps(reminders, indent=2))


if __name__ == "__main__":
    main()
