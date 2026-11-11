"""Fictional verified pool, calculations, saved decisions and history in Admin."""
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


class ReadinessBrowserTests(SourceHelpers, FourHelpers, StaticLiveServerTestCase):
    def test_four_result_review_saved_decision_and_history(self):
        from programs.testsupport import application_fixture
        from members.tests import create_member
        from ewaf.decision_models import DevelopmentHumanDecision, DevelopmentHumanDecisionAudit
        from assistance.models import AssistanceRelease
        self.setup_durable()
        self.add_four_ready_applicant('FICTIONAL-BROWSER-HIGH-A', income='60', dependents=5)
        self.add_four_ready_applicant('FICTIONAL-BROWSER-HIGH-B', income='60', dependents=5)
        self.add_four_ready_applicant('FICTIONAL-BROWSER-MIDDLE', income='20', dependents=2)
        client = Client()
        client.force_login(self.officer)
        self.register()
        self.install_four()
        application_fixture(self.program, create_member('FICTIONAL-BROWSER-LATE-PENDING'))
        context = processing.inspect_context(self.program.pk, user=self.officer, contract=self.contract)
        processing.accept_request(self.program.pk, user=self.officer, contract=self.contract,
            request_key='readiness-browser-contract', expected=context['expected'], expected_context=context['context_digest'],
            reason='Fictional browser contract with explicitly retained late application')
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='fictional-readiness-browser-') as output:
            process = subprocess.run(['node', str(root / 'scripts/stage8_readiness_browser_qa.cjs')], cwd=root,
                env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.program.pk),
                    'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME, 'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'QA_OUTPUT': output}, capture_output=True, text=True, encoding='utf-8', timeout=240)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            print(process.stdout)
            if os.environ.get('G12_ARTIFACT_DIR'):
                for name in Path(output).glob('readiness-*.png'):
                    shutil.copyfile(name, Path(os.environ['G12_ARTIFACT_DIR']) / name.name)
        self.assertEqual(DevelopmentHumanDecision.objects.count(), 2)
        self.assertEqual(DevelopmentHumanDecisionAudit.objects.count(), 2)
        self.assertFalse(AssistanceRelease.objects.exists())
