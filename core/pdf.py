"""Small shared PDF renderer for program proposals and authorized reports."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle


def render_pdf(title, sections=(), *, columns=None, rows=(), subtitle=''):
    output = BytesIO()
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(output, pagesize=landscape(A4) if columns else A4,
                                 rightMargin=36, leftMargin=36, topMargin=42, bottomMargin=42,
                                 title=title, author='Barangay Santolan PWD Association')

    def paragraph(value, style='BodyText'):
        return Paragraph(escape(str(value if value is not None else 'Not specified')).replace('\n', '<br/>'), styles[style])

    story = [paragraph(title, 'Title'), paragraph(subtitle), Spacer(1, 16)]
    for heading, value in sections:
        story.extend([paragraph(heading, 'Heading2'), paragraph(value), Spacer(1, 8)])
    if columns:
        table = LongTable([[paragraph(value) for value in columns]] +
                         [[paragraph(value) for value in row] for row in rows],
                         colWidths=[document.width / len(columns)] * len(columns), repeatRows=1,
                         hAlign='LEFT')
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef4')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), .3, colors.HexColor('#bcc7d1')),
            ('LEFTPADDING', (0, 0), (-1, -1), 7), ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))
        story.append(table)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.drawRightString(doc.pagesize[0] - 36, 23, f'Page {doc.page}')
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
