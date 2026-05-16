---
name: make_report
description: Generate a PDF report from a RegimenReport or DeepResearchReport JSON. Auto-detects the schema and renders the appropriate layout.
---

## MakeReport

Convert an Acuity JSON report to a formatted PDF using ReportLab.

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
python skills/make_report/scripts/make_report.py --in /tmp/report.json

# From stdin (pipe from analyze)
python skills/analyze/scripts/analyze.py --drugs '["aspirin","warfarin"]' | \
  python skills/make_report/scripts/make_report.py

# Explicit output path
python skills/make_report/scripts/make_report.py --in /tmp/report.json --out /session/reports/my_report.pdf
```

### Side Effects

- Writes a PDF to the filesystem (default `/session/reports/`).
- `/session/reports/` is created if it does not exist.

### Failure Modes

- Exit 1 if the input JSON cannot be parsed or does not match any known schema.
- Exit 1 if ReportLab is not installed (`pip install reportlab`).
- Exit 1 if the output path is not writable.
