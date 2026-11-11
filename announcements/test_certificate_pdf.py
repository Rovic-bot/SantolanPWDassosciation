from pathlib import Path
import subprocess
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from .certificate_pdf import attachment_details, certificate_pdfs


@override_settings(CERTIFICATE_OFFICE_EXECUTABLE='synthetic-soffice')
class CertificatePDFTests(SimpleTestCase):
    def test_batch_uses_one_private_conversion_and_keeps_recipient_order(self):
        folders = []

        def convert(command, **kwargs):
            folders.append(Path(command[command.index('--outdir') + 1]))
            self.assertTrue(command[1].startswith('-env:UserInstallation=file:'))
            self.assertIn('--headless', command)
            self.assertNotIn('shell', kwargs)
            for source in command[command.index('--outdir') + 2:]:
                source = Path(source)
                source.with_suffix('.pdf').write_bytes(b'%PDF-1.4\n' + source.read_bytes() + b'\n%%EOF\n')

        with patch('announcements.certificate_pdf.subprocess.run', side_effect=convert) as runner:
            results = certificate_pdfs([b'first personalized document', b'second personalized document'])
        runner.assert_called_once()
        self.assertIn(b'first personalized document', results[0])
        self.assertIn(b'second personalized document', results[1])
        self.assertFalse(folders[0].exists())

    def test_failed_or_missing_output_never_returns_docx_or_private_error_details(self):
        for error in (OSError('private path'), subprocess.TimeoutExpired('private member', 30), None):
            with self.subTest(error=error), patch('announcements.certificate_pdf.subprocess.run', side_effect=error):
                with self.assertRaises(ValidationError) as caught:
                    certificate_pdfs([b'document'])
                self.assertIn('PDF conversion failed', str(caught.exception))
                self.assertNotIn('private', str(caught.exception))

    @override_settings(CERTIFICATE_OFFICE_EXECUTABLE='')
    def test_unconfigured_converter_blocks_new_certificates_but_not_an_empty_batch(self):
        with patch('announcements.certificate_pdf.shutil.which', return_value=None):
            self.assertEqual(certificate_pdfs([]), [])
            with self.assertRaisesMessage(ValidationError, 'PDF conversion is not configured'):
                certificate_pdfs([b'document'])

    def test_pdf_and_historical_docx_have_correct_attachment_metadata(self):
        self.assertEqual(attachment_details(b'%PDF-1.4'), ('Santolan-PWD-Certificate.pdf', 'application/pdf'))
        filename, content_type = attachment_details(b'PK historical attachment')
        self.assertEqual(filename, 'Santolan-PWD-Certificate.docx')
        self.assertIn('wordprocessingml', content_type)
