import os
from pathlib import Path
import subprocess
from datetime import timedelta

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from documents.services import verify_document
from ewaf.operational_testsupport import OperationalHelpers


class InlineDocumentBrowserTests(OperationalHelpers, StaticLiveServerTestCase):
    def test_review_without_leaving_applicant_page(self):
        self.setup_operational()
        verify_document(self.document.pk, user=self.officer, member_version=self.member.version,
            verified=False, expires_on=None, reason='Fictional document awaiting one-click review.')
        expired = self.member.application.documents.exclude(pk=self.document.pk).first()
        verify_document(expired.pk, user=self.officer, member_version=self.member.version,
            verified=False, expires_on=timezone.localdate() - timedelta(days=1),
            reason='Fictional expired document for validation testing.')
        before = self.document.verifications.count()
        client = Client()
        client.force_login(self.officer)
        root = Path(settings.BASE_DIR)
        output = root / '.local/inline-documents/browser'
        output.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(['node', str(root / 'scripts/inline_document_browser_qa.cjs')], cwd=root,
            env={**os.environ, 'QA_URL': self.live_server_url,
                 'QA_APPLICATION': reverse('programs:application_detail', args=[self.program.pk, self.application.pk]),
                 'QA_DOCUMENT': str(self.document.pk), 'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
                 'QA_EXPIRED_DOCUMENT': str(expired.pk),
                 'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value, 'QA_OUTPUT': str(output)},
            capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.assertEqual(self.document.verifications.count(), before + 1)
        self.assertTrue(self.document.verifications.first().verified)
        self.assertFalse(expired.verifications.first().verified)
