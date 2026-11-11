"""Explicit headless-browser QA on synthetic disposable MySQL only."""
import os
from pathlib import Path
import subprocess
import shutil
import tempfile
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from ewaf.evidence_testsupport import EvidenceHelpers


class G12BrowserTests(EvidenceHelpers, StaticLiveServerTestCase):
    def test_private_review_readiness_history_and_accessibility(self):
        self.setup_evidence()
        self.prepare_relevance()
        self.assess()
        client = Client()
        client.force_login(self.officer)
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='synthetic-g12-browser-') as output:
            process = subprocess.run(['node', str(root / 'scripts/g12_browser_qa.cjs')], cwd=root,
                env={**os.environ, 'QA_URL': self.live_server_url, 'QA_APPLICATION': str(self.application.pk),
                     'QA_PROGRAM': str(self.program.pk), 'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
                     'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value, 'QA_OUTPUT': output},
                capture_output=True, text=True, encoding='utf-8', timeout=180)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            print(process.stdout)
            if os.environ.get('G12_ARTIFACT_DIR'):
                destination = Path(os.environ['G12_ARTIFACT_DIR']) / 'g12-history-mobile.png'
                shutil.copyfile(Path(output) / 'g12-history-mobile.png', destination)
                print(f'Synthetic browser screenshot: {destination}')
