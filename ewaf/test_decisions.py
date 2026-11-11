"""Saved fictional decisions: immutable revisions, atomic audits and protected use."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from copy import deepcopy
from datetime import timedelta
import json
from unittest.mock import patch
from threading import Event

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, models
from django.test import TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.tests.test_authority_generation import worker
from .four_testsupport import FourHelpers
from .test_source_writers import SourceHelpers
from . import test_generation_processing as previous_tests
from . import decision_services as decisions, generation_processing as processing
from .decision_models import DevelopmentHumanDecision as Decision, DevelopmentHumanDecisionAudit as Audit
from .generation_models import ProgramSourceState


class DecisionTests(SourceHelpers, FourHelpers, TransactionTestCase):
    context_new = previous_tests.ProcessingTests.context_new
    accept = previous_tests.ProcessingTests.accept
    process_new = previous_tests.ProcessingTests.process_new

    def setUp(self):
        self.setup_durable()
        self.client.force_login(self.officer)
        self.register()
        self.install_four()
        self.run = self.process_new(self.accept())
        self.url = reverse('ewaf:four_workspace', args=[self.program.pk])

    def data(self, **overrides):
        return {'user': self.officer, 'expected': self.token(), 'run_id': self.run.pk,
            'application_id': self.application.pk, 'decision': 'SELECT_DEMO',
            'reason': 'Fictional human review of verified functional need, separate from the computed score.',
            'expected_revision': 0, 'expected_previous': None, **overrides}

    def save(self, **overrides):
        return decisions.record(self.program.pk, **self.data(**overrides))

    def test_saved_revision_retry_and_withdrawal_preserve_calculations_and_assistance(self):
        from assistance.models import AssistanceCase, AssistanceRelease
        before = list(AssistanceCase.objects.values())
        state = self.token()
        original = self.save()
        self.assertEqual(self.save().pk, original.pk)
        successor = self.save(expected_revision=1, expected_previous=original.pk, decision='WITHDRAW_DEMO',
            reason='Fictional additional human review; retained original choice.')
        self.assertEqual(successor.previous_id, original.pk)
        self.assertEqual((Decision.objects.count(), Audit.objects.count()), (2, 2))
        from .four_decisions import demonstrate
        preview = demonstrate(self.program.pk, user=self.officer, expected=self.token(), run_id=self.run.pk,
            application_id=self.application.pk, decision='WITHDRAW_DEMO', reason='Fictional withdrawal preview')
        self.assertFalse(preview['selected_in_demonstration'])
        self.assertEqual((Decision.objects.count(), Audit.objects.count()), (2, 2))
        self.assertEqual(self.token(), state)
        self.assertEqual(processing.inspect_current(self.program.pk, user=self.officer)['run_id'], self.run.pk)
        self.assertEqual(list(AssistanceCase.objects.values()), before)
        self.assertFalse(AssistanceRelease.objects.exists())
        history = decisions.inspect_history(self.program.pk, user=self.officer)
        self.assertEqual([r.pk for r in history['rows']], [successor.pk, original.pk])
        older = decisions.inspect_history(self.program.pk, user=self.officer, limit=1, page=2)
        self.assertEqual([r.pk for r in older['rows']], [original.pk])
        self.assertEqual((older['total'], older['previous_page'], older['next_page']), (2, 1, None))
        original.refresh_from_db()
        original.clean()

    def test_wrong_run_cross_application_reason_and_stale_revision_fail_closed(self):
        from uuid import uuid4
        for override in ({'run_id': self.run.pk + 1}, {'application_id': uuid4()}, {'reason': '   '},
                         {'decision': 'APPROVED'}, {'expected_revision': True}, {'expected_previous': 99}):
            with self.subTest(override=override), self.assertRaises(ValidationError):
                self.save(**override)
        row = self.save()
        with self.assertRaisesMessage(ValidationError, 'STALE_HUMAN_DECISION_REVISION'):
            self.save(reason='Conflicting stale form')
        self.assertEqual(Decision.objects.count(), 1)
        self.assertEqual(row.revision, 1)

    def test_audit_and_decision_insert_failure_roll_back_both(self):
        for target in ('ewaf.decision_models.DevelopmentHumanDecisionAudit.save',
                       'ewaf.decision_models.DevelopmentHumanDecision.save'):
            with self.subTest(target=target), patch(target, side_effect=ValidationError('injected save failure')):
                with self.assertRaises(ValidationError):
                    self.save()
            self.assertFalse(Decision.objects.exists())
            self.assertFalse(Audit.objects.exists())

    def test_final_check_failure_rolls_back_decision_and_audit(self):
        original = processing._current
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise ValidationError('injected final freshness failure')
            return original(*args, **kwargs)
        with patch('ewaf.decision_services.processing._current', side_effect=fail_second):
            with self.assertRaisesMessage(ValidationError, 'injected final freshness failure'):
                self.save()
        self.assertEqual((Decision.objects.count(), Audit.objects.count()), (0, 0))

    def test_expiry_after_insert_rolls_back_and_future_read_clears_pointer(self):
        original = decisions._persist
        deadline = ProgramSourceState.objects.get(program=self.program).current_binding.request_binding.valid_until
        clock = patch('django.utils.timezone.now', return_value=deadline + timedelta(seconds=1))
        def expire_after_insert(row):
            result = original(row)
            clock.start()
            return result
        try:
            with patch('ewaf.decision_services._persist', side_effect=expire_after_insert):
                with self.assertRaisesMessage(ValidationError, 'DEVELOPMENT_RESULT_EXPIRED'):
                    self.save()
            self.assertEqual((Decision.objects.count(), Audit.objects.count()), (0, 0))
            with self.assertRaises(ValidationError):
                processing.inspect_current(self.program.pk, user=self.officer)
            self.assertIsNone(ProgramSourceState.objects.get(program=self.program).current_binding_id)
        finally:
            clock.stop()

    def test_source_invalidation_retains_history_and_blocks_old_decision_form(self):
        from members.services import change_status
        data = self.data()
        row = self.save()
        change_status(self.member.pk, user=self.officer, version=self.member.version, status='inactive',
            notes='Fictional source correction', source_expected=self.expected())
        with self.assertRaises(ValidationError):
            decisions.record(self.program.pk, **data)
        history = decisions.inspect_history(self.program.pk, user=self.officer)
        self.assertEqual(history['rows'][0].digest, row.digest)
        self.assertEqual(Audit.objects.count(), 1)

    def test_replacement_run_requires_new_review_and_preserves_old_decision(self):
        old = self.save()
        old_data = self.data()
        new = self.process_new(self.accept('decision-replacement', previous_id=self.run.pk))
        with self.assertRaises(ValidationError):
            decisions.record(self.program.pk, **old_data)
        self.run = new
        successor = self.save(expected_revision=old.revision, expected_previous=old.pk, decision='DEFER_REVIEW',
            reason='Fictional re-review against the replacement run')
        self.assertNotEqual(successor.run_binding_id, old.run_binding_id)
        self.assertEqual(len(decisions.inspect_history(self.program.pk, user=self.officer)['rows']), 2)

    def test_append_only_guards_and_digest_tampering(self):
        row = self.save()
        for action in (lambda: row.delete(), lambda: row.save(),
                       lambda: Decision.objects.filter(pk=row.pk).update(reason='changed'),
                       lambda: Decision.objects.all().delete(), lambda: Audit.objects.all().delete()):
            with self.assertRaises(ValidationError):
                action()
        row.payload = deepcopy(row.payload)
        row.payload['actually_assisted'] = True
        with self.assertRaises(ValidationError):
            row.clean()

    def test_stale_cached_permission_and_disposable_capability(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        self.assertTrue(self.officer.has_perm('assistance.decide_assistance'))
        self.officer.user_permissions.set(Permission.objects.exclude(codename='decide_assistance'))
        get_user_model().objects.filter(pk=self.officer.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied):
            self.save()
        with patch('accounts.authority_services.enlisted', return_value=False):
            with self.assertRaises(PermissionDenied):
                self.save()
        self.assertEqual(Decision.objects.count(), 0)

    def test_two_connections_conflicting_choices_have_one_winner(self):
        data = self.data()
        def attempt(reason):
            def task():
                try:
                    return decisions.record(self.program.pk, **{**data, 'reason': reason}).pk
                except ValidationError as error:
                    return error.messages
            return worker(task)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, ['Fictional first choice', 'Fictional conflicting choice']))
        self.assertEqual(len({identity for identity, result in results}), 2)
        self.assertEqual(sum(type(result) is int for identity, result in results), 1, results)
        self.assertEqual((Decision.objects.count(), Audit.objects.count()), (1, 1))
        first = Decision.objects.get()
        with ThreadPoolExecutor(max_workers=2) as pool:
            retries = list(pool.map(attempt, [first.reason, first.reason]))
        self.assertEqual([result for identity, result in retries], [first.pk, first.pk])
        self.assertEqual((Decision.objects.count(), Audit.objects.count()), (1, 1))
        data.update(expected_revision=1, expected_previous=first.pk)
        with ThreadPoolExecutor(max_workers=2) as pool:
            successors = list(pool.map(attempt, ['Fictional successor A', 'Fictional successor B']))
        self.assertEqual(sum(type(result) is int for identity, result in successors), 1, successors)
        self.assertEqual((Decision.objects.count(), Audit.objects.count()), (2, 2))
        self.assertEqual(Decision.objects.get(revision=2).previous_id, first.pk)

    def test_source_writer_waits_for_decision_then_invalidates_without_erasing_history(self):
        from members.services import change_status
        entered, release = Event(), Event()
        original = decisions._persist
        data = self.data()
        source_token = self.expected()
        def held(row):
            entered.set()
            if not release.wait(20):
                raise RuntimeError('Decision fence coordination timeout')
            return original(row)
        with patch('ewaf.decision_services._persist', side_effect=held), ThreadPoolExecutor(max_workers=2) as pool:
            saved = pool.submit(worker, lambda: decisions.record(self.program.pk, **data).pk)
            try:
                self.assertTrue(entered.wait(20))
                writer = pool.submit(worker, lambda: change_status(self.member.pk, user=self.officer,
                    version=self.member.version, status='inactive', notes='Fictional concurrent source review',
                    source_expected=source_token))
                with self.assertRaises(TimeoutError):
                    writer.result(timeout=.2)
            finally:
                release.set()
            decision_connection, pk = saved.result(timeout=30)
            writer_connection, _ = writer.result(timeout=30)
        self.assertNotEqual(decision_connection, writer_connection)
        self.assertIsNone(ProgramSourceState.objects.get(program=self.program).current_binding_id)
        self.assertEqual(decisions.inspect_history(self.program.pk, user=self.officer)['rows'][0].pk, pk)
        with self.assertRaises(ValidationError):
            decisions.record(self.program.pk, **data)

    def test_private_admin_record_post_retains_reason_and_history(self):
        response = self.client.get(self.url)
        initial = response.context['choice_form'].initial
        payload = {**initial, 'expected': json.dumps(initial['expected']),
            'expected_decisions': json.dumps(initial['expected_decisions']), 'action': 'record',
            'application_id': str(self.application.pk), 'decision': 'SELECT_FOR_DEMONSTRATION',
            'reason': 'Fictional officer decision, separate from score.'}
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        page = self.client.get(self.url)
        self.assertContains(page, 'Saved: yes. Actually assisted: no.')
        self.assertContains(page, 'Fictional officer decision, separate from score.')
        self.assertEqual(Decision.objects.count(), 1)
        self.assertIn('no-store', page['Cache-Control'])
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.officer)
        self.assertEqual(csrf.post(self.url, payload).status_code, 403)
        self.assertEqual(Client().get(self.url).status_code, 302)
