"""Render a RegimenReport dict to a PDF using ReportLab."""

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

from template import SEVERITY_COLORS, STYLES, header_footer, safe


def _debug(msg: str) -> None:
    print(f"[make_report/regimen] {msg}", file=sys.stderr)


def _severity_badge(severity: str) -> Table:
    bg = SEVERITY_COLORS.get(severity, colors.HexColor("#6B7280"))
    label = severity.upper().replace("_", " ")
    t = Table([[Paragraph(safe(label), STYLES["label"])]], colWidths=[1.2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return t


def render(data: dict, out_path: str) -> None:
    regimen = data.get("regimen", [])
    interactions = data.get("interactions", [])
    generated_at = data.get("generated_at", "")
    overall = data.get("overall_summary", "")

    # Debug: preview parsed content
    _debug(f"generated_at={generated_at!r}")
    _debug(f"regimen drugs={[d.get('generic_name') or d.get('input_name') for d in regimen]}")
    _debug(f"interactions count={len(interactions)}")
    _debug(f"overall_summary[:120]={overall[:120]!r}")
    for i, ix in enumerate(interactions[:3]):
        pair = ix.get("drug_pair", [])
        severity = ix.get("severity", "?")
        _debug(f"  interaction[{i}] pair={pair} severity={severity!r}")

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
    story.append(Paragraph("Drug Interaction Report", STYLES["title"]))
    story.append(Paragraph(safe(f"Generated: {generated_at}"), STYLES["subtitle"]))

    # Regimen list
    if regimen:
        drug_names = []
        for d in regimen:
            name = d.get("generic_name") or d.get("input_name", "Unknown")
            drug_names.append(name.title())
        story.append(Paragraph("Regimen", STYLES["h2"]))
        story.append(Paragraph(safe(", ".join(drug_names)), STYLES["body"]))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E7EB"), spaceAfter=8))

    # Overall summary
    if overall:
        story.append(Paragraph("Overall Summary", STYLES["h2"]))
        story.append(Paragraph(safe(overall), STYLES["body"]))

    # Patient-friendly summary
    friendly = data.get("patient_friendly_summary", "")
    if friendly:
        story.append(Paragraph("Patient-Friendly Summary", STYLES["h2"]))
        story.append(Paragraph(safe(friendly), STYLES["body"]))

    # Interactions
    if interactions:
        story.append(Paragraph("Interactions", STYLES["h2"]))
        story.append(Spacer(1, 0.05 * inch))

    for ix in interactions:
        pair = ix.get("drug_pair", [])
        pair_label = " + ".join(str(p).title() for p in pair) if pair else "Unknown pair"
        severity = ix.get("severity", "no_concern")

        story.append(_severity_badge(severity))
        story.append(Spacer(1, 0.04 * inch))
        story.append(Paragraph(safe(pair_label), STYLES["h3"]))

        headline = ix.get("headline", "")
        if headline:
            # Wrap in <i> after escaping — safe() escapes first, then we add the tag
            story.append(Paragraph(f"<i>{safe(headline)}</i>", STYLES["body"]))

        reasoning = ix.get("reasoning", "")
        if reasoning:
            story.append(Paragraph(safe(reasoning), STYLES["body"]))

        # Citations table
        citations = ix.get("citations", [])
        if citations:
            story.append(Paragraph("Citations", STYLES["h3"]))
            table_data = [["Source", "Finding #", "Excerpt"]]
            for c in citations:
                table_data.append([
                    safe(str(c.get("source", ""))),
                    safe(str(c.get("finding_index", ""))),
                    safe(str(c.get("quote", ""))[:120]),
                ])
            t = Table(table_data, colWidths=[1.4 * inch, 0.8 * inch, 4.3 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(t)

        story.append(Spacer(1, 0.15 * inch))

    _debug(f"story items={len(story)}, writing to {out_path!r}")
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    _debug("done")
