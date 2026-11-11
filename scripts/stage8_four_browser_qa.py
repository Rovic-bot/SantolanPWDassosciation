"""Live four-criterion Admin browser exercise in fresh disposable MySQL."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client
from ewaf.four_testsupport import FourHelpers
from ewaf.test_source_writers import SourceHelpers
from ewaf import generation_processing as processing


class FourBrowserTests(SourceHelpers, FourHelpers, StaticLiveServerTestCase):
    def test_verified_application_workflow_and_accessibility(self):
        self.setup_durable()
        self.add_four_ready_applicant()
        client = Client()
        client.force_login(self.officer)
        self.register()
        self.install_four()
        context = processing.inspect_context(self.program.pk, user=self.officer, contract=self.contract)
        processing.accept_request(self.program.pk, user=self.officer, contract=self.contract,
            request_key='four-browser-contract', expected=context['expected'], expected_context=context['context_digest'],
            reason='Fictional browser evaluation contract')
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='fictional-four-browser-') as output:
            process = subprocess.run(['node', str(root / 'scripts/stage8_four_browser_qa.cjs')], cwd=root,
                env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.program.pk),
                    'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME, 'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'QA_OUTPUT': output}, capture_output=True, text=True, encoding='utf-8', timeout=180)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            print(process.stdout)
            if os.environ.get('G12_ARTIFACT_DIR'):
                for name in ('four-mobile.png', 'four-desktop.png', 'four-history.png'):
                    shutil.copyfile(Path(output) / name, Path(os.environ['G12_ARTIFACT_DIR']) / name)
