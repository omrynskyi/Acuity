#!/usr/bin/env python3
"""Get the user's profile (name, age, sex, height, weight, doctor).

Usage:
    python skills/db/scripts/get_profile.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _client import api_get


def main() -> None:
    profile = api_get("/api/user/profile")
    print(json.dumps(profile, indent=2, default=str))


if __name__ == "__main__":
    main()
