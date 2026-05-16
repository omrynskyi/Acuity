#!/usr/bin/env python3
"""List the user's active medications (removed_at IS NULL).

Usage:
    python skills/db/scripts/list_medicines.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _client import api_get


def main() -> None:
    medicines = api_get("/api/user/medicines")
    print(json.dumps(medicines, indent=2, default=str))


if __name__ == "__main__":
    main()
