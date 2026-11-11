"""Build-time Linux converter check using fictional text, without database access."""
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from django.conf import settings
settings.configure(CERTIFICATE_OFFICE_EXECUTABLE='/usr/bin/soffice')
from announcements.certificates import certificate_document
from announcements.certificate_pdf import certificate_pdfs

document = certificate_document(member_name='Deployment Test',
    program_name='Fictional Runtime Verification', issued_on=date(2026, 11, 11))
pdf, = certificate_pdfs([document])
assert pdf.startswith(b'%PDF-') and b'%%EOF' in pdf[-1024:]
print('Linux certificate PDF conversion verified using fictional text; no email sent.')
