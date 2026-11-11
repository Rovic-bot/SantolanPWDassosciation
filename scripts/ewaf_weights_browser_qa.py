"""Weight-input interaction on the actual Admin route with disposable records."""
from copy import deepcopy
import os
from pathlib import Path
import subprocess

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from ewaf.operational_testsupport import OperationalHelpers
from ewaf.operational_models import OperationalConfiguration


@override_settings(EWAF_FICTIONAL_DEMO=True)
class WeightBrowserTests(OperationalHelpers, StaticLiveServerTestCase):
    def test_cascade_preview_authorization_and_retained_history(self):
        self.setup_operational()
        original = self.lock_policy()
        run = self.calculate()
        original_payload, original_scores = deepcopy(original.payload()), deepcopy(run.calculations)
        client = Client()
        client.force_login(self.officer)
        root = Path(__file__).resolve().parents[1]
        output = root / '.local/ui-qa/ewaf-weights'
        output.mkdir(parents=True, exist_ok=True)
        process = subprocess.run(['node', str(root / 'scripts/ewaf_weights_browser_qa.cjs')],
            cwd=root, env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.program.pk),
                'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME, 'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value,
                'QA_OUTPUT': str(output)}, capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        print(process.stdout)
        self.assertEqual(OperationalConfiguration.objects.count(), 2)
        latest = OperationalConfiguration.objects.first()
        self.assertEqual(latest.status, 'LOCKED')
        self.assertEqual(latest.policy['weight_input']['proposal']['order'], ['SI', 'ND', 'ES', 'PA'])
        latest.clean()
        original.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual(original.payload(), original_payload)
        self.assertEqual(run.calculations, original_scores)
        run.clean()
