"""Actual operational Admin forms with explicitly fictional MySQL records."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from ewaf.operational_testsupport import OperationalHelpers
from ewaf import operational_services as service
from ewaf.four_criterion_development import ahp


@override_settings(EWAF_FICTIONAL_DEMO=True)
class OperationalBrowserTests(OperationalHelpers, StaticLiveServerTestCase):
    def test_configuration_calculation_history_and_reasoned_human_decisions(self):
        from ewaf.operational_models import OperationalConfiguration, OperationalRun, OperationalDecision
        from assistance.models import AssistanceRelease
        self.setup_operational(additional=3)
        service.record_configuration(self.program.pk, user=self.officer, expected=service.configuration_token(self.program),
            proposed=self.proposal, judgments=ahp()['pairs'], status='DRAFT', reason='Fictional complete policy draft for browser verification')
        client = Client()
        client.force_login(self.officer)
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix='fictional-operational-browser-') as output:
            process = subprocess.run(['node', str(root / 'scripts/ewaf_operational_browser_qa.cjs')], cwd=root,
                env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.program.pk),
                    'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME, 'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value,
                    'QA_OUTPUT': output}, capture_output=True, text=True, encoding='utf-8', timeout=300)
            if os.environ.get('G12_ARTIFACT_DIR'):
                for name in Path(output).glob('operational-*.png'):
                    shutil.copyfile(name, Path(os.environ['G12_ARTIFACT_DIR']) / name.name)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            print(process.stdout)
        self.assertEqual(OperationalConfiguration.objects.first().status, 'LOCKED')
        self.assertEqual(OperationalRun.objects.count(), 2)
        self.assertEqual(OperationalDecision.objects.count(), 2)
        self.assertFalse(AssistanceRelease.objects.exists())
        runs = list(OperationalRun.objects.order_by('revision'))
        self.assertEqual(runs[1].previous_id, runs[0].pk)
        for run in runs:
            run.clean()
            for calculation in run.calculations.values():
                self.assertEqual([trace['criterion'] for trace in calculation['traces']], ['SI', 'ES', 'PA', 'ND'])
