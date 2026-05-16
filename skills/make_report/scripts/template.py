"""Shared ReportLab styles and canvas helpers for Acuity PDF reports."""

from __future__ import annotations

import html

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch

# Acuity brand colours
ACUITY_BLUE = colors.HexColor("#1A56DB")
ACUITY_DARK = colors.HexColor("#111928")
ACUITY_LIGHT_BG = colors.HexColor("#F9FAFB")
ACUITY_BORDER = colors.HexColor("#E5E7EB")

SEVERITY_COLORS: dict[str, colors.Color] = {
    "contraindicated": colors.HexColor("#DC2626"),
    "major": colors.HexColor("#EA580C"),
    "moderate": colors.HexColor("#D97706"),
    "minor": colors.HexColor("#16A34A"),
    "no_concern": colors.HexColor("#6B7280"),
}

_base = getSampleStyleSheet()

STYLES: dict[str, ParagraphStyle] = {
    "title": ParagraphStyle(
        "AcuityTitle",
        parent=_base["Title"],
        fontSize=22,
        textColor=ACUITY_DARK,
        spaceAfter=6,
    ),
    "subtitle": ParagraphStyle(
        "AcuitySubtitle",
        parent=_base["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#6B7280"),
        spaceAfter=18,
    ),
    "h2": ParagraphStyle(
        "AcuityH2",
        parent=_base["Heading2"],
        fontSize=14,
        textColor=ACUITY_DARK,
        spaceBefore=14,
        spaceAfter=4,
    ),
    "h3": ParagraphStyle(
        "AcuityH3",
        parent=_base["Heading3"],
        fontSize=11,
        textColor=ACUITY_DARK,
        spaceBefore=10,
        spaceAfter=2,
    ),
    "body": ParagraphStyle(
        "AcuityBody",
        parent=_base["Normal"],
        fontSize=10,
        textColor=ACUITY_DARK,
        leading=14,
        spaceAfter=6,
    ),
    "small": ParagraphStyle(
        "AcuitySmall",
        parent=_base["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#6B7280"),
        leading=11,
    ),
    "label": ParagraphStyle(
        "AcuityLabel",
        parent=_base["Normal"],
        fontSize=9,
        textColor=colors.white,
        leading=11,
    ),
}


def safe(text: str) -> str:
    """Escape XML special characters so ReportLab Paragraph never silently drops content.

    ReportLab parses Paragraph text as XML; bare &, <, > break the parser and
    the paragraph renders as blank with no error. Always pass dynamic text through
    this before handing it to Paragraph().
    """
    return html.escape(str(text) if text is not None else "")


def header_footer(canvas, doc) -> None:
    """Draw page header and footer on every page."""
    canvas.saveState()
    w = doc.pagesize[0]

    # Header bar
    canvas.setFillColor(ACUITY_BLUE)
    canvas.rect(0, doc.pagesize[1] - 0.5 * inch, w, 0.5 * inch, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(0.5 * inch, doc.pagesize[1] - 0.33 * inch, "Acuity · Drug Interaction Report")

    # Footer
    canvas.setFillColor(ACUITY_DARK)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(0.5 * inch, 0.35 * inch, "Acuity — For informational purposes only. Not a substitute for clinical judgment.")
    canvas.drawRightString(w - 0.5 * inch, 0.35 * inch, f"Page {doc.page}")

    canvas.restoreState()
