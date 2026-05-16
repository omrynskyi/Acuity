"""Render a DeepResearchReport dict to a PDF using ReportLab."""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from template import ACUITY_BLUE, STYLES, header_footer, safe

ASPECT_ORDER = [
    "mechanism",
    "indications",
    "contraindications",
    "adverse_events",
    "interactions",
    "pharmacokinetics",
    "other",
]

ASPECT_LABELS = {
    "mechanism": "Mechanism of Action",
    "indications": "Indications",
    "contraindications": "Contraindications",
    "adverse_events": "Adverse Events",
    "interactions": "Drug Interactions",
    "pharmacokinetics": "Pharmacokinetics",
    "other": "Other",
}


def _debug(msg: str) -> None:
    print(f"[make_report/deep_research] {msg}", file=sys.stderr)


def render(data: dict, out_path: str) -> None:
    drug = data.get("drug", "Unknown Drug")
    findings = data.get("findings", [])
    exec_summary = data.get("executive_summary", "")
    generated_at = data.get("generated_at", "")

    # Debug: preview parsed content so blank-PDF issues are immediately visible
    _debug(f"drug={drug!r}")
    _debug(f"generated_at={generated_at!r}")
    _debug(f"executive_summary[:120]={exec_summary[:120]!r}")
    _debug(f"findings count={len(findings)}")
    for i, f in enumerate(findings[:4]):
        aspect = f.get("aspect", "?")
        summary_preview = (f.get("summary") or "")[:80]
        ncitations = len(f.get("citations", []))
        _debug(f"  finding[{i}] aspect={aspect!r} citations={ncitations} summary[:80]={summary_preview!r}")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        out_path,
        pagesize=LETTER,
        topMargin=0.8 * inch,
        bottomMargin=0.7 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    story = []

    # Cover
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(safe(f"Deep Research Report: {drug.title()}"), STYLES["title"]))
    story.append(Paragraph(safe(f"Generated: {generated_at}"), STYLES["subtitle"]))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E7EB"), spaceAfter=8))

    # Executive summary
    if exec_summary:
        story.append(Paragraph("Executive Summary", STYLES["h2"]))
        story.append(Paragraph(safe(exec_summary), STYLES["body"]))
        story.append(Spacer(1, 0.1 * inch))

    # Findings — sorted by ASPECT_ORDER, unknown aspects at end
    indexed: dict[str, dict] = {f.get("aspect", "other"): f for f in findings}
    ordered = [indexed[a] for a in ASPECT_ORDER if a in indexed]
    known = set(ASPECT_ORDER)
    ordered += [f for f in findings if f.get("aspect") not in known]

    if ordered:
        story.append(Paragraph("Findings", STYLES["h2"]))

    for finding in ordered:
        aspect = finding.get("aspect", "other")
        label = ASPECT_LABELS.get(aspect, aspect.replace("_", " ").title())
        summary = finding.get("summary") or ""
        citations = finding.get("citations", [])

        story.append(Paragraph(safe(label), STYLES["h3"]))
        if summary:
            story.append(Paragraph(safe(summary), STYLES["body"]))

        if citations:
            table_data = [["Title", "URL", "Excerpt"]]
            for c in citations:
                table_data.append([
                    safe(str(c.get("title", ""))[:40]),
                    safe(str(c.get("url", ""))[:50]),
                    safe(str(c.get("quote") or "")[:80]),
                ])
            t = Table(table_data, colWidths=[1.6 * inch, 2.0 * inch, 2.9 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TEXTCOLOR", (1, 1), (1, -1), ACUITY_BLUE),
            ]))
            story.append(t)

        story.append(Spacer(1, 0.12 * inch))

    _debug(f"story items={len(story)}, writing to {out_path!r}")
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    _debug("done")
