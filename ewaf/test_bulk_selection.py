"""Checked human selections against fictional records in a disposable database."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import os
from pathlib import Path
import subprocess
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse

from assistance.models import AssistanceCase, AssistanceRelease
from announcements.models import ProgramResultRevision
from membership.tests import grant
from programs.models import ProgramLog
from programs.tests import create_program
from . import operational_services as service
from .operational_forms import BulkSelectAssistanceForm
from .operational_models import OperationalDecision as Decision
from .operational_testsupport import OperationalHelpers


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class BulkSelectionTests(OperationalHelpers, TransactionTestCase):
    reason = BulkSelectAssistanceForm.audit_reason

    def prepare(self, slots=3, **policy):
        # Set capacity before evidence and approved terms are created.
        with patch('ewaf.evidence_testsupport.create_program',
                   side_effect=lambda **values: create_program(**{**values, 'slots': slots})):
            self.setup_operational(additional=2)
        self.lock_policy(**policy)
        self.run = self.calculate()
        self.url = reverse('ewaf:operational_workspace', args=[self.program.pk])
        self.client.force_login(self.officer)

    def selections(self, helpers=None):
        return [{'application_id': str(helper.application.pk), 'expected_revision': 0,
                 'tie_reason': 'Fictional application of the approved human tie procedure.'}
                for helper in (helpers if helpers is not None else self.helpers[:2])]

    def select(self, selections=None, **changes):
        return service.select_assistance_batch(self.program.pk, **{
            'user': self.officer, 'run_id': self.run.pk, 'reason': self.reason,
            'selections': selections if selections is not None else self.selections(), **changes})

    def post_data(self, selections=None, **changes):
        rows = selections if selections is not None else self.selections()
        values = {'action': 'BULK_SELECT_ASSISTANCE', 'bulk-run_id': self.run.pk,
                  'bulk-applications': [row['application_id'] for row in rows]}
        for row in rows:
            values['bulk-revision-' + row['application_id']] = row['expected_revision']
            values['bulk-tie-' + row['application_id']] = row.get('tie_reason', '')
        return {**values, **changes}

    def assert_rolled_back(self, operation, message=None):
        before = (list(Decision.objects.order_by('pk').values()),
                  list(ProgramLog.objects.order_by('pk').values()))
        with self.assertRaises(ValidationError) as caught:
            operation()
        if message:
            self.assertIn(message, str(caught.exception))
        self.assertEqual(list(Decision.objects.order_by('pk').values()), before[0])
        self.assertEqual(list(ProgramLog.objects.order_by('pk').values()), before[1])

    def test_success_and_retry_preserve_scores_release_publication_and_individual_flow(self):
        self.prepare()
        original = deepcopy(self.run.payload())
        cases = list(AssistanceCase.objects.order_by('pk').values())
        publications = list(ProgramResultRevision.objects.order_by('pk').values())
        selected = self.select()
        self.assertEqual(len(selected), 2)
        for decision in selected:
            decision.clean()
            self.assertEqual(decision.outcome, 'SELECTED')
            self.assertEqual(decision.audit_entry.actor_id, self.officer.pk)
        audit_count = ProgramLog.objects.count()
        self.assertEqual([row.pk for row in self.select()], [row.pk for row in selected])
        self.assertEqual(ProgramLog.objects.count(), audit_count)
        # The individual selection path uses the same rules and retains its retry.
        single = self.choose(self.run, application_id=self.helpers[2].application.pk)
        self.assertEqual(self.choose(self.run, application_id=self.helpers[2].application.pk).pk, single.pk)
        self.assertEqual(Decision.objects.count(), 3)
        self.assertEqual(list(AssistanceCase.objects.order_by('pk').values()), cases)
        self.assertFalse(AssistanceRelease.objects.exists())
        self.assertEqual(list(ProgramResultRevision.objects.order_by('pk').values()), publications)
        self.assertEqual(len(mail.outbox), 0)
        self.run.refresh_from_db()
        self.assertEqual(self.run.payload(), original)

    def test_capacity_failure_on_second_applicant_rolls_back_first_decision_and_audit(self):
        self.prepare(slots=1)
        self.assert_rolled_back(self.select, 'slots')

    def test_stale_revision_and_foreign_applicant_roll_back_whole_batch(self):
        self.prepare()
        rows = self.selections()
        rows[1]['expected_revision'] = 7
        self.assert_rolled_back(lambda: self.select(rows), 'Decision changed')
        rows[1].update(expected_revision=0, application_id=str(uuid4()))
        self.assert_rolled_back(lambda: self.select(rows), 'eligible application')

    def test_duplicate_malformed_empty_and_oversized_batches_are_rejected(self):
        self.prepare()
        row = self.selections()[0]
        for rows in ([], [row, row], [row] * 51,
                     [{**row, 'expected_revision': True}], [{**row, 'application_id': 'invalid'}]):
            with self.subTest(rows=rows[:1]):
                self.assert_rolled_back(lambda: self.select(rows))

    def test_permissions_are_checked_on_server_even_with_valid_form(self):
        self.prepare()
        viewer = get_user_model().objects.create_user('fictional_bulk_reader', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *service.VIEW, 'ewaf.decide_operational')
        with self.assertRaises(PermissionDenied):
            self.select(user=viewer)
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(self.url, self.post_data()).status_code, 403)
        page = self.client.get(self.url)
        self.assertNotContains(page, 'id="bulk-assistance-form"')
        self.assertTrue(all(not row['bulk_selectable'] for row in page.context['result']['rows']))
        self.assertFalse(Decision.objects.exists())

    def test_reasoned_tie_requires_each_explanation_and_held_ties_stay_unavailable(self):
        self.prepare()
        rows = self.selections()
        rows[1]['tie_reason'] = ''
        self.assert_rolled_back(lambda: self.select(rows), 'tie_reason')
        self.lock_policy(tie_rule='hold')
        self.run = self.calculate()
        self.assert_rolled_back(self.select, 'tie_rule')
        page = self.client.get(self.url)
        tied = [row for row in page.context['result']['rows'] if row['tie_review']]
        self.assertEqual(len(tied), 2)
        self.assertTrue(all(row['tie_held'] and not row['bulk_selectable'] for row in tied))

    def test_stale_run_and_final_freshness_failure_roll_back_all_audits(self):
        self.prepare()
        old = self.run
        self.run = self.calculate()
        self.assert_rolled_back(lambda: self.select(run_id=old.pk), 'current complete')
        original, calls = service.current_result_run, []
        def check(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise ValidationError('Fictional final freshness failure')
            return original(*args, **kwargs)
        with patch.object(service, 'current_result_run', side_effect=check):
            self.assert_rolled_back(self.select, 'final freshness')
        self.assertEqual(len(calls), 2)

    def test_previous_run_selection_reserves_capacity_and_can_be_reconfirmed(self):
        self.prepare(slots=1)
        self.select(self.selections(self.helpers[:1]))
        self.run = self.calculate()
        page = self.client.get(self.url)
        self.assertEqual(page.context['result']['remaining_slots'], 0)
        held = next(row for row in page.context['result']['rows'] if row['application'] == str(self.application.pk))
        self.assertTrue(held['bulk_selectable'])
        self.assertEqual(held['bulk_slot_needed'], 0)
        self.assert_rolled_back(lambda: self.select(self.selections(self.helpers[1:])), 'slots')
        rows = self.selections(self.helpers[:1])
        rows[0]['expected_revision'] = 1
        self.assertEqual(self.select(rows)[0].revision, 2)

    def test_retained_legacy_selection_reserves_capacity(self):
        self.prepare(slots=1)
        # Adoption validation itself is covered in programs.test_mandatory_ewaf.
        # This boundary fixture represents its retained selection outside the
        # current scored candidates, which must still consume a real slot.
        retained = uuid4()
        with patch('programs.mandatory_ewaf.retained_selected_ids', side_effect=lambda program: {retained}):
            self.assert_rolled_back(self.select, 'slots')
            self.assertEqual(self.client.get(self.url).context['result']['remaining_slots'], 0)

    def test_final_ranking_timing_is_enforced(self):
        self.prepare()
        with patch('ewaf.revised.rolling_pool.selection_waiting', return_value=True):
            self.assert_rolled_back(self.select, 'final ranking')
            page = self.client.get(self.url)
            self.assertFalse(page.context['result']['bulk_available'])
            self.assertTrue(all(not row['bulk_selectable'] for row in page.context['result']['rows']))

    def test_http_post_validates_run_revision_csrf_and_disables_selected_rows(self):
        self.prepare()
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.officer)
        self.assertEqual(protected.post(self.url, self.post_data()).status_code, 403)
        self.assertFalse(Decision.objects.exists())
        self.assertContains(self.client.get(self.url), 'Select all applies only to selectable applicants on this page')
        mismatch = self.client.post(self.url, self.post_data(**{'bulk-run_id': self.run.pk + 1}))
        self.assertContains(mismatch, 'No applicants were selected.')
        self.assertFalse(Decision.objects.exists())
        stale = self.post_data()
        stale['bulk-revision-' + str(self.helpers[1].application.pk)] = 999
        self.assertContains(self.client.post(self.url, stale), 'Decision changed')
        self.assertFalse(Decision.objects.exists())
        response = self.client.post(self.url, self.post_data())
        self.assertEqual(response.status_code, 302)
        page = self.client.get(response.url)
        self.assertContains(page, '2 checked applicants selected for assistance.')
        self.assertEqual(page.context['result']['remaining_slots'], 1)
        selected = [row for row in page.context['result']['rows'] if row['is_selected']]
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(not row['bulk_selectable'] for row in selected))

    def test_concurrent_checked_batches_cannot_overbook_one_slot(self):
        self.prepare(slots=1)
        barrier = Barrier(2)
        def worker(helper):
            close_old_connections()
            try:
                barrier.wait(timeout=20)
                try:
                    return self.select(self.selections([helper]))[0].pk
                except ValidationError as error:
                    return error.messages
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, helper) for helper in self.helpers[:2]]
            outcomes = [future.result(timeout=60) for future in futures]
        self.assertEqual(sum(isinstance(value, int) for value in outcomes), 1, outcomes)
        self.assertEqual(Decision.objects.filter(outcome='SELECTED').count(), 1)
        Decision.objects.get().clean()


class BulkSelectionBrowserTests(OperationalHelpers, StaticLiveServerTestCase):
    def test_capacity_tie_review_selection_filters_and_mobile_layout(self):
        with patch('ewaf.evidence_testsupport.create_program',
                   side_effect=lambda **values: create_program(**{**values, 'slots': 2})):
            self.setup_operational(additional=2)
        self.officer.set_password('fictional-bulk-browser-only')
        self.officer.save(update_fields=['password'])
        self.lock_policy()
        run = self.calculate()
        original = deepcopy(run.payload())
        cases = list(AssistanceCase.objects.order_by('pk').values())
        browser = subprocess.run(['node', str(Path(settings.BASE_DIR) / 'scripts/ewaf_bulk_selection_browser.cjs')],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.program.pk),
                 'QA_USERNAME': self.officer.username, 'QA_PASSWORD': 'fictional-bulk-browser-only',
                 'FEATURE_ARTIFACT_DIR': str(Path(settings.BASE_DIR) / '.local/review/artifacts')},
            capture_output=True, text=True, encoding='utf-8', timeout=150)
        self.assertEqual(browser.returncode, 0, browser.stdout + browser.stderr)
        print(browser.stdout)
        self.assertEqual(Decision.objects.filter(outcome='SELECTED').count(), 2)
        self.assertEqual(list(AssistanceCase.objects.order_by('pk').values()), cases)
        self.assertFalse(AssistanceRelease.objects.exists())
        self.assertFalse(ProgramResultRevision.objects.exists())
        run.refresh_from_db()
        self.assertEqual(run.payload(), original)
