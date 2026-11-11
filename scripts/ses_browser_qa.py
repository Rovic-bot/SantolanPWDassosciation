"""SES Admin browser checks; fresh disposable MySQL and synthetic media only."""
import os
from pathlib import Path
import subprocess

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from ewaf import dataset_methods as methods, test_ses_workflow as fixture


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class SesBrowserTests(StaticLiveServerTestCase):
    draft = fixture.SesWorkflowTests.draft
    approve = fixture.SesWorkflowTests.approve
    bind = fixture.SesWorkflowTests.bind
    publish = fixture.SesWorkflowTests.publish
    applicant = fixture.SesWorkflowTests.applicant
    accept = fixture.SesWorkflowTests.accept
    pool = fixture.SesWorkflowTests.pool
    generate = fixture.SesWorkflowTests.generate

    def setUp(self):
        fixture.SesWorkflowTests.setUp(self)

    def test_four_criterion_controls_keyboard_and_historical_admin_screens(self):
        a, _, _, _ = self.pool()
        self.generate()
        root = Path(__file__).resolve().parents[1]
        env = {**os.environ, 'SES_QA_URL': self.live_server_url,
            'SES_QA_SESSION': self.client.cookies['sessionid'].value,
            'SES_QA_VAULT': reverse('ewaf:vault') + '?method=' + methods.SES,
            'SES_QA_OLD_VAULT': reverse('ewaf:vault') + '?method=' + methods.HOUSEHOLD,
            'SES_QA_POLICY': reverse('ewaf:dataset_policies') + '?method=' + methods.SES,
            'SES_QA_INPUTS': reverse('ewaf:dataset_inputs', args=[a.pk]),
            'SES_QA_BREAKDOWN': reverse('ewaf:operational_breakdown', args=[self.program.pk])}
        result = subprocess.run(['node', str(root / 'scripts/ses_browser_qa.cjs')], cwd=root, env=env,
            capture_output=True, text=True, encoding='utf-8', timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
