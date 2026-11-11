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
        services.review_eligibility(self.application.pk, user=self.officer, data=review_data(self.application))
        close_non_ewaf_program(self.program)
        self.other = create_program(name='Fictional second PA-dependent program')
        other_application = application_fixture(self.other, self.member)
        ProgramApplication.objects.filter(pk=other_application.pk).update(status='CLOSED')
        self.bootstrap([self.program.pk, self.other.pk])
        self.register()

    def all_expected(self):
        return {str(p.pk): self.token(p) for p in (self.program, self.other)}

    def approve(self, **changes):
        return services.decide_assistance(self.application.pk, user=self.officer,
            data=decision_data(self.application, **changes), source_expected=self.expected())

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

    def test_eligibility_and_decision_invalidate_own_program_only(self):
        self.approve(decision='pending')
        services.review_eligibility(self.application.pk, user=self.officer,
            data=review_data(self.application), source_expected=self.expected())
        self.approve()
        self.states(4, 1)
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_release_and_void_invalidate_complete_cross_program_scope(self):
        self.approve()
        release = self.release()
        self.states(3, 2)
        self.assertEqual(services.previous_assistance_count(self.member), 1)
        old_token = self.all_expected()
        self.void(release)
        self.states(4, 3)
        self.assertEqual(services.previous_assistance_count(self.member), 0)
        self.assertEqual(AssistanceRelease.objects.count(), 1)
        self.assertNotEqual(self.all_expected(), old_token)
        for batch in SourceMutationBatch.objects.filter(source_kind='assistance'):
            generation._validate_batch(batch)

    def test_partial_scope_rejected(self):
        self.approve()
        with self.assertRaisesMessage(ValidationError, 'INCOMPLETE_SHARED_SOURCE_SCOPE'):
            self.release(source_expected=self.expected())
        self.assertFalse(AssistanceRelease.objects.exists())
        self.states(2, 1)

    def test_release_requires_existing_human_approval(self):
        with self.assertRaises(ValidationError):
            self.release()
        self.states(1, 1)

    def test_receipt_button_keeps_complete_source_scope_and_late_rollback(self):
        self.approve()
        self.application.refresh_from_db()
        self.program.refresh_from_db()
        data = {'version': self.application.version, 'program_version': self.program.version}
        with patch('ewaf.shared_invalidation.finish', side_effect=ValidationError('Synthetic source audit failure')):
            with self.assertRaisesMessage(ValidationError, 'Synthetic source audit failure'):
                services.record_actual_receipt(self.application.pk, user=self.officer,
                    data=data, source_expected=self.all_expected())
        self.assertFalse(AssistanceRelease.objects.exists())
        self.states(2, 1)
        release = services.record_actual_receipt(self.application.pk, user=self.officer,
            data=data, source_expected=self.all_expected())
        self.assertEqual(release.approval_snapshot['recording_method'], 'program_receipt_button')
        self.states(3, 2)

    def test_duplicate_decision_and_receipt_do_not_invalidate(self):
        self.approve()
        with self.assertRaises(ValidationError):
            self.approve()
        self.release()
        with self.assertRaises(ValidationError):
            self.release()
        self.states(3, 2)

    def test_stale_source_token_rejected(self):
        prior = self.all_expected()
        self.approve()
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION_TOKEN'):
            self.release(source_expected=prior)
        self.states(2, 1)

    def test_stale_application_version_rejected(self):
        self.approve()
        data = release_data(self.application, version=1234)
        with self.assertRaises(ValidationError):
            self.release(data=data)
        self.states(2, 1)

    def test_missing_duplicate_and_forged_native_audits_roll_back(self):
        self.approve()
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
            self.states(2, 1)

    def test_second_cas_failure_rolls_back_receipt_application_and_audit(self):
        self.approve()
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
        self.states(2, 1)

    def test_void_audit_failure_preserves_successful_receipt(self):
        self.approve()
        release = self.release()
        with patch.object(generation, '_invalidate', side_effect=ValidationError('Fictional audit failure')):
            with self.assertRaises(ValidationError):
                self.void(release)
        release.refresh_from_db()
        self.assertIsNone(release.voided_at)
        self.assertEqual(release.active_application_id, self.application.pk)
        self.states(3, 2)

    def test_sql_complete_program_scope_precedes_application_and_member(self):
        self.approve()
        data, expected = release_data(self.application), self.all_expected()
        with CaptureQueriesContext(connection) as queries:
            services.record_release(self.application.pk, user=self.officer, data=data, source_expected=expected)
        locks = [q['sql'] for q in queries if 'FOR UPDATE' in q['sql']]
        self.assertIn('programs_programtermslock', locks[0])
        self.assertIn('ewaf_authoritygeneration', locks[1])
        self.assertTrue(all('FROM `programs_program`' in q for q in locks[2:4]))
        self.assertTrue(all('ewaf_programsourcestate' in q for q in locks[4:6]))
        self.assertIn('programs_programapplication', locks[6])
        self.assertIn('FROM `members_member`', locks[7])

    def test_separate_connection_release_race_has_one_receipt(self):
        self.approve()
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
        self.states(3, 2)
