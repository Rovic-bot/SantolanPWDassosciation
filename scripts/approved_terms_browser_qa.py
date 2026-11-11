"""Explicit browser QA; synthetic fixtures on the disposable MySQL test server."""
import os
from pathlib import Path
import subprocess
import tempfile

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client

from programs.test_approved_terms import TermsHelpers


class ApprovedTermsBrowserTests(TermsHelpers, StaticLiveServerTestCase):
    def test_private_terms_review_history_and_mobile_accessibility(self):
        self.setup_terms()
        binding = self.reconcile()
        client = Client()
        client.force_login(self.officer)
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='synthetic-terms-browser-') as output:
            result = subprocess.run(['node', str(root / 'scripts/approved_terms_browser_qa.cjs')], cwd=root,
                env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.program.pk),
                     'QA_REVISION': str(binding.revision_id), 'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
                     'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value, 'QA_OUTPUT': output},
                capture_output=True, text=True, encoding='utf-8', timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            print(result.stdout)
