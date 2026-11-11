"""Select during open registration using fictional data in disposable MySQL."""
from copy import deepcopy
import json
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
from ewaf.revised import rolling_pool
from scripts.durable_test_runner import require_disposable


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class OpenRegistrationSelectionBrowserTests(StaticLiveServerTestCase):
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

    def test_select_while_registration_is_open(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            applicant, other = self.pool()
            run = self.generate()
            retained = deepcopy(run.payload())
            schedule = (self.program.registration_opens_at, self.program.registration_closes_at)
            output = Path(os.environ['G12_ARTIFACT_DIR']) / 'open-registration-selection-browser'
            output.mkdir()
            route = reverse('ewaf:operational_workspace', args=[self.program.pk])
            result = subprocess.run(['node', 'scripts/open_registration_selection_browser_qa.cjs'], env={**os.environ,
                'QA_URL': self.live_server_url, 'QA_OUTPUT': str(output),
                'QA_SESSION': self.client.cookies['sessionid'].value,
                'QA_ROUTE': route + f'?run={run.pk}&review={applicant.pk}'},
                capture_output=True, text=True, encoding='utf-8', timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            decision = OperationalDecision.objects.get(program=self.program)
            self.assertEqual(decision.application_id, applicant.pk)
            self.assertEqual(decision.outcome, 'SELECTED')
            self.assertEqual(decision.review['selection_timing']['rule'], rolling_pool.SELECTION_RULE)
            self.assertIs(decision.review['selection_timing']['registration_open'], True)
            decision.clean()
            run.refresh_from_db(); run.clean()
            self.assertEqual(run.payload(), retained)
            self.program.refresh_from_db()
            self.assertEqual((self.program.registration_opens_at, self.program.registration_closes_at), schedule)
            self.assertFalse(AssistanceRelease.objects.filter(application__program=self.program).exists())
            (output / 'results.json').write_text(json.dumps({'selection_before_close': True,
                'selected_decisions': 1, 'score_and_ranking_unchanged': True, 'schedule_unchanged': True,
                'assistance_release_created': False, 'widths': [1440,390,320]}, indent=2), encoding='utf-8')
            print(result.stdout, flush=True)
