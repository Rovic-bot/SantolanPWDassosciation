"""Fictional Gate 2B transaction/constraint tests on disposable MySQL only."""
from concurrent.futures import ThreadPoolExecutor
from copy import copy
from threading import Barrier, Event
from unittest.mock import patch
import uuid

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, close_old_connections, connection, connections, transaction
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TransactionTestCase

from programs.tests import create_program
from programs.testsupport import private_media
from . import generation_services as service
from .generation_models import (AuthorityGeneration, AuthorityInvalidation, ProgramSourceState,
    SourceMutationBatch, SourceInvalidation, RequestSourceBinding, RunSourceBinding, DevelopmentPromotion)
from .generation_records import MAX_GENERATION, bounded

FOUNDATION_MODELS = (AuthorityGeneration, AuthorityInvalidation, ProgramSourceState,
    SourceMutationBatch, SourceInvalidation, RequestSourceBinding, RunSourceBinding, DevelopmentPromotion)


def worker(action):
    close_old_connections()
    try:
        try:
            return action()
        except ValidationError as exc:
            return exc
    finally:
        connections.close_all()


class FoundationHelpers:
    def setup_foundation(self):
        private_media(self)
        self.officer = get_user_model().objects.create_superuser('fictional_foundation_officer')
        self.program = create_program()

    def bootstrap(self, programs=None):
        authority = service.initialize_authority(user=self.officer, reason='Fictional disposable bootstrap')
        return service.initialize_programs(programs or [self.program.pk], user=self.officer,
            expected_authority_generation=authority.generation, reason='Fictional source bootstrap')

    def token(self, program=None):
        result = service.inspect_foundation((program or self.program).pk, user=self.officer)
        return {key: result[key] for key in ('source_generation', 'authority_generation', 'revision', 'current_binding')}

    def advance(self, expected=None, **kwargs):
        return service.advance_sources(expected if expected is not None else {self.program.pk: self.token()},
            **{'user': self.officer, 'kind': 'REPLACEMENT', 'source_kind': 'foundation',
               'source_id': 'fictional-intent', 'native_audits': [], 'reason_code': 'FICTIONAL_TEST',
               'reason': 'Fictional low-level transition, no source workflow', **kwargs})

    def authority_reference(self):
        from django.contrib.admin.models import LogEntry, CHANGE
        from django.contrib.contenttypes.models import ContentType
        with service._fence(self.officer):
            row = LogEntry.objects.create(user=self.officer, content_type=ContentType.objects.get_for_model(self.officer),
                object_id=str(self.officer.pk), object_repr='Fictional authority fixture', action_flag=CHANGE,
                change_message='Fictional native audit fixture')
            return service.native_reference(row)

    def advance_authority(self, **kwargs):
        return service.advance_authority(**{'user': self.officer, 'expected_generation': 1,
            'kind': 'USER_CHANGE', 'subject_kind': 'user', 'subject_id': str(self.officer.pk),
            'native_audits': [self.authority_reference()], 'reason_code': 'FICTIONAL_TEST',
            'reason': 'Fictional authority transition', **kwargs})


class GenerationFoundationTests(FoundationHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_foundation()

    def test_empty_tables_and_default_disabled_access(self):
        self.assertTrue(all(not model.objects.exists() for model in FOUNDATION_MODELS))
        with self.assertRaisesMessage(ValidationError, 'AUTHORITY_NOT_INITIALIZED'):
            self.token()
        from .durable_services import require_operational_result
        with self.assertRaisesMessage(ValidationError, 'OPERATIONAL_DURABLE_PROCESSING_UNAVAILABLE'):
            require_operational_result()

    def test_bootstrap_is_audited_idempotent_and_never_current(self):
        self.bootstrap()
        before = {m: list(m.objects.values()) for m in FOUNDATION_MODELS}
        self.bootstrap()
        self.assertEqual(before, {m: list(m.objects.values()) for m in FOUNDATION_MODELS})
        self.assertEqual(self.token(), {'source_generation': 1, 'authority_generation': 1,
                                      'revision': 1, 'current_binding': None})
        self.assertEqual(AuthorityInvalidation.objects.count(), 1)
        self.assertEqual(SourceMutationBatch.objects.count(), 1)
        self.assertEqual(SourceInvalidation.objects.count(), 1)
        self.assertFalse(DevelopmentPromotion.objects.exists())

    def test_missing_authority_denies_program_initialization(self):
        with self.assertRaisesMessage(ValidationError, 'AUTHORITY_NOT_INITIALIZED'):
            service.initialize_programs([self.program.pk], user=self.officer,
                expected_authority_generation=1, reason='Fictional test')
        self.assertFalse(ProgramSourceState.objects.exists())

    def test_missing_state_denies_observation_and_transition(self):
        service.initialize_authority(user=self.officer, reason='Fictional bootstrap')
        with self.assertRaisesMessage(ValidationError, 'SOURCE_STATE_NOT_INITIALIZED'):
            self.token()
        with self.assertRaisesMessage(ValidationError, 'SOURCE_STATE_NOT_INITIALIZED'):
            self.advance({self.program.pk: {'source_generation': 1, 'authority_generation': 1,
                                          'revision': 1, 'current_binding': None}})

    def test_invalid_context_and_missing_program_fail_closed(self):
        self.bootstrap()
        for value in (None, {}, {'source_generation': True}):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.advance({self.program.pk: value})
        with self.assertRaises(ValidationError):
            service.initialize_programs([uuid.uuid4()], user=self.officer, expected_authority_generation=1,
                                        reason='Fictional missing program')
        with self.assertRaises(ValidationError):
            service.initialize_programs([self.program.pk] * 2, user=self.officer,
                expected_authority_generation=1, reason='Fictional duplicate scope')

    def test_outer_transaction_rejected(self):
        with transaction.atomic(), self.assertRaisesMessage(ValidationError, 'top-level'):
            service.initialize_authority(user=self.officer, reason='Fictional bootstrap')

    def test_disposable_capability_required(self):
        with patch('scripts.durable_test_runner._identity', None), self.assertRaises(PermissionDenied):
            service.initialize_authority(user=self.officer, reason='Fictional bootstrap')
        self.assertFalse(AuthorityGeneration.objects.exists())

    def test_revoked_permissions_not_hidden_by_cached_user(self):
        self.bootstrap()
        self.officer.has_perm('ewaf.process_durablerequest')
        get_user_model().objects.filter(pk=self.officer.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.advance({self.program.pk: {'source_generation': 1, 'authority_generation': 1,
                                          'revision': 1, 'current_binding': None}})
        self.assertEqual(SourceInvalidation.objects.count(), 1)

    def test_generation_bounds_and_overflow_are_exact_integers(self):
        self.assertEqual(service._next(MAX_GENERATION - 1), MAX_GENERATION)
        for value in (-1, True, 1.0, '1', MAX_GENERATION + 1):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                bounded(value)
        with self.assertRaisesMessage(ValidationError, 'GENERATION_EXHAUSTED'):
            service._next(MAX_GENERATION)

    def test_monotonic_multi_program_batch_and_stale_token(self):
        other = create_program(name='Fictional second scope')
        self.bootstrap([self.program.pk, other.pk])
        expected = {self.program.pk: self.token(), other.pk: self.token(other)}
        batch = self.advance(expected)
        self.assertEqual(batch.scope_count, 2)
        self.assertEqual(SourceInvalidation.objects.filter(batch=batch).count(), 2)
        self.assertEqual(self.token()['source_generation'], 2)
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION_TOKEN'):
            self.advance(expected)
        self.assertEqual(SourceMutationBatch.objects.count(), 2)

    def test_authority_transition_invalidates_tokens_without_program_fanout(self):
        self.bootstrap()
        token = self.token()
        self.advance_authority()
        self.assertEqual(AuthorityGeneration.objects.get().generation, 2)
        self.assertEqual(ProgramSourceState.objects.get().generation, 1)
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION_TOKEN'):
            self.advance({self.program.pk: token})
        with self.assertRaisesMessage(ValidationError, 'STALE_AUTHORITY_GENERATION'):
            self.advance_authority()

    def test_source_change_requires_native_audits(self):
        self.bootstrap()
        with self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT_REQUIRED'):
            self.advance(kind='SOURCE_CHANGE')
        ref = self.authority_reference()
        self.advance(kind='SOURCE_CHANGE', native_audits=[ref])
        self.assertEqual(self.token()['source_generation'], 2)

    def test_duplicate_changed_or_unknown_native_audits_rejected(self):
        self.bootstrap()
        ref = self.authority_reference()
        for refs in ([ref, ref], [{**ref, 'digest': '0' * 64}], [{**ref, 'model': 'auth.user'}],
                     [{**ref, 'pk': '9999999'}]):
            with self.subTest(refs=refs), self.assertRaises(ValidationError):
                self.advance(kind='SOURCE_CHANGE', native_audits=refs)
        self.assertEqual(self.token()['source_generation'], 1)

    def test_native_audit_cannot_be_reused_for_another_transition(self):
        self.bootstrap()
        ref = self.authority_reference()
        self.advance_authority(native_audits=[ref])
        with self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT_ALREADY_ACCOUNTED'):
            self.advance_authority(expected_generation=2, native_audits=[ref])
        self.advance(kind='SOURCE_CHANGE', native_audits=[ref])
        with self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT_ALREADY_ACCOUNTED'):
            self.advance(kind='SOURCE_CHANGE', native_audits=[ref])
        self.assertEqual(AuthorityInvalidation.objects.count(), 2)
        self.assertEqual(SourceInvalidation.objects.count(), 2)

    def test_string_program_tokens_and_duplicate_normalized_scope(self):
        self.bootstrap()
        token = self.token()
        with self.assertRaisesMessage(ValidationError, 'DUPLICATE_PROGRAM_SCOPE'):
            self.advance({self.program.pk: token, str(self.program.pk): token})
        self.advance({str(self.program.pk): token})
        self.assertEqual(self.token()['source_generation'], 2)

    def test_empty_program_bootstrap_is_not_silent_success(self):
        self.bootstrap()
        with self.assertRaisesMessage(ValidationError, 'PROGRAM_INITIALIZATION_SCOPE_REQUIRED'):
            service.initialize_programs([], user=self.officer, expected_authority_generation=1, reason='Fictional')

    def test_low_level_authority_cas_rejects_stale_expected_row(self):
        self.bootstrap()
        stale = AuthorityGeneration.objects.get()
        self.advance_authority()
        event = AuthorityInvalidation.objects.get(after_generation=2)
        with service._fence(self.officer):
            with self.assertRaisesMessage(ValidationError, 'STALE_AUTHORITY_CAS'):
                service._cas_authority(stale, event)
        self.assertEqual(AuthorityGeneration.objects.get().generation, 2)

    def test_invalid_authority_subject_and_sequence_are_rejected(self):
        self.bootstrap()
        with self.assertRaisesMessage(ValidationError, 'AUTHORITY_SUBJECT_MISMATCH'):
            self.advance_authority(subject_kind='group')
        with service._fence(self.officer) as (_, state, _, _):
            event = AuthorityInvalidation.objects.get()
            with self.assertRaisesMessage(ValidationError, 'AUTHORITY_SEQUENCE_CONFLICT'):
                service._cas_authority(state, event)
        self.assertEqual(AuthorityGeneration.objects.get().generation, 1)

    def test_authority_audit_failure_rolls_back_bootstrap(self):
        with patch.object(AuthorityInvalidation, 'save', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                service.initialize_authority(user=self.officer, reason='Fictional bootstrap')
        self.assertFalse(AuthorityGeneration.objects.exists())
        self.assertFalse(AuthorityInvalidation.objects.exists())

    def test_authority_cas_failure_rolls_back_event(self):
        self.bootstrap()
        with patch.object(service, '_cas_authority', side_effect=ValidationError('CAS failure')):
            with self.assertRaises(ValidationError):
                self.advance_authority()
        self.assertEqual(AuthorityGeneration.objects.get().generation, 1)
        self.assertEqual(AuthorityInvalidation.objects.count(), 1)

    def test_source_initialization_audit_failure_rolls_back_inserted_states(self):
        service.initialize_authority(user=self.officer, reason='Fictional bootstrap')
        with patch.object(SourceInvalidation, 'save', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                self.bootstrap()
        self.assertFalse(ProgramSourceState.objects.exists())
        self.assertFalse(SourceMutationBatch.objects.exists())

    def test_batch_audit_failure_rolls_back_transition(self):
        self.bootstrap()
        with patch.object(SourceMutationBatch, 'save', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                self.advance()
        self.assertEqual(self.token()['source_generation'], 1)

    def test_second_program_failure_rolls_back_entire_batch_and_first_cas(self):
        other = create_program(name='Fictional second scope')
        self.bootstrap([self.program.pk, other.pk])
        expected = {self.program.pk: self.token(), other.pk: self.token(other)}
        original, calls = service._cas_source, []
        def fail_second(state, event):
            calls.append(state.pk)
            if len(calls) == 2:
                raise ValidationError('Second CAS failed')
            return original(state, event)
        with patch.object(service, '_cas_source', side_effect=fail_second), self.assertRaises(ValidationError):
            self.advance(expected)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.token(), expected[self.program.pk])
        self.assertEqual(self.token(other), expected[other.pk])
        self.assertEqual(SourceMutationBatch.objects.count(), 1)
        self.assertEqual(SourceInvalidation.objects.count(), 2)

    def test_final_validation_failure_rolls_back_all_writes(self):
        self.bootstrap()
        original = service._validate_batch
        def fail_new(batch):
            original(batch)
            if batch.kind != 'INITIALIZE':
                raise ValidationError('Final validation failed')
        with patch.object(service, '_validate_batch', side_effect=fail_new), self.assertRaises(ValidationError):
            self.advance()
        self.assertEqual(self.token()['source_generation'], 1)
        self.assertEqual(SourceMutationBatch.objects.count(), 1)

    def test_low_level_cas_requires_one_matching_row(self):
        self.bootstrap()
        with service._fence(self.officer, [self.program.pk]) as (_, _, _, states):
            stale = copy(states[self.program.pk])
            service._invalidate([states[self.program.pk]], metadata=service._metadata(self.officer, 'TEST', 'Fictional'),
                kind='REPLACEMENT', source_kind='foundation', source_id='test', native_audits=[])
            event = SourceInvalidation.objects.get(program=self.program, after_generation=2)
            with self.assertRaisesMessage(ValidationError, 'STALE_SOURCE_CAS'):
                service._cas_source(stale, event)
        self.assertEqual(self.token()['source_generation'], 2)

    def test_cross_program_tail_is_service_enforced(self):
        other = create_program(name='Fictional second scope')
        self.bootstrap([self.program.pk, other.pk])
        wrong = ProgramSourceState.objects.get(program=other).last_invalidation_id
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('UPDATE ewaf_programsourcestate SET last_invalidation_id=%s WHERE program_id=%s',
                               [wrong, self.program.pk.hex])
            # SQL permits an existing FK from another program; service rejects it.
            with self.assertRaisesMessage(ValidationError, 'SOURCE_STATE_TAIL_MISMATCH'):
                service._state(ProgramSourceState.objects.get(program=self.program))
            transaction.set_rollback(True)
        self.assertEqual(self.token()['source_generation'], 1)

    def test_incomplete_scope_is_detected(self):
        self.bootstrap()
        batch = SourceMutationBatch.objects.get()
        batch.scope_count = 2
        from .evidence import digest
        batch.digest = digest(batch.payload())
        with self.assertRaisesMessage(ValidationError, 'INCOMPLETE_INVALIDATION_SCOPE'):
            service._validate_batch(batch)

    def test_orm_history_guards_and_protected_actor(self):
        self.bootstrap()
        event = AuthorityInvalidation.objects.get()
        for action in (lambda: event.save(), lambda: event.delete(),
                       lambda: AuthorityInvalidation.objects.update(reason='changed'),
                       lambda: AuthorityInvalidation.objects.all().delete(),
                       lambda: AuthorityInvalidation.objects.bulk_create([event]),
                       lambda: AuthorityInvalidation.objects.bulk_update([event], ['reason']),
                       lambda: AuthorityGeneration.objects.update(generation=2)):
            with self.assertRaises(ValidationError):
                action()
        with self.assertRaises(ProtectedError):
            self.officer.delete()

    def test_sql_constraints_reject_invalid_values(self):
        self.bootstrap()
        statements = [
            ('UPDATE ewaf_authoritygeneration SET id=2', []),
            ('UPDATE ewaf_authoritygeneration SET generation=%s', [MAX_GENERATION + 1]),
            ('UPDATE ewaf_authoritygeneration SET generation=0', []),
            ('UPDATE ewaf_authoritygeneration SET last_event_id=NULL', []),
            ('UPDATE ewaf_authoritygeneration SET last_event_id=%s', ['0' * 32]),
            ('UPDATE ewaf_authorityinvalidation SET after_generation=3', []),
            ('UPDATE ewaf_authorityinvalidation SET kind=%s', ['UNKNOWN']),
            ('UPDATE ewaf_authorityinvalidation SET subject_kind=%s', ['UNKNOWN']),
            ('UPDATE ewaf_authorityinvalidation SET system_code=%s', ['DISPOSABLE_BOOTSTRAP']),
            ('UPDATE ewaf_authorityinvalidation SET reason_code=%s', ['']),
            ('UPDATE ewaf_programsourcestate SET revision=0', []),
            ('UPDATE ewaf_programsourcestate SET generation=%s, revision=%s', [MAX_GENERATION + 1] * 2),
            ('UPDATE ewaf_sourceinvalidation SET after_generation=4', []),
            ('UPDATE ewaf_sourceinvalidation SET after_revision=4', []),
            ('UPDATE ewaf_sourcemutationbatch SET kind=%s', ['UNKNOWN']),
        ]
        for sql, params in statements:
            with self.subTest(sql=sql), self.assertRaises(DatabaseError):
                with transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(sql, params)
        self.assertEqual(self.token()['source_generation'], 1)

    def test_duplicate_audit_sequence_rejected_by_mysql(self):
        self.bootstrap()
        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
            cursor.execute('INSERT INTO ewaf_sourceinvalidation '
                '(recorded_at,digest,before_generation,after_generation,before_revision,after_revision,'
                'cleared_binding_id,program_id,batch_id) SELECT recorded_at,digest,before_generation,'
                'after_generation,before_revision,after_revision,cleared_binding_id,program_id,batch_id '
                'FROM ewaf_sourceinvalidation')

    def test_actual_mysql_schema_constraints_indexes_and_no_permissions(self):
        with connection.cursor() as cursor:
            for model in FOUNDATION_MODELS:
                constraints = connection.introspection.get_constraints(cursor, model._meta.db_table)
                for constraint in model._meta.constraints:
                    self.assertIn(constraint.name, constraints)
                    self.assertTrue(constraints[constraint.name]['check'] or constraints[constraint.name]['unique'])
                for index in model._meta.indexes:
                    self.assertEqual(constraints[index.name]['columns'],
                        [model._meta.get_field(f).column for f in index.fields])
                for field in model._meta.fields:
                    if field.is_relation:
                        self.assertTrue(any(c['foreign_key'] and c['columns'] == [field.column]
                                            for c in constraints.values()))
                self.assertEqual(model._meta.default_permissions, ())
                self.assertNotIn(model, admin.site._registry)
                self.assertFalse(Permission.objects.filter(content_type__app_label='ewaf',
                    content_type__model=model._meta.model_name).exists())

    def test_promotion_cannot_be_recorded_even_in_owned_context(self):
        self.bootstrap()
        with service._fence(self.officer), self.assertRaisesMessage(ValidationError, 'DEVELOPMENT_PROMOTION_UNAVAILABLE'):
            service._validate_record(DevelopmentPromotion())
        self.assertFalse(DevelopmentPromotion.objects.exists())
        self.assertFalse(hasattr(service, 'promote'))
        self.assertFalse(hasattr(service, 'get_current_result'))


class GenerationConcurrencyTests(FoundationHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_foundation()

    def test_concurrent_bootstrap_is_one_audited_generation(self):
        barrier = Barrier(2)
        def action():
            barrier.wait(timeout=15)
            return self.bootstrap()[0].generation
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result(timeout=40) for f in [pool.submit(worker, action) for _ in range(2)]]
        self.assertEqual(results, [1, 1])
        self.assertEqual(AuthorityInvalidation.objects.count(), 1)
        self.assertEqual(SourceInvalidation.objects.count(), 1)

    def test_two_connections_same_expected_token_one_wins(self):
        self.bootstrap()
        expected, barrier = {self.program.pk: self.token()}, Barrier(2)
        def action():
            barrier.wait(timeout=15)
            return self.advance(expected)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = [f.result(timeout=40) for f in [pool.submit(worker, action) for _ in range(2)]]
        self.assertEqual(sum(isinstance(r, ValidationError) for r in results), 1)
        self.assertEqual(self.token()['source_generation'], 2)

        self.assertEqual(SourceInvalidation.objects.count(), 2)

    def test_uncommitted_audit_and_cas_are_not_visible_to_other_connection(self):
        self.bootstrap()
        expected = {self.program.pk: self.token()}
        held, release = Event(), Event()
        original = service._cas_source
        def hold(state, event):
            original(state, event)
            held.set()
            if not release.wait(timeout=15):
                raise RuntimeError('Fictional coordination timeout')
        with patch.object(service, '_cas_source', side_effect=hold), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(worker, lambda: self.advance(expected))
            try:
                self.assertTrue(held.wait(timeout=10))
                self.assertEqual(ProgramSourceState.objects.get().generation, 1)
                self.assertEqual(SourceInvalidation.objects.count(), 1)
            finally:
                release.set()
            self.assertNotIsInstance(future.result(timeout=20), ValidationError)
        self.assertEqual(self.token()['source_generation'], 2)



class GenerationStartupPolicyTests(SimpleTestCase):
    def test_exact_reviewed_foundation_can_remain_unapplied(self):
        from core.management.commands.runlocal import validate_plan
        from core.test_local_startup import planned
        self.assertTrue(validate_plan([planned('ewaf', '0006_source_invalidation_foundation')]))

    def test_changed_foundation_migration_still_blocks(self):
        from core.management.commands.runlocal import validate_plan
        from core.test_local_startup import planned
        from django.core.management.base import CommandError
        with patch('core.management.commands.runlocal.FOUNDATION_SHA256', '0' * 64):
            with self.assertRaises(CommandError):
                validate_plan([planned('ewaf', '0006_source_invalidation_foundation')])

    def test_future_or_reverse_foundation_migration_still_blocks(self):
        from core.management.commands.runlocal import validate_plan
        from core.test_local_startup import planned
        from django.core.management.base import CommandError
        for migration in (planned('ewaf', '0007_future'), planned('ewaf', '0006_source_invalidation_foundation', True)):
            with self.assertRaises(CommandError):
                validate_plan([migration])
