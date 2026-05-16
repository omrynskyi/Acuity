#!/usr/bin/env python3
"""DB read stub — pending Supabase schema finalization.

Exits 2 with a clear status so the agent can surface a helpful message.
"""

import json
import sys

print(json.dumps({
    "status": "todo",
    "reason": "Supabase schema not yet defined. DB read tools are pending a follow-on implementation session.",
    "planned_tools": ["GetActiveMedicineList", "ListReports"],
}), file=sys.stderr)
sys.exit(2)
