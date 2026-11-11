"""Explicit browser QA, synthetic fixture and disposable test server only."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from ewaf.evidence_testsupport import EvidenceHelpers
from ewaf.configuration_testsupport import ConfigurationHelpers
from ewaf.scoring_testsupport import ScoringHelpers


class G15BrowserTests(ScoringHelpers, ConfigurationHelpers, EvidenceHelpers, StaticLiveServerTestCase):
    def test_proposal_readiness_history_and_accessibility(self):
        self.setup_scoring()
        client = Client()
        client.force_login(self.officer)
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='synthetic-g15-browser-') as output:
            process = subprocess.run(['node', str(root / 'scripts/g15_browser_qa.cjs')], cwd=root,
                env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.program.pk),
                    'QA_APPLICATION': str(self.application.pk), 'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
                    'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value, 'QA_OUTPUT': output},
                capture_output=True, text=True, encoding='utf-8', timeout=180)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            print(process.stdout)
            if os.environ.get('G12_ARTIFACT_DIR'):
                shutil.copyfile(Path(output) / 'g15-readiness-mobile.png', Path(os.environ['G12_ARTIFACT_DIR']) / 'g15-readiness-mobile.png')
