"""Real EWAF decisions and synthetic result-popup HTML in a disposable database."""
import json
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from announcements.generation import PERMISSIONS
from announcements.models import Announcement
from announcements.results import results_current
from announcements.test_selection_reason import REASON
from assistance.models import AssistanceRelease
from ewaf.operational_models import OperationalDecision
from ewaf import test_rolling_pool as fixtures
from membership.tests import grant
from programs.models import ProgramApplication
from scripts.durable_test_runner import require_disposable


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class ResultReasonFixtures(TransactionTestCase):
    setUp = fixtures.RollingPoolTests.setUp
    draft = fixtures.RollingPoolTests.draft
    approve = fixtures.RollingPoolTests.approve
    bind = fixtures.RollingPoolTests.bind
    publish = fixtures.RollingPoolTests.publish
    applicant = fixtures.RollingPoolTests.applicant
    generate = fixtures.RollingPoolTests.generate

    def test_real_selection_unchanged_and_popup_fixtures(self):
        require_disposable()
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.publish()
            applications = [self.applicant(f'REASON-UI-{i}', low=i == 0,
                employment_status=('unemployed', 'retired', 'employed')[i],
                household_members=6 - i * 2,
                household_monthly_income=('0', '1000', '100000')[i]) for i in range(3)]
            for application, name in zip(applications, ('Andrea Santos', 'Miguel Dela Cruz', 'Patricia Reyes')):
                application.member.full_name = name
                application.member.save(update_fields=['full_name'])
            run = self.generate()
            selection_url = reverse('ewaf:operational_workspace', args=[self.program.pk]) + f'?run={run.pk}'
            for application in applications[:1]:
                response = self.client.post(selection_url, {'action': 'SELECT_ASSISTANCE',
                    'decision-run_id': run.pk, 'decision-application_id': str(application.pk),
                    'decision-expected_revision': 0})
                self.assertEqual(response.status_code, 302,
                    str(response.context and response.context['result']['submitted'].errors))
            self.assertEqual(OperationalDecision.objects.filter(outcome='SELECTED').count(), 1)
            grant(self.user, *PERMISSIONS)
            before = list(ProgramApplication.objects.filter(program=self.program).values())
            decisions = list(OperationalDecision.objects.filter(program=self.program).values())
            calculation = deepcopy(run.payload())
            url = reverse('announcements:prepare_results', args=[self.program.pk])
            preview = self.client.get(url)
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.context['review_pool']['selected_count'], 1)
            output = Path('.local/result-reason-synthetic')
            output.mkdir(parents=True, exist_ok=True)
            output.joinpath('preview.html').write_bytes(preview.content)
            plan = preview.context['preview']
            data = {'action': 'PUBLISH_RECORDED_RESULTS', 'expected': plan['expected'], 'version': plan['version']}
            errors = self.client.post(url, {**data, 'selection_reason': ' '})
            self.assertIn('selection_reason', errors.context['generation_form'].errors)
            output.joinpath('errors.html').write_bytes(errors.content)
            self.assertFalse(Announcement.objects.filter(program=self.program).exists())
            with patch('announcements.certificate_delivery.queue_certificates') as queue:
                published = self.client.post(url, {**data, 'selection_reason': REASON},
                    HTTP_X_ANNOUNCEMENT_DIALOG='1', follow=True)
                queue.assert_called_once()
            self.assertContains(published, 'Program results published.')
            output.joinpath('published.html').write_bytes(published.content)
            item = Announcement.objects.get(program=self.program)
            self.assertTrue(results_current(item))
            self.assertEqual(len(item.result_revision.public_payload['rows']), 1)
            self.assertEqual(item.result_revision.public_payload['selection_reason'], REASON)
            stale = self.client.post(url, {**data, 'selection_reason': REASON})
            self.assertContains(stale, 'recorded results changed')
            output.joinpath('stale.html').write_bytes(stale.content)
            self.assertEqual(item.result_revisions.count(), 1)
            self.assertEqual(list(ProgramApplication.objects.filter(program=self.program).values()), before)
            self.assertEqual(list(OperationalDecision.objects.filter(program=self.program).values()), decisions)
            run.refresh_from_db()
            self.assertEqual(run.payload(), calculation)
            self.assertFalse(AssistanceRelease.objects.filter(application__program=self.program).exists())
            public_url = reverse('core:announcements') + '?category=results'
            public = self.client.get(public_url)
            self.assertContains(public, REASON)
            for app in applications:
                self.assertNotContains(public, app.member.full_name)
            output.joinpath('public.html').write_bytes(public.content)
            output.joinpath('manifest.json').write_text(json.dumps({'preview': url,
                'public': public_url, 'reason': REASON}, indent=2), encoding='utf-8')
