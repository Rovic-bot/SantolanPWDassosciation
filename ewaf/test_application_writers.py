"""Fictional Gate 2D-2A integration; isolated MySQL and temporary media only."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import timedelta
from pathlib import Path
from threading import Event
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from accounts import authority_services
from accounts.tests.test_authority_generation import worker
from announcements.tests import image_upload
from assistance import services as assistance
from assistance.models import AssistanceCase, AssistanceLog, AssistanceRelease, EligibilityStatus
from members.tests import create_member
from membership.tests import pdf
from programs import services as programs
from programs.models import (Program, ProgramApplication, ProgramLog, ProgramRequirement,
    ReferenceCounter, ProgramCodeCounter, ApplicationPhoto, PhotoVerification, ProgramDocument)
from programs.tests import verification
from programs.testsupport import application_fixture
from . import generation_services as generation, application_invalidation as adapter
from .generation_models import ProgramSourceState, SourceMutationBatch, SourceInvalidation
from .test_source_writers import SourceHelpers
from .durable_testsupport import DurableHelpers


class ApplicationHelpers(SourceHelpers):
    def setup_application(self, closure=False, case=False):
        from assistance.tests import seed_statuses
        seed_statuses()
        self.setup_foundation()
        self.member = create_member('FICTIONAL-G18-APPLICATION')
        self.member.refresh_from_db()
        self.grant = programs.verify_member(self.program.pk, **verification(self.member, self.program))
        if closure:
            self.application = application_fixture(self.program, self.member)
        if case:
            self.case = AssistanceCase.objects.create(application=self.application,
                eligibility=EligibilityStatus.objects.get(pk='eligible'), eligibility_label='Eligible',
                review_notes='Fictional review', reviewed_at=timezone.now(), reviewed_by=self.officer,
                member_version=self.member.version, program_version=self.program.version)
        self.register()

    def submit(self, **overrides):
        expected = overrides.pop('source_expected') if 'source_expected' in overrides else self.expected()
        return programs.submit_application(self.program.pk, **{'grant': self.grant,
            'data': {'version': self.program.version},
            'files': MultiValueDict({'calendar_photo': [image_upload()]}),
            'source_expected': expected, **overrides})

    def close(self, **overrides):
        expected = overrides.pop('source_expected') if 'source_expected' in overrides else self.expected()
        return programs.change_application(self.application.pk, **{'user': self.officer,
            'version': self.application.version, 'status': 'CLOSED', 'notes': 'Fictional reasoned closure',
            'source_expected': expected, **overrides})

    def files(self):
        return sorted(str(p.relative_to(settings.MEDIA_ROOT)) for p in Path(settings.MEDIA_ROOT).rglob('*') if p.is_file())

    def snapshot(self):
        return {model._meta.label: list(model.objects.order_by('pk').values()) for model in (
            Program, ProgramApplication, ProgramLog, AssistanceCase, AssistanceLog, ReferenceCounter,
            ProgramCodeCounter, ApplicationPhoto, PhotoVerification, ProgramDocument,
            ProgramSourceState, SourceMutationBatch, SourceInvalidation)}

    def assert_rollback(self, action, target, error=ValidationError):
        before, files = self.snapshot(), self.files()
        with patch(target, side_effect=error('Fictional injected failure')), self.assertRaises(error):
            action()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(files, self.files())

    def lock_order(self, action, expected_tables):
        with CaptureQueriesContext(connection) as queries:
            action()
        locks = [q['sql'] for q in queries if 'FOR UPDATE' in q['sql']]
        positions = [next(i for i, sql in enumerate(locks) if f'`{table}`' in sql) for table in expected_tables]
        self.assertEqual(positions, sorted(set(positions)))
        self.assertFalse(any('JOIN' in sql and '`programs_applicationphoto`' in sql for sql in locks))


class SubmissionTests(ApplicationHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_application()

    def test_success_has_system_provenance_reference_and_one_transition(self):
        application = self.submit()
        self.assertEqual(application.member_id, self.member.pk)
        self.assertEqual(application.status, 'PENDING_PHOTO_VERIFICATION')
        self.assertTrue(application.public_reference.endswith('0000000001'))
        batch = ProgramSourceState.objects.get(program=self.program).last_invalidation.batch
        self.assertIsNone(batch.actor_id)
        self.assertEqual(batch.system_code, 'VERIFIED_MEMBER_SUBMISSION')
        native = ProgramLog.objects.get(application=application, action='submitted')
        self.assertIsNone(native.actor_id)
        self.assertEqual(batch.source_audits[0]['pk'], str(native.pk))
        self.assert_transition(2)

    def test_duplicate_preserves_graph_files_counters_and_generation(self):
        first = self.submit()
        before, files = self.snapshot(), self.files()
        second = self.submit(data={}, files=MultiValueDict())
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(files, self.files())
        self.assert_transition(2)

    def test_duplicate_with_stale_source_token_is_rejected(self):
        old = self.expected()
        self.submit()
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION'):
            self.submit(source_expected=old)
        self.assert_transition(2)

    def test_expired_wrong_program_and_changed_member_grants_are_rejected(self):
        for values in ({'expires': 0}, {'program': 'wrong'}, {'member_version': 987}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.submit(grant={**self.grant, **values})
        self.assertFalse(ProgramApplication.objects.exists())
        self.assert_transition(1)

    def test_inactive_member_rejected(self):
        # Adversarial fixture change; Members integration is not claimed.
        type(self.member).objects.filter(pk=self.member.pk).update(is_active=False)
        with self.assertRaisesMessage(ValidationError, 'Membership changed'):
            self.submit()
        self.assert_transition(1)

    def test_closed_registration_and_stale_program_version_rejected(self):
        with self.assertRaises(ValidationError):
            self.submit(data={'version': 999})
        Program.objects.filter(pk=self.program.pk).update(registration_closes_at=timezone.now() - timedelta(days=1))
        with self.assertRaises(ValidationError):
            self.submit()
        self.assert_transition(1)

    def test_missing_required_evidence_rejected(self):
        with self.assertRaises(ValidationError):
            self.submit(files=MultiValueDict())
        self.assert_transition(1)

    def test_missing_extra_and_invalid_generation_tokens_rejected(self):
        bad = self.expected()
        bad[str(self.program.pk)]['source_generation'] = True
        for expected in (None, {}, {**self.expected(), 'other': self.token()}, bad):
            with self.subTest(expected=expected), self.assertRaises(ValidationError):
                self.submit(source_expected=expected)
        self.assert_transition(1)

    def test_missing_state_fails_closed(self):
        expected = self.expected()
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM ewaf_programsourcestate WHERE program_id=%s', [self.program.pk.hex])
        with self.assertRaisesMessage(ValidationError, 'SOURCE_STATE_NOT_INITIALIZED'):
            self.submit(source_expected=expected)
        self.assertFalse(ProgramApplication.objects.exists())

    def test_missing_native_audit_rolls_back_reference_and_files(self):
        before, files = self.snapshot(), self.files()
        with patch.object(programs, 'record_log'), self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT'):
            self.submit()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(files, self.files())
        self.assertTrue(self.submit().public_reference.endswith('0000000001'))

    def test_duplicate_native_audit_rolls_back(self):
        original = programs.record_log
        def duplicate(*args, **kwargs):
            original(*args, **kwargs)
            return original(*args, **kwargs)
        before = self.snapshot()
        with patch.object(programs, 'record_log', duplicate), self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT'):
            self.submit()
        self.assertEqual(before, self.snapshot())

    def test_fabricated_admin_actor_rejected(self):
        original = programs.record_log
        def fabricated(*args, **kwargs):
            return original(*args, **{**kwargs, 'user': self.officer})
        before = self.snapshot()
        with patch.object(programs, 'record_log', fabricated), self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT'):
            self.submit()
        self.assertEqual(before, self.snapshot())

    def test_unexpected_assistance_audit_rejects_submission(self):
        original = programs.record_log
        def extra(*args, **kwargs):
            row = original(*args, **kwargs)
            AssistanceLog.objects.create(application=kwargs['application'], actor=self.officer,
                actor_label=self.officer.username, action='unexpected', notes='Fictional unrelated audit')
            return row
        before = self.snapshot()
        with patch.object(programs, 'record_log', extra), self.assertRaisesMessage(ValidationError, 'ASSISTANCE_AUDIT'):
            self.submit()
        self.assertEqual(before, self.snapshot())

    def test_system_code_cannot_be_replayed_for_unrelated_event(self):
        self.submit()
        batch = ProgramSourceState.objects.get(program=self.program).last_invalidation.batch
        batch.reason_code = 'UNRELATED'
        batch.digest = generation.digest(batch.payload())
        with self.assertRaisesMessage(ValidationError, 'SUBMISSION_SYSTEM_SCOPE_INVALID'):
            batch.full_clean()

    def test_authority_change_rejects_old_submission_token(self):
        expected = self.expected()
        self.advance_authority()
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION'):
            self.submit(source_expected=expected)
        self.assertFalse(ProgramApplication.objects.exists())
        self.assertEqual(ProgramSourceState.objects.get(program=self.program).generation, 1)

    def test_native_exception_cleans_files(self):
        self.assert_rollback(self.submit, 'programs.services.record_log', RuntimeError)

    def test_generation_audit_failure_cleans_files(self):
        self.assert_rollback(self.submit, 'ewaf.generation_services._persist')

    def test_cas_failure_cleans_files(self):
        self.assert_rollback(self.submit, 'ewaf.generation_services._cas_source')

    def test_final_failure_cleans_photo_and_document_files(self):
        requirement = ProgramRequirement.objects.create(program=self.program, label='Fictional supporting evidence',
            kind='document', is_active=True, is_required=True)
        self.assert_rollback(lambda: self.submit(files=MultiValueDict({'calendar_photo': [image_upload()],
            f'requirement_{requirement.pk}': [pdf()]})), 'ewaf.source_invalidation._final_validate')

    def test_submission_lock_order(self):
        expected = self.expected()
        self.lock_order(lambda: self.submit(source_expected=expected), ('programs_programtermslock',
            'ewaf_authoritygeneration', 'programs_program', 'ewaf_programsourcestate',
            'programs_programapplication', 'members_member', 'programs_programcodecounter'))

    def test_unregistered_behavior_no_generation_queries(self):
        with patch.object(authority_services, '_session', None), CaptureQueriesContext(connection) as queries:
            item = programs.submit_application(self.program.pk, grant=self.grant,
                data={'version': self.program.version}, files=MultiValueDict({'calendar_photo': [image_upload()]}))
        self.assertIsNotNone(item.pk)
        self.assertFalse(any('ewaf_programsourcestate' in q['sql'] or 'ewaf_authoritygeneration' in q['sql'] for q in queries))
        self.assert_transition(1)

    def test_caller_token_cannot_activate_and_outer_transaction_denied(self):
        expected = self.expected()
        with patch.object(authority_services, '_session', None), self.assertRaises(PermissionDenied):
            self.submit(source_expected=expected)
        with transaction.atomic(), self.assertRaisesMessage(ValidationError, 'top-level'):
            self.submit(source_expected=expected)

    def test_new_pending_application_is_in_complete_inventory(self):
        from .pool_services import inspect_program_pool
        before = inspect_program_pool(self.program.pk, user=self.officer)
        item = self.submit()
        after = inspect_program_pool(self.program.pk, user=self.officer)
        self.assertEqual(after['retained_application_count'], before['retained_application_count'] + 1)
        self.assertIn(str(item.pk), str(after['manifest']))
        self.assert_transition(2)


class ClosureTests(ApplicationHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_application(closure=True, case=True)

    def test_closure_case_and_two_native_audits_commit_once(self):
        item = self.close()
        self.case.refresh_from_db()
        self.assertEqual((item.status, self.case.eligibility_id, self.case.decision), ('CLOSED', 'review', 'pending'))
        batch = ProgramSourceState.objects.get(program=self.program).last_invalidation.batch
        self.assertEqual({ref['model'] for ref in batch.source_audits}, {'programs.programlog', 'assistance.assistancelog'})
        self.assertEqual(batch.actor_id, self.officer.pk)
        self.assert_transition(2)

    def test_closure_without_case_requires_only_program_audit(self):
        self.case.delete()  # Fixture variant, no Assistance writer change.
        self.close()
        self.assertFalse(AssistanceLog.objects.exists())
        self.assert_transition(2)

    def test_stale_business_version_and_missing_reason_rejected(self):
        for changes in ({'version': 987}, {'notes': ' '}, {'status': 'ELIGIBLE'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.close(**changes)
        self.assert_transition(1)

    def test_approved_case_cannot_close(self):
        AssistanceCase.objects.filter(pk=self.case.pk).update(decision='approved')
        with self.assertRaisesMessage(ValidationError, 'Return the assistance approval'):
            self.close()
        self.assert_transition(1)

    def test_released_application_cannot_close(self):
        AssistanceRelease.objects.create(application=self.application, active_application=self.application,
            assistance_type='Fictional', benefit='Fictional', released_on=timezone.localdate(), notes='Fictional release fixture')
        with self.assertRaisesMessage(ValidationError, 'has been released'):
            self.close()
        self.assert_transition(1)

    def test_repeat_closure_and_public_resubmission_denied(self):
        self.close()
        self.application.refresh_from_db()
        for action in (self.close, self.submit):
            with self.assertRaises(ValidationError):
                action()
        self.assert_transition(2)

    def test_current_permission_recheck(self):
        expected = self.expected()
        get_user_model().objects.filter(pk=self.officer.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied):
            self.close(source_expected=expected)
        self.application.refresh_from_db()
        self.assertNotEqual(self.application.status, 'CLOSED')

    def test_case_audit_missing_or_duplicated_rolls_back_everything(self):
        original = assistance.record_log
        def duplicate(*args, **kwargs):
            original(*args, **kwargs)
            return original(*args, **kwargs)
        for replacement in (lambda *a, **k: None, duplicate):
            before = self.snapshot()
            with patch.object(assistance, 'record_log', replacement), self.assertRaisesMessage(ValidationError, 'ASSISTANCE_AUDIT'):
                self.close()
            self.assertEqual(before, self.snapshot())

    def test_wrong_case_audit_snapshot_rolls_back(self):
        original = assistance.record_log
        def incorrect(application, user, action, notes, snapshot, address=None):
            return original(application, user, action, notes, {'before': {}, 'after': {}}, address)
        before = self.snapshot()
        with patch.object(assistance, 'record_log', incorrect), self.assertRaisesMessage(ValidationError, 'ASSISTANCE_AUDIT'):
            self.close()
        self.assertEqual(before, self.snapshot())

    def test_program_audit_failure_rolls_back_case_and_assistance_log(self):
        self.assert_rollback(self.close, 'programs.services.record_log')

    def test_missing_program_audit_rolls_back_case(self):
        before = self.snapshot()
        with patch.object(programs, 'record_log'), self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT'):
            self.close()
        self.assertEqual(before, self.snapshot())

    def test_final_authorization_failure_rolls_back_case_and_both_audits(self):
        from .source_invalidation import _actor
        calls = []
        def fail_final(user):
            calls.append(True)
            if len(calls) == 2:
                raise PermissionDenied('Fictional final authority failure')
            return _actor(user)
        before = self.snapshot()
        with patch('ewaf.source_invalidation._actor', fail_final), self.assertRaises(PermissionDenied):
            self.close()
        self.assertEqual(before, self.snapshot())

    def test_incomplete_source_scope_rejected_before_closure(self):
        for expected in (None, {}, {**self.expected(), 'extra': self.token()}):
            with self.subTest(expected=expected), self.assertRaisesMessage(ValidationError, 'INCOMPLETE_SOURCE_SCOPE'):
                self.close(source_expected=expected)
        self.assert_transition(1)

    def test_assistance_audit_exception_rolls_back(self):
        self.assert_rollback(self.close, 'assistance.services.record_log')

    def test_closure_cas_and_final_failure_roll_back(self):
        for target in ('ewaf.generation_services._cas_source', 'ewaf.source_invalidation._final_validate'):
            with self.subTest(target=target):
                self.assert_rollback(self.close, target)

    def test_application_changed_then_restored_cannot_reuse_old_token(self):
        old = self.expected()
        old_status = self.application.status
        self.close()
        # Adversarial raw restoration is NOT an authorized reopening workflow.
        ProgramApplication.objects.filter(pk=self.application.pk).update(status=old_status, version=self.application.version)
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION'):
            self.close(source_expected=old)
        self.assert_transition(2)

    def test_closure_lock_order(self):
        expected = self.expected()
        self.lock_order(lambda: self.close(source_expected=expected), ('programs_programtermslock',
            'ewaf_authoritygeneration', 'programs_program', 'ewaf_programsourcestate',
            'programs_programapplication', 'members_member', 'assistance_eligibilitystatus', 'assistance_assistancecase'))


class ApplicationConcurrencyTests(ApplicationHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_application(closure=True, case=True)

    def race(self, operation, fail_first=False):
        entered, release, attempted = Event(), Event(), Event()
        real, boundary = generation._invalidate, generation.durable_services._boundary
        calls = []
        def hold(*args, **kwargs):
            calls.append(True)
            if len(calls) == 1:
                entered.set()
                if not release.wait(20):
                    raise RuntimeError('Fictional race timeout')
                if fail_first:
                    raise ValidationError('Fictional first writer rollback')
            return real(*args, **kwargs)
        def signal():
            if entered.is_set():
                attempted.set()
            return boundary()
        def mutate():
            try:
                return str(operation().pk)
            except ValidationError as exc:
                return str(exc)
        with patch.object(generation, '_invalidate', hold), patch.object(generation.durable_services, '_boundary', signal):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(worker, mutate)
                try:
                    self.assertTrue(entered.wait(10))
                    second = pool.submit(worker, mutate)
                    self.assertTrue(attempted.wait(10))
                    with self.assertRaises(TimeoutError):
                        second.result(.25)
                finally:
                    release.set()
                a, b = first.result(30), second.result(30)
        self.assertNotEqual(a[0], b[0])
        if fail_first:
            self.assertIn('first writer rollback', a[1])
            self.assertNotIn('STALE', b[1])
        else:
            self.assertNotIn('STALE', a[1])
            self.assertIn('STALE_GENERATION', b[1])
        self.assert_transition(2)

    def test_two_closures_have_one_winner(self):
        expected = self.expected()
        self.race(lambda: self.close(source_expected=expected))

    def test_failed_closure_allows_waiting_writer_to_commit(self):
        expected = self.expected()
        self.race(lambda: self.close(source_expected=expected), fail_first=True)

    def test_two_new_submissions_preserve_reference_uniqueness(self):
        member = create_member('FICTIONAL-RACE-SECOND')
        member.refresh_from_db()
        grant = programs.verify_member(self.program.pk, **verification(member, self.program))
        expected = self.expected()
        self.race(lambda: self.submit(grant=grant, source_expected=expected))
        self.assertEqual(ProgramApplication.objects.filter(member=member, program=self.program).count(), 1)
        self.assertEqual(ReferenceCounter.objects.get(program=self.program).value, 2)

    def test_failed_submission_cleans_files_before_waiting_writer_commits(self):
        member = create_member('FICTIONAL-RACE-ROLLBACK')
        member.refresh_from_db()
        grant = programs.verify_member(self.program.pk, **verification(member, self.program))
        expected, before_files = self.expected(), len(self.files())
        self.race(lambda: self.submit(grant=grant, source_expected=expected), fail_first=True)
        self.assertEqual(len(self.files()), before_files + 1)
        self.assertEqual(ReferenceCounter.objects.get(program=self.program).value, 2)

    def test_existing_assistance_review_waits_for_closure_and_then_rejects(self):
        from assistance.tests import review_data
        expected = self.expected()
        data = review_data(self.application)
        entered, release, attempting = Event(), Event(), Event()
        original = generation._invalidate
        def hold(*args, **kwargs):
            entered.set()
            if not release.wait(20):
                raise RuntimeError('Fictional concurrency timeout')
            return original(*args, **kwargs)
        def review():
            attempting.set()
            try:
                assistance.review_eligibility(self.application.pk, user=self.officer, data=data)
                return 'unexpected success'
            except ValidationError as exc:
                return str(exc)
        with patch.object(generation, '_invalidate', hold), ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(worker, lambda: self.close(source_expected=expected).status)
            try:
                self.assertTrue(entered.wait(10))
                second = pool.submit(worker, review)
                self.assertTrue(attempting.wait(10))
                with self.assertRaises(TimeoutError):
                    second.result(.25)
            finally:
                release.set()
            a, b = first.result(30), second.result(30)
        self.assertNotEqual(a[0], b[0])
        self.assertEqual(a[1], 'CLOSED')
        self.assertNotEqual(b[1], 'unexpected success')
        self.assert_transition(2)


class ApplicationHistoryTests(ApplicationHelpers, DurableHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()
        self.new_member = create_member('FICTIONAL-AFTER-CUTOFF')
        self.new_member.refresh_from_db()
        self.grant = programs.verify_member(self.program.pk, **verification(self.new_member, self.program))
        self.register()

    def test_after_cutoff_submission_invalidates_and_preserves_old_run_bindings(self):
        from .durable_services import inspect_development_history, require_operational_result
        request = self.request_run()
        run = self.process(request)
        expected = self.token()
        with generation._fence(self.officer, [self.program.pk]) as (_, authority, _, states):
            state = states[self.program.pk]
            rb = generation._bind_request(request, run.snapshot, state=state, authority=authority,
                expected=expected, valid_until=timezone.now() + timedelta(minutes=2))
            run_binding = generation._bind_run(run, state=state, authority=authority)
        before = run.digest, run.context_digest, run.snapshot, rb.digest, run_binding.digest
        item = self.submit(data={'version': self.program.version,
            f'requirement_{self.relevance_requirement.pk}': 'Fictional relevance pending review'})
        self.assertGreater(item.submitted_at.isoformat(), self.contract['cutoff'])
        self.assert_transition(2)
        run.refresh_from_db(); rb.refresh_from_db(); run_binding.refresh_from_db()
        rb.full_clean(); run_binding.full_clean()
        self.assertEqual(before, (run.digest, run.context_digest, run.snapshot, rb.digest, run_binding.digest))
        self.assertFalse(inspect_development_history(run.pk, program_id=self.program.pk, user=self.officer)['operational_ready'])
        with self.assertRaises(ValidationError):
            require_operational_result()

    def test_closure_preserves_old_numerical_history(self):
        from .durable_services import inspect_development_history
        run = self.process(self.request_run())
        before = run.digest, run.snapshot
        self.close()
        run.refresh_from_db()
        self.assertEqual(before, (run.digest, run.snapshot))
        self.assertFalse(inspect_development_history(run.pk, program_id=self.program.pk, user=self.officer)['operational_ready'])
        self.assert_transition(2)
