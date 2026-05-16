#!/usr/bin/env python3
"""DB write stub — pending Supabase schema finalization.

Exits 2 with a clear status so the agent can surface a helpful message.
"""

import json
import sys

print(json.dumps({
    "status": "todo",
    "reason": "Supabase schema not yet defined. DB write tools are pending a follow-on implementation session.",
    "planned_tools": ["AddMedicine", "RemoveMedicine", "SaveReport"],
}), file=sys.stderr)
sys.exit(2)
