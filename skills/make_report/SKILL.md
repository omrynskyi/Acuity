---
name: make_report
description: Generate a PDF report from a RegimenReport or DeepResearchReport JSON. Auto-detects the schema and renders the appropriate layout.
---

## MakeReport

Convert an Acuity JSON report to a formatted PDF using ReportLab.

### Sandbox Runtime

- This skill runs inside a NemoClaw sandbox. The active user is `sandbox`, **home is `/sandbox`** (not `/home/sandbox`, not `/root`). The skills root is `/sandbox/.openclaw/skills/`.
- Always invoke scripts with an **absolute path**: `python3 /sandbox/.openclaw/skills/make_report/scripts/make_report.py …`. Do not search `/root/.openclaw/...` — that path does not exist here.
- When you use the `exec` / shell tool, pass the actual command as the `command` argument. Do **not** emit raw RPC strings like `exec --host host --command "…"` — that is an internal envelope, and bash will reject `--host` as an invalid option.
- Stderr lines like `bash: cannot create /proc/self/oom_score_adj: Permission denied` are harmless kernel notices from the sandbox's rootless container. They do not indicate script failure — ignore them and check the script's exit code instead.

### Inputs

| Argument | Type | Required | Description |
|---|---|---|---|
| `--in` | file path | No* | Path to the JSON report file |
| `--out` | file path | No | Output PDF path (default: `/session/reports/<timestamp>.pdf`) |

*If `--in` is omitted, JSON is read from stdin.

### Schema Detection

- `schema_version == "1.0"` **and** `interactions` key present → **RegimenReport** layout
- `report_type == "deep_research"` → **DeepResearchReport** layout
- Anything else → exit 1 with a descriptive error

### Outputs

Prints the path of the generated PDF to **stdout**. Exits 0 on success, non-zero on failure with an error message on stderr.

### Invocation

```bash
# From a file
python3 /sandbox/.openclaw/skills/make_report/scripts/make_report.py --in /tmp/report.json

# From stdin (pipe from analyze)
python3 /sandbox/.openclaw/skills/analyze/scripts/analyze.py --drugs '["aspirin","warfarin"]' | \
  python3 /sandbox/.openclaw/skills/make_report/scripts/make_report.py

# Explicit output path
python3 /sandbox/.openclaw/skills/make_report/scripts/make_report.py --in /tmp/report.json --out /session/reports/my_report.pdf
```

### Side Effects

- Writes a PDF to the filesystem (default `/session/reports/`).
- `/session/reports/` is created if it does not exist.

### Failure Modes

- Exit 1 if the input JSON cannot be parsed or does not match any known schema.
- Exit 1 if ReportLab is not installed (`pip install reportlab`).
- Exit 1 if the output path is not writable.
