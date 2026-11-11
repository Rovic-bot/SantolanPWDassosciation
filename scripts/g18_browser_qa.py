"""Explicit G18 browser QA: isolated synthetic MySQL and private test storage."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from ewaf.evidence_testsupport import EvidenceHelpers


class G18BrowserTests(EvidenceHelpers, StaticLiveServerTestCase):
    def test_policy_review_and_existing_preparatory_workflow(self):
        self.setup_evidence()
        client = Client()
        client.force_login(self.officer)
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='synthetic-g18-browser-') as output:
            process = subprocess.run(['node', str(root / 'scripts/g18_browser_qa.cjs')], cwd=root,
                env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.program.pk),
                    'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME, 'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'QA_OUTPUT': output}, capture_output=True, text=True, encoding='utf-8', timeout=180)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            print(process.stdout)
            if os.environ.get('G12_ARTIFACT_DIR'):
                for name in ('g18-policy-mobile.png', 'g18-policy-desktop.png', 'g18-draft-mobile.png'):
                    destination = Path(os.environ['G12_ARTIFACT_DIR']) / name
                    shutil.copyfile(Path(output) / name, destination)
                    print(f'Synthetic G18 screenshot: {destination}')
