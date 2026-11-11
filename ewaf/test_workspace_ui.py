"""Private presentation and actual selection tests for the screenshot-based UI."""
from copy import deepcopy
import os
from pathlib import Path
import subprocess

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from assistance.models import AssistanceRelease
from assistance.services import record_release
from assistance.tests import release_data
from membership.tests import grant
from . import test_current_weights as fixture, operational_services as operational
from .operational_models import OperationalRun, OperationalDecision


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True,
    PDAO_ENFORCEMENT_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class WorkspaceUITests(StaticLiveServerTestCase):
    for _name in ('setUp', 'observe', 'handoff_form', 'register_members', 'program', 'publish',
                  'apply', 'history', 'save_weights', 'bind', 'findings', 'accept', 'generate',
                  'build', 'preview', 'approve', 'assert_scores'):
        locals()[_name] = getattr(fixture.CurrentWeightTests, _name)

    def test_browser_ranking_drawer_breakdown_and_selection_preserve_calculations(self):
        self.build('ses')
        run = self.generate()
        original = deepcopy(run.payload())
        app = self.apps['T02']
        operational.record_decision(self.target.pk, user=self.user, run_id=run.pk,
            application_id=app.pk, expected_revision=0, outcome='SELECTED', reason='Synthetic confirmed recipient.')
        record_release(app.pk, user=self.user, data=release_data(app))
        ledger = list(AssistanceRelease.objects.order_by('pk').values())
        browser = subprocess.run(['node', str(Path(settings.BASE_DIR) / 'scripts/ewaf_workspace_ui_browser.cjs')],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.target.pk),
                 'QA_USERNAME': self.user.username, 'QA_PASSWORD': 'synthetic-only',
                 'QA_REFERENCE': self.apps['T01'].public_reference},
            capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(browser.returncode, 0, browser.stdout + browser.stderr)
        print(browser.stdout)
        run.refresh_from_db()
        self.assertEqual(run.payload(), original)
        current = OperationalRun.objects.filter(program=self.target).first()
        self.assert_scores(current, 'ses', self.apps)
        self.assertEqual(OperationalRun.objects.count(), 2)
        self.assertEqual(OperationalDecision.objects.count(), 2)
        self.assertEqual(ledger, list(AssistanceRelease.objects.order_by('pk').values()))

    def test_drawer_filters_permissions_stale_inputs_and_no_script_fallback(self):
        self.build('balanced')
        run = self.generate()
        original = deepcopy(run.payload())
        url = reverse('ewaf:operational_workspace', args=[self.target.pk])
        iris = str(self.apps['T09'].pk)
        page = self.client.get(url, {'q': 'Iris'})
        self.assertEqual(page.context['result']['pool_size'], 12)
        self.assertEqual(page.context['result']['rows'].paginator.count, 1)
        row = page.context['result']['rows'][0]
        self.assertEqual(row['rank'], 7)
        self.assertEqual(row['accepted_information'][0]['value'], '\u20b137,000 / month')
        self.assertContains(page, 'Verified No')
        self.assertContains(self.client.get(url, {'review': iris}), 'open data-auto-open')
        self.assertEqual(self.client.get(url, {'review': 'not-in-this-run'}).status_code, 404)
        self.assertEqual(self.client.get(url, {'decision': 'selected'}).context['result']['rows'].paginator.count, 0)
        # Form POST remains the service boundary even when JavaScript is disabled.
        bad = self.client.post(url, {'action': 'SELECT_ASSISTANCE', 'decision-run_id': run.pk,
            'decision-application_id': iris, 'decision-expected_revision': 999})
        self.assertContains(bad, 'open data-auto-open')
        self.assertContains(bad, 'Decision changed')
        self.assertFalse(OperationalDecision.objects.exists())
        viewer = get_user_model().objects.create_user('synthetic-ui-readonly', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *operational.VIEW)
        self.client.force_login(viewer)
        page = self.client.get(url, {'review': iris})
        self.assertContains(page, 'Selection permission required')
        self.assertNotContains(page, 'name="action" value="SELECT_ASSISTANCE"')
        self.assertEqual(self.client.post(url, {'action': 'SELECT_ASSISTANCE', 'decision-run_id': run.pk,
            'decision-application_id': iris, 'decision-expected_revision': 0}).status_code, 403)
        self.client.force_login(self.user)
        self.approve('hm')
        stale = self.client.get(url, {'run': run.pk, 'review': iris})
        self.assertFalse(stale.context['result']['active'])
        self.assertContains(stale, 'Generate a current ranking before making a selection.')
        run.refresh_from_db()
        self.assertEqual(run.payload(), original)
        self.assertFalse(OperationalDecision.objects.exists())
