"""Published and newly selected recipients in the same disposable EWAF program."""
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from announcements.testsupport import publish_selection
from assistance.models import AssistanceRelease
from ewaf import operational_services
from ewaf.test_rolling_delivery import RollingDeliveryFixture
from scripts.durable_test_runner import require_disposable


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class PublicationReceiptBrowserTests(RollingDeliveryFixture, StaticLiveServerTestCase):
    host = '127.0.0.1'

    def setUp(self):
        require_disposable()
        self.setup_delivery()

    def test_new_selection_waits_for_republication(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b = self.pool()
            run = self.generate()
            def select(app):
                operational_services.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                    application_id=app.pk, expected_revision=0, outcome='SELECTED', reason='SYNTHETIC publication gate')
            select(a)
            first = publish_selection(self.program, self.user)
            select(b)
            output = Path(os.environ['G12_ARTIFACT_DIR']) / 'publication-receipt-browser'
            output.mkdir()
            for phase in ('before', 'after'):
                if phase == 'after':
                    second = publish_selection(self.program, self.user)
                result = subprocess.run(['node', 'scripts/publication_receipt_browser_qa.cjs'], env={**os.environ,
                    'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output), 'QA_PHASE': phase,
                    'QA_SESSION': self.client.cookies['sessionid'].value,
                    'QA_ROUTE': reverse('assistance:program_releases', args=[self.program.pk]),
                    'QA_APPLICANTS': json.dumps([str(a.pk), str(b.pk)])},
                    capture_output=True, text=True, encoding='utf-8', timeout=90)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(AssistanceRelease.objects.count(), 2)
            self.assertEqual(AssistanceRelease.objects.get(application=a).approval_snapshot['result_publication']['revision'], first.result_revision_id)
            self.assertEqual(AssistanceRelease.objects.get(application=b).approval_snapshot['result_publication']['revision'], second.result_revision_id)
            (output / 'results.json').write_text(json.dumps({'previously_published_can_record': True,
                'new_selection_disabled_until_republished': True, 'published_receipts_recorded': 2,
                'receipt_publication_witnesses_verified': True, 'widths': [1440,390]}, indent=2), encoding='utf-8')
