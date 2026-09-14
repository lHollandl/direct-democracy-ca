"""PDF export of a summary document (DEMOCRACY.md §11.6).

The same content, rendered server-side. The summary hash and URL are printed in
the footer of every page. The PDF's own bytes are not hashed — the web page is
canonical, and the PDF says so.
"""

from __future__ import annotations

import io

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
)

MARGIN = 0.75 * inch


def render(document: dict, summary_hash: str, url: str) -> bytes:
    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10, leading=14)
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=16, spaceAfter=10)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12, spaceBefore=12)
    small = ParagraphStyle("small", parent=body, fontSize=8, textColor="#444444")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColorRGB(0.3, 0.3, 0.3)
        canvas.drawString(MARGIN, 0.5 * inch, f"Fingerprint (SHA-256): {summary_hash}")
        canvas.drawString(MARGIN, 0.36 * inch, f"Published at: {url}")
        canvas.drawRightString(
            LETTER[0] - MARGIN, 0.36 * inch, f"Page {canvas.getPageNumber()}"
        )
        canvas.restoreState()

    doc = BaseDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=inch,
        title=f"Ballot results — cycle {document['header']['cycle_number']}",
    )
    frame = Frame(
        MARGIN, inch, LETTER[0] - 2 * MARGIN, LETTER[1] - MARGIN - inch, id="body"
    )
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=footer)])

    header = document["header"]
    story = [
        Paragraph(
            f"Ballot results — {_esc(header['community_label'])}, cycle {header['cycle_number']}",
            h1,
        ),
        Paragraph(
            f"Active users at snapshot: {header['active_users_at_snapshot']}. "
            f"{_esc(header['verification_mix'])}. Jury: {_esc(header['jury'])}.",
            body,
        ),
        Paragraph(_esc(header["residency_note"]), small),
        Spacer(1, 10),
    ]

    if document.get("empty_note"):
        story.append(Paragraph(_esc(document["empty_note"]), body))

    if document["results"]:
        story.append(Paragraph("Results", h2))
        for item in document["results"]:
            story.append(
                Paragraph(
                    f"<b>{item['position']}. {_esc(item['umbrella'])} — {item['result']}</b> "
                    f"({item['yes']} yes, {item['no']} no)",
                    body,
                )
            )
            story.append(Paragraph(_esc(item["solution_text"]), body))
            story.append(
                Paragraph(
                    f"Version {item['solution_version']} · fingerprint "
                    f"{item['solution_version_hash']} · proposed by "
                    f"{_esc(item['author_display_at_snapshot'])} · "
                    f"{_esc(item['ai_influence_label'])}",
                    small,
                )
            )
            story.append(Spacer(1, 8))

    if document["held_back"]:
        story.append(Paragraph("Held back by the jury", h2))
        for item in document["held_back"]:
            story.append(
                Paragraph(f"<b>{_esc(item['umbrella'])}</b>", body)
            )
            story.append(Paragraph(_esc(item["solution_text"]), body))
            for reason in item["jury_reasons"]:
                story.append(
                    Paragraph(
                        f"{_esc(reason['juror'])} — {_esc(reason['category'])}: "
                        f"{_esc(reason['reason'])}",
                        small,
                    )
                )
            story.append(Spacer(1, 8))

    story.append(Paragraph("How this was produced", h2))
    for section in document["how_this_was_produced"]:
        story.append(Paragraph(f"<b>{_esc(section['heading'])}</b>", body))
        story.append(Paragraph(_esc(section["text"]), body))
        story.append(
            Paragraph(
                f"Settings in force: {_esc(section['settings_in_force'])} "
                f"({_esc(section['rule_version'])})",
                small,
            )
        )
        story.append(Spacer(1, 6))

    story.append(Paragraph("Verify this document", h2))
    story.append(
        Paragraph(
            "This PDF is a copy. The web page is the original, and it is what the "
            "fingerprint below was computed from.",
            body,
        )
    )
    story.append(Paragraph(f"SHA-256: {summary_hash}", small))

    doc.build(story)
    return buffer.getvalue()


def _esc(text) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
