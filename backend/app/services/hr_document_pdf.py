"""Server-generated English A4 portrait letters and certificates."""

import io

from reportlab.lib.colors import Color  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4  # type: ignore[import-untyped]
from reportlab.pdfgen import canvas  # type: ignore[import-untyped]

from app.services.report_exports import PDF_FONT, _font, _pdf_text, _visual_text, _wrap

MARGIN = 64
BODY_SIZE = 10
BODY_LEADING = 15
BOTTOM = 60
DRAFT_NOTICE = "DRAFT PREVIEW - NOT AN OFFICIAL DOCUMENT - NOT VALID FOR ISSUE"
UNCONFIGURED = "[not configured]"


def _lines(text: str, width: float, size: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        lines.extend(_wrap(_pdf_text(paragraph), width, size) if paragraph.strip() else [""])
    return lines


def render_document(
    *,
    title: str,
    body: str,
    company: dict,
    document_number: str | None,
    issue_date: str,
    addressee: str | None,
    certificate: bool,
    draft: bool,
) -> bytes:
    _font()
    width, height = A4
    usable = width - 2 * MARGIN
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4, pageCompression=1)
    pdf.setTitle(f"{'DRAFT ' if draft else ''}{title} {document_number or ''}".strip())
    pdf.setAuthor(company.get("company_legal_name") or "")

    header: list[tuple[str, int]] = [
        (company.get("company_legal_name") or UNCONFIGURED, 14),
    ]
    for line in (company.get("company_address") or UNCONFIGURED).split("\n"):
        header.append((line, 9))
    header.append((f"Trade Licence No. {company.get('trade_license_number') or UNCONFIGURED}", 9))

    reference = f"Ref: {document_number}" if document_number else "Ref: (assigned on issue)"
    recipient = (
        f"To: {addressee}" if addressee else ("To Whom It May Concern" if certificate else None)
    )
    body_lines = _lines(body, usable, BODY_SIZE)
    signature = [
        f"For {company.get('company_legal_name') or UNCONFIGURED}",
        "",
        "",
        "",
        company.get("signatory_name") or "Signatory: " + UNCONFIGURED,
        company.get("signatory_designation") or "Designation: " + UNCONFIGURED,
    ]

    recipient_lines = _wrap(_pdf_text(recipient), usable, BODY_SIZE) if recipient else []
    header_height = (
        sum(size + 5 for _, size in header)
        + 4
        + 22
        + 26
        + (len(recipient_lines) * BODY_LEADING + 10 if recipient_lines else 0)
        + 28
    )
    pages: list[list[str]] = [[]]
    first_page_capacity = int((height - MARGIN - header_height - BOTTOM) // BODY_LEADING)
    other_capacity = int((height - MARGIN - BOTTOM) // BODY_LEADING)
    for line in body_lines + [""] + signature:
        capacity = first_page_capacity if len(pages) == 1 else other_capacity
        if len(pages[-1]) >= capacity:
            pages.append([])
        pages[-1].append(line)

    for number, lines in enumerate(pages, 1):
        if draft:
            pdf.saveState()
            pdf.setFillColor(Color(0.55, 0.1, 0.1, alpha=0.16))
            pdf.setFont(PDF_FONT, 120)
            pdf.translate(width / 2, height / 2)
            pdf.rotate(45)
            pdf.drawCentredString(0, 0, "DRAFT")
            pdf.restoreState()
            pdf.setFillColor(Color(0.55, 0.1, 0.1))
            pdf.setFont(PDF_FONT, 8)
            pdf.drawCentredString(width / 2, height - 28, DRAFT_NOTICE)
            pdf.drawString(MARGIN, 32, DRAFT_NOTICE)
            pdf.setFillColor(Color(0, 0, 0))
        y = height - MARGIN
        if number == 1:
            for text, size in header:
                pdf.setFont(PDF_FONT, size)
                pdf.drawString(MARGIN, y, _visual_text(_pdf_text(text)))
                y -= size + 5
            y -= 4
            pdf.setLineWidth(0.6)
            pdf.line(MARGIN, y, width - MARGIN, y)
            y -= 22
            pdf.setFont(PDF_FONT, BODY_SIZE)
            pdf.drawString(MARGIN, y, _visual_text(reference))
            pdf.drawRightString(width - MARGIN, y, _visual_text(f"Date: {issue_date}"))
            y -= 26
            if recipient_lines:
                for line in recipient_lines:
                    pdf.drawString(MARGIN, y, _visual_text(line))
                    y -= BODY_LEADING
                y -= 10
            pdf.setFont(PDF_FONT, 13)
            pdf.drawCentredString(width / 2, y, _visual_text(_pdf_text(title)))
            y -= 28
        pdf.setFont(PDF_FONT, BODY_SIZE)
        for line in lines:
            pdf.drawString(MARGIN, y, _visual_text(line))
            y -= BODY_LEADING
        pdf.setFont(PDF_FONT, 8)
        footer = f"{document_number or 'Draft'} | Page {number} of {len(pages)}"
        pdf.drawRightString(width - MARGIN, 32, _visual_text(footer))
        pdf.showPage()
    pdf.save()
    return output.getvalue()
