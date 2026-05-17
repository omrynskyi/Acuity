---
name: analyze
description: Run a drug-interaction analysis via the Acuity API and return a RegimenReport JSON. Supports single-drug check against the saved regimen and full onboarding sweep.
---

## Analyze

Run Acuity's full multi-source drug-interaction pipeline. The API reads the user's saved regimen from Supabase (managed by the `db` skill) — no drug list is passed directly.

### Sandbox Runtime

- This skill runs inside a NemoClaw sandbox. The active user is `sandbox`, **home is `/sandbox`** (not `/home/sandbox`, not `/root`). The skills root is `/sandbox/.openclaw/skills/`.
- Always invoke scripts with an **absolute path**: `python3 /sandbox/.openclaw/skills/analyze/scripts/analyze.py …`. Do not search `/root/.openclaw/...` — that path does not exist here.
- When you use the `exec` / shell tool, pass the actual command as the `command` argument. Do **not** emit raw RPC strings like `exec --host host --command "…"` — that is an internal envelope, and bash will reject `--host` as an invalid option.
- Stderr lines like `bash: cannot create /proc/self/oom_score_adj: Permission denied` are harmless kernel notices from the sandbox's rootless container. They do not indicate script failure — ignore them and check the script's exit code instead.

### Prerequisites

Environment variables required:
- `ACUITY_PAT` — Personal Access Token from Acuity. Sent as the `x-api-key` header on every request.
- `ACUITY_API_BASE_URL` — API base URL (fallback: `https://acuity.onrender.com`).

### Modes

#### Single-drug check (`--drug`)

Check one new drug against every drug already in the user's saved regimen. Uses the non-streaming endpoint and prints the full `RegimenReport` JSON on completion.

| Argument | Type | Required | Description |
|---|---|---|---|
| `--drug` | string | Yes (mutually exclusive with `--onboarding`) | Drug name (generic or brand) to check against the saved regimen |
| `--session-id` | string | No | Reuse an existing session for memory continuity |

```bash
python3 /sandbox/.openclaw/skills/analyze/scripts/analyze.py --drug "aspirin"
python3 /sandbox/.openclaw/skills/analyze/scripts/analyze.py --drug "warfarin" --session-id abc123
```

#### Onboarding sweep (`--onboarding`)

Check every drug pair in the saved regimen (full post-onboarding sweep). Consumes the SSE stream and prints the `RegimenReport` JSON when the `report_done` event arrives.

| Argument | Type | Required | Description |
|---|---|---|---|
| `--onboarding` | flag | Yes (mutually exclusive with `--drug`) | Run the full regimen pair sweep |
| `--session-id` | string | No | Reuse an existing session for memory continuity |

```bash
python3 /sandbox/.openclaw/skills/analyze/scripts/analyze.py --onboarding
python3 /sandbox/.openclaw/skills/analyze/scripts/analyze.py --onboarding --session-id abc123
```

### Outputs

Prints a `RegimenReport` JSON object to **stdout**. Exits 0 on success, non-zero on failure with an error message on stderr.

### API Routes

| Mode | Method | Route |
|---|---|---|
| `--drug` | POST | `/api/analyze/drug` |
| `--onboarding` | POST | `/api/analyze/onboarding/stream` (SSE) |

### Failure Modes

- Non-zero exit + stderr message if the API returns HTTP ≥ 400.
- Non-zero exit if `ACUITY_PAT` is not set or is rejected (HTTP 401/403).
- Non-zero exit if the server SSE stream ends without emitting a `report_done` event.
- Does **not** crash if the drug list has unknown drugs — the pipeline returns `NO_DATA` coverage for unresolvable names.
- The regimen must have at least one other drug before calling `--drug`, and at least two drugs total before calling `--onboarding`; the API returns HTTP 422 otherwise.
