"""Personalize the owner's certificate without rebuilding its OOXML layout."""
from io import BytesIO
from pathlib import Path
import re
from xml.sax.saxutils import escape
from zipfile import ZipFile

TEMPLATE = Path(__file__).resolve().parent / 'certificate_templates' / 'assistance.docx'


def certificate_document(*, member_name, program_name, issued_on):
    member_name = ' '.join(str(member_name).split())
    program_name = ' '.join(str(program_name).split())
    replacements = {
        '[Recipient Name: ____________]': member_name,
        '[PROGRAM NAME]': program_name,
        'P R O G R A M   N A M E': program_name,
        'Date here': issued_on.strftime('%B %d, %Y'),
    }
    output = BytesIO()
    with ZipFile(TEMPLATE) as source, ZipFile(output, 'w') as target:
        xml = source.read('word/document.xml').decode('utf-8')
        # The supplied template keeps each placeholder in one text run. Fail
        # closed if a replacement template changes that contract.
        for placeholder, value in replacements.items():
            if placeholder not in xml:
                raise ValueError('Certificate template placeholder is missing.')
            if not value or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value):
                raise ValueError('Certificate text is invalid.')
        # Only long variable paragraphs change type size/leading. All fixed
        # furniture and every other package part retain the supplied design.
        def fit_paragraph(match):
            paragraph, size = match.group(), None
            if 'P R O G R A M   N A M E' in paragraph and len(program_name) > 64:
                size = 32 if len(program_name) <= 110 else 28 if len(program_name) <= 150 else 24
            if '[Recipient Name:' in paragraph:
                length = len(member_name) + len(program_name)
                size = 22 if length > 350 else 24 if length > 250 else 28 if length > 150 else None
            if 'Date here' in paragraph:
                # The source's padded date label leaves too little room for a
                # complete date. Keep the date together in its original cell.
                size = 28
                paragraph = paragraph.replace('Date :       ', 'Date: ')
            if size:
                paragraph = re.sub(r'(<w:sz(?:Cs)? w:val=")[0-9]+', rf'\g<1>{size}', paragraph)
                paragraph = paragraph.replace('w:line="360"', 'w:line="280"')
            return paragraph
        xml = re.sub(r'<w:p\b[^>]*>.*?</w:p>', fit_paragraph, xml, flags=re.DOTALL)
        # Correct the unmatched closing parenthesis in the supplied sentence.
        xml = xml.replace('member).', 'member.')
        # One pass prevents member-supplied placeholder-like text from being
        # interpreted as another template slot.
        slots = '|'.join(re.escape(value) for value in replacements)
        xml = re.sub(slots, lambda match: escape(replacements[match.group()]), xml)
        for entry in source.infolist():
            target.writestr(entry, xml.encode('utf-8') if entry.filename == 'word/document.xml'
                            else source.read(entry.filename))
    return output.getvalue()
