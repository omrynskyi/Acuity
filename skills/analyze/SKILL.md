---
name: analyze
description: Run a drug-interaction analysis on a list of drugs via the Acuity API and return a RegimenReport JSON.
---

## Analyze

Run Acuity's full multi-source drug-interaction pipeline for a regimen of one or more drugs.

### Prerequisites

Environment variables required:
- `ACUITY_PAT` — Personal Access Token from Acuity. Sent as the `x-api-key` header on every request.
- `ACUITY_API_BASE_URL` — API base URL (fallback: `http://localhost:8081`).

### Inputs

| Argument | Type | Required | Description |
|---|---|---|---|
| `--drugs` | JSON array of strings | Yes | Drug names (generic or brand), e.g. `'["aspirin","warfarin"]'` |
| `--session-id` | string | No | Reuse an existing session to get memory deltas |

### Outputs

Prints a `RegimenReport` JSON object to **stdout** (the `report` field from `AnalyzeResponse`). Exits 0 on success, non-zero on failure with an error message on stderr.

### Invocation

```bash
python skills/analyze/scripts/analyze.py --drugs '["aspirin","warfarin","ibuprofen"]'
python skills/analyze/scripts/analyze.py --drugs '["metformin","lisinopril"]' --session-id abc123
```

### Side Effects

- Calls `POST {ACUITY_API_BASE_URL}/api/analyze` (env var; fallback `http://localhost:8081`).
- A new session is created server-side if `--session-id` is not provided.

### Failure Modes

- Non-zero exit + stderr message if the API returns HTTP ≥ 400.
- Non-zero exit if `ACUITY_API_BASE_URL` is unreachable and the localhost fallback also fails.
- Does **not** crash if the drug list has unknown drugs — the pipeline returns `NO_DATA` coverage for unresolvable names.
