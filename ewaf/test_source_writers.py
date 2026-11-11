"""Fictional Gate 2D-1 writers; fresh MySQL with DurableTestRunner only."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from datetime import timedelta
from threading import Event
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from accounts import authority_services
from accounts.tests.test_authority_generation import worker
from programs import services as programs
from programs.models import Program, ProgramLog, ProgramRequirement, PDAOApprovalRecord, ProgramTermsRevision
from programs.tests import program_data
from programs.test_approved_terms import TermsHelpers
from programs.testsupport import private_media
from . import source_invalidation as adapter, generation_services as generation
from .generation_models import ProgramSourceState, SourceMutationBatch, SourceInvalidation, AuthorityGeneration
from .test_generation_foundation import FoundationHelpers
from .durable_testsupport import DurableHelpers


class SourceHelpers(FoundationHelpers):
    def register(self):
        self.bootstrap()
        context = authority_services._disposable_authority_session(user=self.officer)
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def expected(self):
        return {str(self.program.pk): self.token()}

    def assert_transition(self, expected_generation):
        state = ProgramSourceState.objects.get(program=self.program)
        self.assertEqual((state.generation, state.revision), (expected_generation, expected_generation))
        self.assertIsNone(state.current_binding_id)
        self.assertEqual(SourceInvalidation.objects.filter(program=self.program).count(), expected_generation)
        generation._state(state)
        for batch in SourceMutationBatch.objects.all():
            generation._validate_batch(batch)
        self.assertEqual(AuthorityGeneration.objects.get(pk=1).generation, 1)


class ProgramSourceTests(SourceHelpers, TermsHelpers, TransactionTestCase):
    def setUp(self):
        private_media(self)
        self.setup_terms(draft=True)
        self.register()

    def save(self, **overrides):
        self.program.refresh_from_db()
        return programs.save_program(pk=self.program.pk, user=self.officer,
            data=self.edit_data(**overrides), source_expected=self.expected())

    def requirement(self, **kwargs):
        self.program.refresh_from_db()
        return programs.save_requirement(self.program.pk, user=self.officer, source_expected=self.expected(),
            **{'data': {'label': 'Fictional requirement', 'kind': 'text', 'is_active': True,
                       'is_required': True, 'position': 0, 'version': self.program.version,
                       'notes': 'Fictional requirement review'}, **kwargs})

    def test_program_update_and_changed_then_restored(self):
        before = self.program.name
        self.save(name='Fictional revised name')
        self.save(name=before)
        self.assert_transition(3)
        self.assertEqual(Program.objects.get(pk=self.program.pk).name, before)

    def test_program_creation_initializes_once_with_native_audits(self):
        created = programs.save_program(user=self.officer, data=program_data(), source_expected={'authority_generation': 1})
        state = ProgramSourceState.objects.get(program=created)
        self.assertEqual((state.generation, state.revision), (1, 1))
        batch = state.last_invalidation.batch
        self.assertEqual(batch.kind, 'INITIALIZE')
        self.assertEqual(len(batch.source_audits), 2)
        generation._validate_batch(batch)

    def test_program_creation_audit_failure_rolls_back_every_table(self):
        before = (Program.objects.count(), ProgramLog.objects.count(), ProgramSourceState.objects.count())
        with patch.object(generation, '_invalidate', side_effect=ValidationError('Fictional audit failure')):
            with self.assertRaises(ValidationError):
                programs.save_program(user=self.officer, data=program_data(), source_expected={'authority_generation': 1})
        self.assertEqual(before, (Program.objects.count(), ProgramLog.objects.count(), ProgramSourceState.objects.count()))
        self.assert_transition(1)

    def test_stale_creation_authority_denied(self):
        with self.assertRaisesMessage(ValidationError, 'STALE_AUTHORITY'):
            programs.save_program(user=self.officer, data=program_data(), source_expected={'authority_generation': 2})
        self.assert_transition(1)

    def test_requirement_creation_and_update(self):
        item = self.requirement()
        self.program.refresh_from_db()
        self.requirement(requirement_id=item.pk, data={'label': 'Fictional revised requirement', 'kind': 'text',
            'is_active': True, 'is_required': True, 'position': 0, 'version': self.program.version,
            'notes': 'Fictional correction'})
        self.assert_transition(3)

    def test_publication_and_withdrawal(self):
        for action in ('published', 'draft'):
            self.program.refresh_from_db()
            programs.change_publication(self.program.pk, user=self.officer, version=self.program.version,
                action=action, notes='Fictional status review', source_expected=self.expected())
        self.assert_transition(3)

    def test_protected_unchanged_save_has_no_invalidation(self):
        programs.change_publication(self.program.pk, user=self.officer, version=self.program.version,
            action='published', notes='Fictional publication', source_expected=self.expected())
        self.save()
        self.assert_transition(2)

    def test_unprotected_same_values_retain_conservative_native_audit_dependency(self):
        self.save()
        # Legacy writer increments Program.version and appends an audit even if
        # editable values match. That is a real Gate 1 dependency change.
        self.assert_transition(2)

    def test_approval_capture_and_binding_each_invalidate_once(self):
        from programs.approval_services import record_pdao_approval
        from programs.test_pdao_approval import approval_data
        revision = self.capture(source_expected=self.expected())
        approval = record_pdao_approval(self.program.pk, user=self.officer,
            data=approval_data(expected_program_version=self.program.version), source_expected=self.expected())
        self.bind(revision, approval, source_expected=self.expected())
        self.assert_transition(4)

    def test_duplicate_terms_capture_fails_without_invalidation(self):
        self.capture(source_expected=self.expected())
        with self.assertRaisesMessage(ValidationError, 'already been recorded'):
            self.capture(source_expected=self.expected())
        self.assert_transition(2)

    def test_failed_business_validation_preserves_generation(self):
        with self.assertRaises(ValidationError):
            self.save(name='')
        self.assert_transition(1)

    def test_stale_generation_denies_even_when_business_version_is_current(self):
        old = self.expected()
        self.save(name='Fictional first change')
        self.program.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION'):
            programs.save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(), source_expected=old)
        self.assert_transition(2)

    def test_stale_business_version_is_preserved(self):
        old_data = self.edit_data(name='Fictional stale edit')
        self.save(name='Fictional new version')
        with self.assertRaisesMessage(ValidationError, 'changed'):
            programs.save_program(pk=self.program.pk, user=self.officer, data=old_data, source_expected=self.expected())
        self.assert_transition(2)

    def test_missing_and_extra_scope_denied(self):
        for token in (None, {}, {**self.expected(), 'extra-program': self.token()}):
            with self.subTest(token=token), self.assertRaisesMessage(ValidationError, 'SOURCE_SCOPE'):
                programs.save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(), source_expected=token)
        self.assert_transition(1)

    def test_missing_state_denied(self):
        expected = self.expected()
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM ewaf_programsourcestate WHERE program_id=%s', [self.program.pk.hex])
        with self.assertRaisesMessage(ValidationError, 'SOURCE_STATE_NOT_INITIALIZED'):
            programs.save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(), source_expected=expected)

    def test_no_implicit_activation_outside_session(self):
        with patch.object(authority_services, '_session', None), CaptureQueriesContext(connection) as queries:
            programs.save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(name='Fictional legacy edit'))
        self.assertFalse(any('ewaf_programsourcestate' in q['sql'] or 'ewaf_authoritygeneration' in q['sql'] for q in queries))
        self.assert_transition(1)

    def test_token_cannot_activate_protocol(self):
        expected = self.expected()
        with patch.object(authority_services, '_session', None), self.assertRaises(PermissionDenied):
            programs.save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(), source_expected=expected)

    def test_outer_transaction_denied(self):
        expected = self.expected()
        with transaction.atomic(), self.assertRaisesMessage(ValidationError, 'top-level'):
            programs.save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(), source_expected=expected)

    def test_missing_native_audit_rolls_back(self):
        before = self.program.name
        with patch.object(programs, 'record_log'), self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT'):
            self.save(name='Fictional rolled back')
        self.assertEqual(Program.objects.get(pk=self.program.pk).name, before)
        self.assert_transition(1)

    def test_duplicate_native_audit_rolls_back(self):
        original = programs.record_log
        def duplicate(*args, **kwargs):
            original(*args, **kwargs)
            return original(*args, **kwargs)
        with patch.object(programs, 'record_log', duplicate), self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT'):
            self.save(name='Fictional rolled back')
        self.assert_transition(1)

    def test_out_of_scope_native_audit_rejects_whole_mutation(self):
        from programs.tests import create_program
        other = create_program(name='Fictional unrelated program')
        original = programs.record_log
        before = ProgramLog.objects.count()
        def extra(*args, **kwargs):
            result = original(*args, **kwargs)
            original(other, 'updated', 'Fictional unexpected scope', user=self.officer)
            return result
        with patch.object(programs, 'record_log', extra), self.assertRaisesMessage(ValidationError, 'AUDIT_OR_SCOPE'):
            self.save(name='Fictional rolled back')
        self.assertEqual(ProgramLog.objects.count(), before)
        self.assert_transition(1)

    def test_approval_control_lock_is_after_source_state(self):
        with CaptureQueriesContext(connection) as queries:
            self.capture(source_expected=self.expected())
        locks = [q['sql'] for q in queries if 'FOR UPDATE' in q['sql']]
        control = next(i for i,q in enumerate(locks) if '`programs_programapprovalcontrol`' in q)
        state = max(i for i,q in enumerate(locks[:control]) if '`ewaf_programsourcestate`' in q)
        self.assertGreater(control, state)
        self.assert_transition(2)

    def test_native_audit_exception_rolls_back(self):
        with patch.object(programs, 'record_log', side_effect=RuntimeError('Fictional audit failure')):
            with self.assertRaises(RuntimeError):
                self.save(name='Fictional rolled back')
        self.assert_transition(1)

    def test_invalidation_and_cas_and_final_validation_failure_roll_back(self):
        for module, method in ((generation, '_persist'), (generation, '_cas_source'), (adapter, '_final_validate')):
            before = (self.program.name, ProgramLog.objects.count())
            with self.subTest(method=method), patch.object(module, method, side_effect=ValidationError('Fictional failure')):
                with self.assertRaises(ValidationError):
                    self.save(name='Fictional rolled back')
            self.program.refresh_from_db()
            self.assertEqual(before, (self.program.name, ProgramLog.objects.count()))
            self.assert_transition(1)

    def test_fresh_permission_recheck_rejects_cached_superuser(self):
        self.officer.get_all_permissions()
        get_user_model().objects.filter(pk=self.officer.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied):
            # Capture token via another privileged fixture path is unnecessary:
            # the exact expected token is known and provides no authorization.
            programs.save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(),
                source_expected={str(self.program.pk): {'source_generation': 1, 'revision': 1,
                    'authority_generation': 1, 'current_binding': None}})
        self.assert_transition(1)

    def test_final_authority_failure_rolls_back_native_and_source_changes(self):
        real = adapter._actor
        calls = []
        def revoke(user):
            calls.append(True)
            if len(calls) == 2:
                raise PermissionDenied('Fictional final authorization failure')
            return real(user)
        with patch.object(adapter, '_actor', revoke), self.assertRaises(PermissionDenied):
            self.save(name='Fictional rolled back')
        self.assert_transition(1)


class EwafSourceTests(SourceHelpers, DurableHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()
        self.register()

    def test_evidence_policy_and_assessment_each_advance_once(self):
        self.assess('ND', source_expected=self.expected())
        self.policy_record(source_expected=self.expected())
        self.assert_transition(3)

    def test_configuration_validation_review_authority_and_scoring_history(self):
        self.draft(source_expected=self.expected())
        self.validate(source_expected=self.expected())
        self.review(source_expected=self.expected())
        self.authority(source_expected=self.expected())
        self.propose(source_expected=self.expected())
        self.assert_transition(6)

    def test_repeated_validation_is_conservative_audit_dependency(self):
        first = self.validate(source_expected=self.expected())
        second = self.validate(source_expected=self.expected())
        self.assertEqual(first.result, second.result)
        self.assertNotEqual(first.pk, second.pk)
        self.assert_transition(3)

    def test_assessment_business_context_stale_rejected(self):
        with self.assertRaisesMessage(ValidationError, 'SOURCE_CHANGED'):
            self.assess('ND', expected_context='0' * 64, source_expected=self.expected())
        self.assert_transition(1)

    def test_ewaf_artifact_and_native_audit_rollback(self):
        from .models import ConfigurationReview
        before = (ConfigurationReview.objects.count(), ProgramLog.objects.count())
        with patch.object(adapter, '_final_validate', side_effect=ValidationError('Fictional final failure')):
            with self.assertRaises(ValidationError):
                self.review(source_expected=self.expected())
        self.assertEqual(before, (ConfigurationReview.objects.count(), ProgramLog.objects.count()))
        self.assert_transition(1)

    def test_old_durable_graph_and_bindings_remain_reproducible(self):
        from .durable_services import inspect_development_history, require_operational_result
        request = self.request_run()
        run = self.process(request)
        before = (run.digest, run.context_digest, run.snapshot)
        expected = self.token()
        with generation._fence(self.officer, [self.program.pk]) as (_, authority, _, states):
            state = states[self.program.pk]
            request_binding = generation._bind_request(request, run.snapshot, state=state, authority=authority,
                expected=expected, valid_until=timezone.now() + timedelta(minutes=2))
            run_binding = generation._bind_run(run, state=state, authority=authority)
        binding_digests = (request_binding.digest, run_binding.digest)
        self.review(source_expected=self.expected())
        run.refresh_from_db()
        self.assertEqual(before, (run.digest, run.context_digest, run.snapshot))
        result = inspect_development_history(run.pk, program_id=self.program.pk, user=self.officer)
        self.assertFalse(result['operational_ready'])
        self.assertIsNone(result['sources_match_now'])
        request_binding.refresh_from_db()
        run_binding.refresh_from_db()
        request_binding.full_clean()
        run_binding.full_clean()
        self.assertEqual(binding_digests, (request_binding.digest, run_binding.digest))
        with self.assertRaises(ValidationError):
            require_operational_result()
        self.assert_transition(2)

    def test_assessment_lock_prefix_precedes_existing_application_and_member_locks(self):
        expected = self.expected()
        with CaptureQueriesContext(connection) as queries:
            self.assess('ND', source_expected=expected)
        locks = [q['sql'] for q in queries if 'FOR UPDATE' in q['sql']]
        for table, sql in zip(('programs_programtermslock', 'ewaf_authoritygeneration',
                              'programs_program', 'ewaf_programsourcestate'), locks):
            self.assertIn('`' + table + '`', sql)
        application = next(i for i,q in enumerate(locks) if '`programs_programapplication`' in q)
        member = next(i for i,q in enumerate(locks) if '`members_member`' in q)
        self.assertGreater(application, 3)
        self.assertGreater(member, application)


class SourceConcurrencyTests(SourceHelpers, TermsHelpers, TransactionTestCase):
    def setUp(self):
        private_media(self)
        self.setup_terms(draft=True)
        self.register()

    def test_two_connections_same_expected_generation_have_one_winner(self):
        expected = self.expected()
        data = self.edit_data(name='Fictional concurrent mutation')
        entered, release, attempted = Event(), Event(), Event()
        real_invalidate, real_boundary = generation._invalidate, generation.durable_services._boundary
        def hold(*args, **kwargs):
            entered.set()
            if not release.wait(20):
                raise RuntimeError('Fictional concurrency timeout')
            return real_invalidate(*args, **kwargs)
        def boundary():
            if entered.is_set():
                attempted.set()
            return real_boundary()
        def mutate():
            try:
                programs.save_program(pk=self.program.pk, user=self.officer, data=data, source_expected=expected)
                return 'committed'
            except ValidationError as exc:
                return str(exc)
        with patch.object(generation, '_invalidate', hold), patch.object(generation.durable_services, '_boundary', boundary):
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
                a,b = first.result(30), second.result(30)
        self.assertNotEqual(a[0], b[0])
        self.assertEqual(a[1], 'committed')
        self.assertIn('STALE_GENERATION', b[1])
        self.assert_transition(2)

    def test_authority_revocation_invalidates_source_submission(self):
        from django.contrib.auth.models import Group
        expected = self.expected()
        group = Group.objects.create(name='Fictional authority change')
        authority_services.mutate_relation(user=self.officer, model=get_user_model(), pk=self.officer.pk,
            relation='groups', operation='add', related_ids=[group.pk])
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION'):
            programs.save_program(pk=self.program.pk, user=self.officer, data=self.edit_data(), source_expected=expected)
        state = ProgramSourceState.objects.get(program=self.program)
        self.assertEqual((state.generation, state.revision), (1, 1))
        self.assertEqual(AuthorityGeneration.objects.get(pk=1).generation, 2)

    def test_failed_first_writer_leaves_waiting_writer_token_valid(self):
        expected, data = self.expected(), self.edit_data(name='Fictional committed after rollback')
        entered, release, attempted = Event(), Event(), Event()
        original, boundary = generation._invalidate, generation.durable_services._boundary
        calls = []
        def fail_first(*args, **kwargs):
            calls.append(True)
            if len(calls) == 1:
                entered.set()
                if not release.wait(20):
                    raise RuntimeError('Fictional test timeout')
                raise ValidationError('Fictional first writer rollback')
            return original(*args, **kwargs)
        def signal_boundary():
            if entered.is_set():
                attempted.set()
            return boundary()
        def mutate():
            try:
                programs.save_program(pk=self.program.pk, user=self.officer, data=data, source_expected=expected)
                return 'committed'
            except ValidationError as exc:
                return str(exc)
        with patch.object(generation, '_invalidate', fail_first), patch.object(generation.durable_services, '_boundary', signal_boundary):
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
                a,b = first.result(30), second.result(30)
        self.assertNotEqual(a[0], b[0])
        self.assertIn('first writer rollback', a[1])
        self.assertEqual(b[1], 'committed')
        self.assert_transition(2)
