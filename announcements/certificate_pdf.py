"""Convert personalized Word certificates locally; retain only the final PDFs."""
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.exceptions import ValidationError

PDF_TYPE = 'application/pdf'
DOCX_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def attachment_details(document):
    # Old issued attachments remain byte-for-byte intact for safe delivery retries.
    if bytes(document).startswith(b'%PDF-'):
        return 'Santolan-PWD-Certificate.pdf', PDF_TYPE
    return 'Santolan-PWD-Certificate.docx', DOCX_TYPE


def certificate_pdfs(documents):
    """One isolated LibreOffice process per publication, including all recipients."""
    if not documents:
        return []
    executable = getattr(settings, 'CERTIFICATE_OFFICE_EXECUTABLE', '') or shutil.which('soffice')
    if not executable:
        raise ValidationError('PDF conversion is not configured. Configure LibreOffice before publishing certificates.')
    try:
        with TemporaryDirectory(prefix='santolan-certificates-') as directory:
            folder = Path(directory)
            sources = []
            for number, document in enumerate(documents):
                source = folder / f'certificate-{number}.docx'
                source.write_bytes(document)
                sources.append(source)
            # No shell, member-supplied paths, shared Office profile or visible window.
            subprocess.run([str(executable), f'-env:UserInstallation={(folder / "profile").as_uri()}',
                '--headless', '--nologo', '--nodefault', '--norestore',
                '--convert-to', 'pdf:writer_pdf_Export', '--outdir', str(folder),
                *map(str, sources)], check=True, capture_output=True,
                timeout=min(180, 30 + len(sources) * 5),
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            pdfs = [source.with_suffix('.pdf').read_bytes() for source in sources]
            if any(not content.startswith(b'%PDF-') or b'%%EOF' not in content[-1024:] for content in pdfs):
                raise ValueError('Invalid PDF output')
            return pdfs
    except (OSError, subprocess.SubprocessError, ValueError):
        # Publication and the outbox roll back together; never send a partial batch
        # or expose converter output containing private document text/paths.
        raise ValidationError('Certificate PDF conversion failed. No results or certificate emails were published. '
                              'Check LibreOffice and try publishing again.') from None
