"""Browser reproduction of two same-day deliveries during open registration."""
from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from assistance.models import AssistanceRelease, AssistanceLog
from ewaf.test_rolling_delivery import RollingDeliveryFixture
from ewaf.operational_models import OperationalDecision
from scripts.durable_test_runner import require_disposable


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class RollingReceiptBrowserTests(RollingDeliveryFixture, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def setUp(self):
        require_disposable()
        self.setup_delivery()

    def test_sequential_actual_receipt_buttons(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b, run = self.selected_pool()
            retained = deepcopy(run.payload())
            decisions = list(OperationalDecision.objects.filter(program=self.program).values())
        with patch('django.utils.timezone.now', return_value=self.open_at + timedelta(minutes=5)):
            output = Path(os.environ['G12_ARTIFACT_DIR']) / 'open-registration-receipt-browser'
            output.mkdir()
            result = subprocess.run(['node', 'scripts/open_registration_receipt_browser_qa.cjs'], env={**os.environ,
                'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                'QA_SESSION': self.client.cookies['sessionid'].value,
                'QA_ROUTE': reverse('assistance:program_releases', args=[self.program.pk]),
                'QA_APPLICANTS': json.dumps([str(a.pk), str(b.pk)])},
                capture_output=True, text=True, encoding='utf-8', timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(AssistanceRelease.objects.filter(application__program=self.program).count(), 2)
            self.assertEqual(AssistanceLog.objects.filter(application__program=self.program, action='assistance_released').count(), 2)
            run.refresh_from_db(); run.clean()
            self.assertEqual(run.payload(), retained)
            self.assertEqual(decisions, list(OperationalDecision.objects.filter(program=self.program).values()))
            (output / 'results.json').write_text(json.dumps({'same_day_deliveries_recorded': 2,
                'selection_and_ranking_unchanged': True, 'native_delivery_audits': 2,
                'registration_still_open': True, 'widths': [1440,390]}, indent=2), encoding='utf-8')
            print(result.stdout, flush=True)
