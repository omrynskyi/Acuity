---
name: db
description: "TODO: Read and write the user's active medication list in Supabase. Tools are stubbed pending schema finalization."
status: todo
---

## DB Read / Write (TODO)

These tools will enable the NemoClaw agent to manage a user's active medication list stored in Supabase. They are **not yet implemented** — the Supabase schema has not been finalized.

### Planned Tools

| Tool | Script | Description |
|---|---|---|
| `GetActiveMedicineList` | `db_read.py` | Return the user's current active medications |
| `AddMedicine` | `db_write.py add` | Add a medication to the active list |
| `RemoveMedicine` | `db_write.py remove` | Remove a medication from the active list |
| `ListReports` | `db_read.py reports` | List saved analysis reports for this user |
| `SaveReport` | `db_write.py save-report` | Persist a `RegimenReport` to Supabase |

### Current Status

Calling either script exits **2** with a clear status message. The agent should surface this as "medication list tools are not yet available" and suggest the user run `Analyze` instead.

### Prerequisites (future)

Environment variables that will be required:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

### Invocation (future)

```bash
python skills/db/scripts/db_read.py
python skills/db/scripts/db_write.py add --drug "metformin" --dose "500mg" --frequency "twice daily"
```
