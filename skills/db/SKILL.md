---
name: db
description: Read and write the user's profile, active medication list, and past analysis sessions via the Acuity API.
---

## DB

Manage user data stored in Supabase through the Acuity API. All tools authenticate via `ACUITY_PAT` and are scoped to the matching user's profile.

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
python skills/db/scripts/get_profile.py
```

### update_profile

Update one or more profile fields.

```bash
python skills/db/scripts/update_profile.py --name "Jane Doe" --age 45
python skills/db/scripts/update_profile.py --doctor "Dr. Smith" --doctor-email "smith@clinic.com"
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
python skills/db/scripts/list_medicines.py
```

### add_medicine

Add a drug to the active medication list.

```bash
python skills/db/scripts/add_medicine.py --drug "metformin" --dose "500mg" --frequency "twice daily"
```

| Argument | Required | Description |
|---|---|---|
| `--drug` | Yes | Drug name (generic or brand) |
| `--dose` | No | Dosage string, e.g. "500mg" |
| `--frequency` | No | Frequency string, e.g. "twice daily" |

### remove_medicine

Soft-delete a medication (sets `removed_at = now()`). Does not permanently delete the row.

```bash
python skills/db/scripts/remove_medicine.py --id <uuid>
```

### update_medicine

Update dose or frequency for an existing medication.

```bash
python skills/db/scripts/update_medicine.py --id <uuid> --dose "1000mg"
python skills/db/scripts/update_medicine.py --id <uuid> --frequency "once daily"
```

---

## Session / Report History Tools

### list_sessions

List past drug-interaction analyses, most recent first.

```bash
python skills/db/scripts/list_sessions.py
python skills/db/scripts/list_sessions.py --limit 5
```

Returns: `id`, `new_drug`, `drugs_checked`, `overall_severity`, `generated_at`, `created_at`.

### get_session

Get the full report JSON for a specific past analysis.

```bash
python skills/db/scripts/get_session.py --id <session-uuid>
```

### get_interactions

Get the severity-sorted interaction rows for a session.

```bash
python skills/db/scripts/get_interactions.py --session-id <session-uuid>
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
