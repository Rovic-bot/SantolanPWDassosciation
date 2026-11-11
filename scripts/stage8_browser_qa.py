"""Fictional live-server browser QA in the verified isolated MySQL harness."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client

from ewaf.durable_testsupport import DurableHelpers
from ewaf.test_source_writers import SourceHelpers


class Stage8BrowserTests(SourceHelpers, DurableHelpers, StaticLiveServerTestCase):
    def test_private_development_forms_history_and_accessibility(self):
        self.setup_durable()
        self.request_run()
        client = Client()
        client.force_login(self.officer)
        self.register()
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='fictional-stage8-browser-') as output:
            process = subprocess.run(['node', str(root / 'scripts/stage8_browser_qa.cjs')], cwd=root,
                env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.program.pk),
                    'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME, 'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'QA_OUTPUT': output}, capture_output=True, text=True, encoding='utf-8', timeout=180)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            print(process.stdout)
            if os.environ.get('G12_ARTIFACT_DIR'):
                for name in ('stage8-mobile.png', 'stage8-desktop.png', 'stage8-history.png'):
                    shutil.copyfile(Path(output) / name, Path(os.environ['G12_ARTIFACT_DIR']) / name)
