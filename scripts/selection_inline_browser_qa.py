"""Exercise inline selection only on a guarded disposable MySQL database."""
from copy import deepcopy
import os
from pathlib import Path
import subprocess
from unittest.mock import patch

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from assistance.models import AssistanceRelease
from ewaf import test_rolling_pool as fixtures
from ewaf.operational_models import OperationalDecision
from scripts.durable_test_runner import require_disposable


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class InlineSelectionBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'
    draft = fixtures.RollingPoolTests.draft
    approve = fixtures.RollingPoolTests.approve
    bind = fixtures.RollingPoolTests.bind
    publish = fixtures.RollingPoolTests.publish
    applicant = fixtures.RollingPoolTests.applicant
    generate = fixtures.RollingPoolTests.generate
    pool = fixtures.RollingPoolTests.pool

    def setUp(self):
        require_disposable()
        fixtures.RollingPoolTests.setUp(self)

    def test_selection_updates_without_navigation_or_scroll(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            applicant, other = self.pool()
            run = self.generate()
            retained = deepcopy(run.payload())
            output = Path(os.environ['G12_ARTIFACT_DIR']) / 'inline-selection-browser'
            output.mkdir()
            route = reverse('ewaf:operational_workspace', args=[self.program.pk])
            result = subprocess.run(['node', 'scripts/selection_inline_browser_qa.cjs'], env={**os.environ,
                'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                'QA_SESSION': self.client.cookies['sessionid'].value,
                'QA_NAME': applicant.member.full_name,
                'QA_ROUTE': route + f'?run={run.pk}&review={applicant.pk}'},
                capture_output=True, text=True, encoding='utf-8', timeout=180)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            decisions = list(OperationalDecision.objects.filter(program=self.program).order_by('revision'))
            self.assertEqual([item.outcome for item in decisions],
                ['SELECTED', 'DEFERRED', 'SELECTED', 'DEFERRED', 'SELECTED', 'DEFERRED', 'SELECTED'])
            for decision in decisions:
                self.assertEqual(decision.application_id, applicant.pk)
                decision.clean()
            run.refresh_from_db(); run.clean()
            self.assertEqual(run.payload(), retained)
            self.assertFalse(AssistanceRelease.objects.filter(application__program=self.program).exists())
            print(result.stdout, flush=True)
