"""Fictional eligibility, human decisions and cross-program actual receipts."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from accounts.tests.test_authority_generation import worker
from assistance import services
from assistance.models import AssistanceCase, AssistanceRelease, AssistanceLog
from assistance.tests import seed_statuses, create_application, review_data, decision_data, release_data
from programs.models import ProgramApplication
from programs.tests import create_program
from programs.testsupport import close_non_ewaf_program, application_fixture
from . import generation_services as generation
from .generation_models import ProgramSourceState, SourceMutationBatch
from .test_source_writers import SourceHelpers


class AssistanceWriterTests(SourceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_foundation()
        seed_statuses()
        self.application = create_application(program=self.program)
        self.member = self.application.member
        from assistance.testsupport import historical_selection
        from announcements.testsupport import publish_selection
        historical_selection(self.application, self.officer)
        close_non_ewaf_program(self.program)
        publish_selection(self.program, self.officer)
        self.other = create_program(name='Fictional second PA-dependent program')
        other_application = application_fixture(self.other, self.member)
        ProgramApplication.objects.filter(pk=other_application.pk).update(status='CLOSED')
        self.bootstrap([self.program.pk, self.other.pk])
        self.register()

    def all_expected(self):
        return {str(p.pk): self.token(p) for p in (self.program, self.other)}

    def retained_selection(self):
        # Existing pre-adoption approvals can still be delivered. New approval
        # writes are retired; no synthetic approval is performed after bootstrap.
        case = AssistanceCase.objects.get(application=self.application)
        self.assertEqual(case.decision, 'approved')
        return case

    def release(self, **kwargs):
        return services.record_release(self.application.pk, **{'user': self.officer,
            'data': release_data(self.application), 'source_expected': self.all_expected(), **kwargs})

    def void(self, release, **kwargs):
        self.application.refresh_from_db()
        return services.void_release(self.application.pk, release.pk, **{'user': self.officer,
            'data': {'version': self.application.version, 'notes': 'Fictional receipt correction', 'confirm': True},
            'source_expected': self.all_expected(), **kwargs})

    def states(self, first, second):
        self.assertEqual(ProgramSourceState.objects.get(program=self.program).generation, first)
        self.assertEqual(ProgramSourceState.objects.get(program=self.other).generation, second)
        for state in ProgramSourceState.objects.all():
            generation._state(state)

    def test_retired_eligibility_and_decision_leave_history_and_sources_unchanged(self):
        before = services.case_snapshot(self.retained_selection())
        with self.assertRaisesMessage(ValidationError, 'updated to EWAF'):
            services.review_eligibility(self.application.pk, user=self.officer,
                data=review_data(self.application), source_expected=self.expected())
        with self.assertRaises(ValidationError):
            services.decide_assistance(self.application.pk, user=self.officer,
                data=decision_data(self.application), source_expected=self.expected())
        self.assertEqual(services.case_snapshot(self.retained_selection()), before)
        self.states(1, 1)
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_release_and_void_invalidate_complete_cross_program_scope(self):
        self.retained_selection()
        release = self.release()
        self.states(2, 2)
        self.assertEqual(services.previous_assistance_count(self.member), 1)
        old_token = self.all_expected()
        self.void(release)
        self.states(3, 3)
        self.assertEqual(services.previous_assistance_count(self.member), 0)
        self.assertEqual(AssistanceRelease.objects.count(), 1)
        self.assertNotEqual(self.all_expected(), old_token)
        for batch in SourceMutationBatch.objects.filter(source_kind='assistance'):
            generation._validate_batch(batch)

    def test_partial_scope_rejected(self):
        self.retained_selection()
        with self.assertRaisesMessage(ValidationError, 'INCOMPLETE_SHARED_SOURCE_SCOPE'):
            self.release(source_expected=self.expected())
        self.assertFalse(AssistanceRelease.objects.exists())
        self.states(1, 1)

    def test_release_requires_existing_human_approval(self):
        AssistanceCase.objects.filter(application=self.application).update(decision='pending')
        with self.assertRaisesMessage(ValidationError, 'approve assistance'):
            self.release()
        self.states(1, 1)

    def test_receipt_button_refuses_nested_disposable_source_transaction(self):
        # The current receipt button owns a transaction for its receipt/email
        # audit. The non-promotable foundation protocol requires a top-level
        # source writer and must refuse this nested combination without writes.
        self.retained_selection()
        self.application.refresh_from_db()
        self.program.refresh_from_db()
        data = {'version': self.application.version, 'program_version': self.program.version,
                'claimant_type': 'beneficiary', 'beneficiary_identity_verified': True, 'receipt_confirmed': True}
        before = list(AssistanceLog.objects.values())
        with self.assertRaisesMessage(ValidationError, 'top-level durable service transaction'):
            services.record_actual_receipt(self.application.pk, user=self.officer,
                data=data, source_expected=self.all_expected())
        self.assertFalse(AssistanceRelease.objects.exists())
        self.assertEqual(list(AssistanceLog.objects.values()), before)
        self.states(1, 1)

    def test_duplicate_decision_and_receipt_do_not_invalidate(self):
        self.retained_selection()
        with self.assertRaises(ValidationError):
            services.decide_assistance(self.application.pk, user=self.officer,
                data=decision_data(self.application), source_expected=self.expected())
        self.release()
        with self.assertRaises(ValidationError):
            self.release()
        self.states(2, 2)

    def test_stale_source_token_rejected(self):
        prior = self.all_expected()
        receipt = self.release()
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION_TOKEN'):
            self.void(receipt, source_expected=prior)
        receipt.refresh_from_db()
        self.assertIsNone(receipt.voided_at)
        self.states(2, 2)

    def test_stale_application_version_rejected(self):
        self.retained_selection()
        data = release_data(self.application, version=1234)
        with self.assertRaises(ValidationError):
            self.release(data=data)
        self.states(1, 1)

    def test_missing_duplicate_and_forged_native_audits_roll_back(self):
        self.retained_selection()
        original = services.record_log
        for mode in ('missing', 'duplicate', 'forged'):
            def corrupt(*args, **kwargs):
                if mode == 'missing':
                    return None
                row = original(*args, **kwargs)
                if mode == 'duplicate':
                    original(*args, **kwargs)
                else:
                    AssistanceLog.objects.filter(pk=row.pk).update(snapshot={})
                return row
            with self.subTest(mode=mode), patch.object(services, 'record_log', side_effect=corrupt):
                with self.assertRaises(ValidationError):
                    self.release()
            self.assertFalse(AssistanceRelease.objects.exists())
            self.states(1, 1)

    def test_second_cas_failure_rolls_back_receipt_application_and_audit(self):
        self.retained_selection()
        count = AssistanceLog.objects.count()
        original = generation._cas_source
        def fail(state, event):
            if state.program_id == self.other.pk:
                raise ValidationError('Fictional second CAS failure')
            return original(state, event)
        with patch.object(generation, '_cas_source', side_effect=fail), self.assertRaises(ValidationError):
            self.release()
        self.assertFalse(AssistanceRelease.objects.exists())
        self.assertEqual(AssistanceLog.objects.count(), count)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'SELECTED')
        self.states(1, 1)

    def test_void_audit_failure_preserves_successful_receipt(self):
        self.retained_selection()
        release = self.release()
        with patch.object(generation, '_invalidate', side_effect=ValidationError('Fictional audit failure')):
            with self.assertRaises(ValidationError):
                self.void(release)
        release.refresh_from_db()
        self.assertIsNone(release.voided_at)
        self.assertEqual(release.active_application_id, self.application.pk)
        self.states(2, 2)

    def test_sql_complete_program_scope_precedes_application_and_member(self):
        self.retained_selection()
        data, expected = release_data(self.application), self.all_expected()
        with CaptureQueriesContext(connection) as queries:
            services.record_release(self.application.pk, user=self.officer, data=data, source_expected=expected)
        locks = [q['sql'] for q in queries if 'FOR UPDATE' in q['sql']]
        self.assertIn('programs_programtermslock', locks[0])
        self.assertIn('ewaf_authoritygeneration', locks[1])
        self.assertTrue(all(('FROM ' + connection.ops.quote_name('programs_program')) in q for q in locks[2:4]))
        self.assertTrue(all('ewaf_programsourcestate' in q for q in locks[4:6]))
        self.assertIn('programs_programapplication', locks[6])
        self.assertIn(('FROM ' + connection.ops.quote_name('members_member')), locks[7])

    def test_separate_connection_release_race_has_one_receipt(self):
        self.retained_selection()
        data, expected = release_data(self.application), self.all_expected()
        entered, release = Event(), Event()
        original = services.record_log
        def pause(*args, **kwargs):
            row = original(*args, **kwargs)
            entered.set()
            if not release.wait(15):
                raise RuntimeError('Fictional race timeout')
            return row
        def action():
            return services.record_release(self.application.pk, user=self.officer, data=data, source_expected=expected)
        with patch.object(services, 'record_log', side_effect=pause), ThreadPoolExecutor(2) as pool:
            first = pool.submit(worker, action)
            self.assertTrue(entered.wait(10))
            second = pool.submit(worker, action)
            try:
                with self.assertRaises(TimeoutError):
                    second.result(timeout=.25)
            finally:
                release.set()
            first.result(timeout=20)
            with self.assertRaises(ValidationError):
                second.result(timeout=20)
        self.assertEqual(AssistanceRelease.objects.count(), 1)
        self.states(2, 2)
