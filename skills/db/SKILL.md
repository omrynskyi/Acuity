---
name: db
description: Read and write the user's profile, active medication list, and past analysis sessions via the Acuity API.
---

## DB

Manage user data stored in Supabase through the Acuity API. All tools authenticate via `ACUITY_PAT` and are scoped to the matching user's profile.

### Sandbox Runtime

- This skill runs inside a NemoClaw sandbox. The active user is `sandbox`, **home is `/sandbox`** (not `/home/sandbox`, not `/root`). The skills root is `/sandbox/.openclaw/skills/`.
- Always invoke scripts with an **absolute path**: `python3 /sandbox/.openclaw/skills/db/scripts/<script>.py …`. Do not search `/root/.openclaw/...` — that path does not exist here.
- When you use the `exec` / shell tool, pass the actual command as the `command` argument. Do **not** emit raw RPC strings like `exec --host host --command "…"` — that is an internal envelope, and bash will reject `--host` as an invalid option.
- Stderr lines like `bash: cannot create /proc/self/oom_score_adj: Permission denied` are harmless kernel notices from the sandbox's rootless container. They do not indicate script failure — ignore them and check the script's exit code instead.

### Prerequisites

| Variable | Required | Description |
|---|---|---|
| `ACUITY_PAT` | Yes | Personal Access Token from Acuity account settings. Sent as `x-api-key`. |
| `ACUITY_API_BASE_URL` | No | API base URL (fallback: `http://localhost:8081`) |

---

## Profile Tools

### get_profile

Return the user's profile (name, age, sex, height, weight, doctor).

```bash
python3 /sandbox/.openclaw/skills/db/scripts/get_profile.py
```

### update_profile

Update one or more profile fields.

```bash
python3 /sandbox/.openclaw/skills/db/scripts/update_profile.py --name "Jane Doe" --age 45
python3 /sandbox/.openclaw/skills/db/scripts/update_profile.py --doctor "Dr. Smith" --doctor-email "smith@clinic.com"
```

| Argument | Required | Description |
|---|---|---|
| `--name` | No | Full name |
| `--age` | No | Age in years |
| `--sex` | No | Biological sex |
| `--height` | No | Height string, e.g. "5ft 8in" |
| `--weight` | No | Weight string, e.g. "160 lbs" |
| `--doctor` | No | Primary care physician name |
| `--doctor-email` | No | Physician contact email |

---

## Regimen Tools (Active Medication List)

### list_medicines

List all active medications (removed_at IS NULL), ordered by sort_order.

```bash
python3 /sandbox/.openclaw/skills/db/scripts/list_medicines.py
```

### add_medicine

Add a drug to the active medication list.

```bash
python3 /sandbox/.openclaw/skills/db/scripts/add_medicine.py --drug "metformin" --dose "500mg" --frequency "twice daily"
```

| Argument | Required | Description |
|---|---|---|
| `--drug` | Yes | Drug name (generic or brand) |
| `--dose` | No | Dosage string, e.g. "500mg" |
| `--frequency` | No | Frequency string, e.g. "twice daily" |

### remove_medicine

Soft-delete a medication (sets `removed_at = now()`). Does not permanently delete the row.

```bash
python3 /sandbox/.openclaw/skills/db/scripts/remove_medicine.py --id <uuid>
```

### update_medicine

Update dose or frequency for an existing medication.

```bash
python3 /sandbox/.openclaw/skills/db/scripts/update_medicine.py --id <uuid> --dose "1000mg"
python3 /sandbox/.openclaw/skills/db/scripts/update_medicine.py --id <uuid> --frequency "once daily"
```

---

## Session / Report History Tools

### list_sessions

List past drug-interaction analyses, most recent first.

```bash
python3 /sandbox/.openclaw/skills/db/scripts/list_sessions.py
python3 /sandbox/.openclaw/skills/db/scripts/list_sessions.py --limit 5
```

Returns: `id`, `new_drug`, `drugs_checked`, `overall_severity`, `generated_at`, `created_at`.

### get_session

Get the full report JSON for a specific past analysis.

```bash
python3 /sandbox/.openclaw/skills/db/scripts/get_session.py --id <session-uuid>
```

### get_interactions

Get the severity-sorted interaction rows for a session.

```bash
python3 /sandbox/.openclaw/skills/db/scripts/get_interactions.py --session-id <session-uuid>
```

Returns rows with: `drug_a`, `drug_b`, `severity`, `headline`, `reasoning`, `citations`.

---

## API Routes

All scripts call the following Acuity API endpoints:

| Script | Method | Route |
|---|---|---|
| `get_profile.py` | GET | `/api/user/profile` |
| `update_profile.py` | PATCH | `/api/user/profile` |
| `list_medicines.py` | GET | `/api/user/medicines` |
| `add_medicine.py` | POST | `/api/user/medicines` |
| `remove_medicine.py` | DELETE | `/api/user/medicines/{id}` |
| `update_medicine.py` | PATCH | `/api/user/medicines/{id}` |
| `list_sessions.py` | GET | `/api/user/sessions` |
| `get_session.py` | GET | `/api/user/sessions/{id}` |
| `get_interactions.py` | GET | `/api/user/sessions/{id}/interactions` |
