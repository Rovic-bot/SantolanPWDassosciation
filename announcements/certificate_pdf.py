"""Convert personalized Word certificates locally; retain only the final PDFs."""
from pathlib import Path
import logging
import shutil
import subprocess
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore

from django.conf import settings
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)
# The deployed Gunicorn worker serves multiple request threads. One Office
# process at a time leaves memory and request capacity for the rest of the app.
# Reject overlapping work immediately instead of tying up threads waiting.
_conversion_slot = BoundedSemaphore(1)

PDF_TYPE = 'application/pdf'
DOCX_TYPE = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'


def attachment_details(document):
    # Old issued attachments remain byte-for-byte intact for safe delivery retries.
    if bytes(document).startswith(b'%PDF-'):
        return 'Santolan-PWD-Certificate.pdf', PDF_TYPE
    return 'Santolan-PWD-Certificate.docx', DOCX_TYPE


def certificate_pdfs(documents, *, render=None):
    """Convert a batch, optionally rendering its source items after reserving capacity."""
    if not documents:
        return []
    if not _conversion_slot.acquire(blocking=False):
        raise ValidationError('Certificate conversion is already running. Wait for it to finish, then retry publishing. '
                              'No results or certificate emails from this request were published.')
    try:
        # Preparing personalized DOCX files also costs CPU/memory. Reserve the
        # slot before rendering them so overlapping publications fail promptly.
        if render is not None:
            documents = [render(document) for document in documents]
        return _convert_documents(documents)
    finally:
        _conversion_slot.release()


def _convert_documents(documents):
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
                # Cold Office/font initialization needs a fixed startup budget, even
                # for one recipient. Keep the existing 180-second overall cap.
                timeout=min(180, max(90, 30 + len(sources) * 5)),
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            pdfs = [source.with_suffix('.pdf').read_bytes() for source in sources]
            if any(not content.startswith(b'%PDF-') or b'%%EOF' not in content[-1024:] for content in pdfs):
                raise ValueError('Invalid PDF output')
            return pdfs
    except (OSError, subprocess.SubprocessError, ValueError) as error:
        # Log fixed categories only: process output, commands, paths and exception
        # messages can contain document text or recipient information.
        category = ('timeout' if isinstance(error, subprocess.TimeoutExpired) else
                    'process' if isinstance(error, subprocess.SubprocessError) else
                    'io' if isinstance(error, OSError) else 'invalid_output')
        logger.warning('Certificate conversion failed: category=%s; documents=%d.', category, len(documents))
        # Publication and the outbox roll back together; never send a partial batch
        # or expose converter output containing private document text/paths.
        raise ValidationError('Certificate PDF conversion failed. No results or certificate emails were published. '
                              'Check LibreOffice and try publishing again.') from None
