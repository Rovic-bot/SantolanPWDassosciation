from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess
from threading import Event
from unittest.mock import Mock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings

from .certificate_pdf import attachment_details, certificate_pdfs


@override_settings(CERTIFICATE_OFFICE_EXECUTABLE='synthetic-soffice')
class CertificatePDFTests(SimpleTestCase):
    def test_overlapping_conversion_rejects_promptly_and_allows_retry(self):
        entered, release = Event(), Event()
        calls = []

        def convert(command, **kwargs):
            calls.append(command)
            if len(calls) == 1:
                entered.set()
                if not release.wait(5):
                    raise TimeoutError('Synthetic conversion was not released.')
            for source in command[command.index('--outdir') + 2:]:
                Path(source).with_suffix('.pdf').write_bytes(b'%PDF-1.4\nSYNTHETIC\n%%EOF\n')

        with patch('announcements.certificate_pdf.subprocess.run', side_effect=convert):
            with ThreadPoolExecutor(max_workers=1) as pool:
                active = pool.submit(certificate_pdfs, [b'first synthetic certificate'])
                try:
                    self.assertTrue(entered.wait(5))
                    self.assertEqual(certificate_pdfs([]), [])
                    render = Mock(return_value=b'overlapping synthetic certificate')
                    with self.assertRaisesMessage(ValidationError, 'already running'):
                        certificate_pdfs(['synthetic recipient'], render=render)
                    render.assert_not_called()
                    self.assertEqual(len(calls), 1)
                finally:
                    release.set()
                self.assertTrue(active.result(timeout=5)[0].startswith(b'%PDF-'))
            self.assertTrue(certificate_pdfs(['synthetic recipient'], render=render)[0].startswith(b'%PDF-'))
            render.assert_called_once_with('synthetic recipient')
            self.assertEqual(len(calls), 2)

    def test_render_failure_releases_capacity_without_partial_conversion(self):
        with patch('announcements.certificate_pdf._convert_documents', return_value=[b'%PDF-']) as convert:
            with self.assertRaisesMessage(ValueError, 'Synthetic rendering failure'):
                certificate_pdfs(['recipient'], render=Mock(side_effect=ValueError('Synthetic rendering failure')))
            convert.assert_not_called()
            self.assertEqual(certificate_pdfs([b'explicit retry']), [b'%PDF-'])
            convert.assert_called_once_with([b'explicit retry'])

    def test_batch_uses_one_private_conversion_and_keeps_recipient_order(self):
        folders = []

        def convert(command, **kwargs):
            folders.append(Path(command[command.index('--outdir') + 1]))
            self.assertTrue(command[1].startswith('-env:UserInstallation=file:'))
            self.assertIn('--headless', command)
            self.assertNotIn('shell', kwargs)
            self.assertEqual(kwargs['timeout'], 90)
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
        for error in (OSError('private path'), subprocess.TimeoutExpired('private member', 30),
                      subprocess.CalledProcessError(1, 'private command', output='private document'), None):
            with self.subTest(error=error), patch('announcements.certificate_pdf.subprocess.run', side_effect=error):
                with self.assertLogs('announcements.certificate_pdf', level='WARNING') as logs, self.assertRaises(ValidationError) as caught:
                    certificate_pdfs([b'document'])
                self.assertIn('PDF conversion failed', str(caught.exception))
                self.assertNotIn('private', str(caught.exception))
                self.assertNotIn('private', str(logs.output))
                category = ('io' if isinstance(error, OSError) or error is None else
                            'timeout' if isinstance(error, subprocess.TimeoutExpired) else 'process')
                self.assertEqual(logs.records[0].getMessage(),
                    f'Certificate conversion failed: category={category}; documents=1.')

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
