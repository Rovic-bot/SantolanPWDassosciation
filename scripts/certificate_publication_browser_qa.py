"""Exercise certificate publication in an isolated browser/database, without email."""
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from announcements import test_certificate_delivery as fixtures
from announcements.certificate_models import SelectionCertificateEmail
from announcements.models import Announcement
from scripts.durable_test_runner import require_disposable


@override_settings(CERTIFICATE_RESEND_ENABLED=False, CERTIFICATE_EMAIL_BACKGROUND=False)
class CertificatePublicationBrowserTests(fixtures.OperationalHelpers, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_publish_queues_private_personalized_certificate(self):
        require_disposable()
        fixtures.CertificateDeliveryTests.setUp(self)
        self.member.email = 'fictional-member@example.invalid'
        self.member.save()
        output = Path(os.environ['G12_ARTIFACT_DIR']) / 'certificate-browser'
        output.mkdir()
        result = subprocess.run(['node', 'scripts/certificate_publication_browser_qa.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                 'QA_SESSION': self.client.cookies['sessionid'].value,
                 'QA_PREVIEW': reverse('announcements:prepare_results', args=[self.program.pk])},
            capture_output=True, text=True, encoding='utf-8', timeout=120,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(Announcement.objects.get().status, 'published')
        job = SelectionCertificateEmail.objects.get()
        self.assertEqual(job.recipient, 'fictional-member@example.invalid')
        self.assertEqual(job.state, 'blocked')
        self.assertEqual(job.attempt_count, 0)
        self.assertFalse(job.attempts.exists())
        print(result.stdout, flush=True)
