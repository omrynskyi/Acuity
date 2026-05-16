#!/usr/bin/env python3
"""Update one or more fields on the user's profile.

Usage:
    python skills/db/scripts/update_profile.py --name "Jane Doe" --age 45
    python skills/db/scripts/update_profile.py --doctor "Dr. Smith" --doctor-email "smith@clinic.com"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _client import api_patch


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Update Acuity user profile")
    p.add_argument("--name", default=None)
    p.add_argument("--age", type=int, default=None)
    p.add_argument("--sex", default=None)
    p.add_argument("--height", default=None)
    p.add_argument("--weight", default=None)
    p.add_argument("--doctor", default=None)
    p.add_argument("--doctor-email", dest="doctor_email", default=None)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    patch = {k: v for k, v in vars(args).items() if v is not None}
    if not patch:
        print("ERROR: provide at least one field to update", file=sys.stderr)
        sys.exit(1)
    updated = api_patch("/api/user/profile", patch)
    print(json.dumps(updated, indent=2, default=str))


if __name__ == "__main__":
    main()
