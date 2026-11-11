"""Private sidecar primitives preserve old graphs and cannot promote them."""
from copy import copy, deepcopy
from datetime import timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from programs.tests import create_program
from . import generation_services as service
from .durable_services import inspect_development_history
from .durable_testsupport import DurableHelpers
from .evidence import digest
from .generation_models import RequestSourceBinding, RunSourceBinding, DevelopmentPromotion, ProgramSourceState
from .test_generation_foundation import FoundationHelpers


class GenerationBindingTests(DurableHelpers, FoundationHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()
        self.request = self.request_run()
        self.run = self.process(self.request)
        self.bootstrap()
        self.deadline = timezone.now() + timedelta(minutes=2)

    def bind(self, *, deadline=None, expected=None, run=True):
        expected = expected or self.token()
        with service._fence(self.officer, [self.program.pk]) as (_, authority, _, states):
            state = states[self.program.pk]
            binding = service._bind_request(self.request, self.run.snapshot, state=state, authority=authority,
                expected=expected, valid_until=deadline or self.deadline)
            run_binding = service._bind_run(self.run, state=state, authority=authority) if run else None
            return binding, run_binding

    def test_binding_idempotency_exact_snapshot_and_history_preserved(self):
        before = (self.run.digest, self.run.context_digest, deepcopy(self.run.snapshot))
        request_binding, run_binding = self.bind()
        repeated = self.bind()
        self.assertEqual((request_binding.pk, run_binding.pk), (repeated[0].pk, repeated[1].pk))
        self.assertEqual(request_binding.accepted_snapshot, self.run.snapshot)
        self.assertEqual(run_binding.eligible_count, 1)
        self.run.refresh_from_db()
        self.assertEqual(before, (self.run.digest, self.run.context_digest, self.run.snapshot))
        self.assertIsNone(ProgramSourceState.objects.get().current_binding_id)
        self.assertFalse(DevelopmentPromotion.objects.exists())
        result = inspect_development_history(self.run.pk, program_id=self.program.pk, user=self.officer)
        self.assertFalse(result['operational_ready'])
        self.assertIsNone(result['sources_match_now'])

    def test_conflicting_request_retry_is_rejected(self):
        self.bind()
        with self.assertRaisesMessage(ValidationError, 'CONFLICTING_REQUEST_BINDING'):
            self.bind(deadline=self.deadline + timedelta(seconds=1))
        self.assertEqual(RequestSourceBinding.objects.count(), 1)

    def test_aware_non_utc_deadline_survives_mysql_round_trip(self):
        binding, run_binding = self.bind(deadline=self.deadline.astimezone(ZoneInfo('Asia/Manila')))
        before = binding.digest
        binding.refresh_from_db()
        binding.full_clean()
        run_binding.refresh_from_db()
        run_binding.full_clean()
        self.assertEqual(binding.digest, before)
        self.assertEqual(self.bind(deadline=self.deadline)[0].pk, binding.pk)

    def test_expired_request_binding_rejected(self):
        with self.assertRaises(ValidationError):
            self.bind(deadline=timezone.now() - timedelta(seconds=1))
        self.bind()
        with patch('ewaf.generation_services.timezone.now', return_value=self.deadline):
            with self.assertRaises(ValidationError):
                self.bind()
        self.assertEqual(RequestSourceBinding.objects.count(), 1)

    def test_old_bindings_remain_replayable_after_new_generation(self):
        binding, run_binding = self.bind()
        before = (binding.payload(), binding.digest, run_binding.payload(), run_binding.digest)
        self.advance()
        binding.refresh_from_db()
        run_binding.refresh_from_db()
        binding.full_clean()
        run_binding.full_clean()
        self.assertEqual(before, (binding.payload(), binding.digest, run_binding.payload(), run_binding.digest))
        with self.assertRaises(ValidationError):
            self.bind()
        self.assertEqual(RunSourceBinding.objects.count(), 1)

    def test_stale_authority_request_rejected(self):
        expected = self.token()
        self.advance_authority()
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION_TOKEN'):
            self.bind(expected=expected)
        self.assertFalse(RequestSourceBinding.objects.exists())

    def test_request_snapshot_and_cross_program_context_rejected(self):
        other = create_program(name='Fictional wrong program')
        self.bootstrap([other.pk])
        with service._fence(self.officer, [other.pk]) as (_, authority, _, states):
            state = states[other.pk]
            with self.assertRaisesMessage(ValidationError, 'REQUEST_BINDING_CONTEXT_INVALID'):
                service._bind_request(self.request, self.run.snapshot, state=state, authority=authority,
                    expected=service._token(state, authority), valid_until=self.deadline)
        binding, _ = self.bind()
        altered = copy(binding)
        altered.accepted_snapshot = deepcopy(binding.accepted_snapshot)
        altered.accepted_snapshot['manifest'] = []
        altered.digest = digest(altered.payload())
        with self.assertRaises(ValidationError):
            altered.full_clean()

    def test_partial_graph_and_incomplete_trace_cannot_bind(self):
        from .durable_models import DurableTrace
        self.bind(run=False)
        trace = DurableTrace.objects.first()
        # Privileged test SQL removes a trace only inside a rolled-back transaction.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('DELETE FROM ewaf_durabletrace WHERE id=%s', [trace.pk])
            with self.assertRaises(ValidationError):
                service._graph(self.run)
            transaction.set_rollback(True)
        self.bind()

    def test_run_binding_failure_rolls_back_request_sidecar(self):
        with patch.object(RunSourceBinding, 'save', side_effect=RuntimeError('Fictional failure')):
            with self.assertRaises(RuntimeError):
                self.bind()
        self.assertFalse(RequestSourceBinding.objects.exists())
        self.assertFalse(RunSourceBinding.objects.exists())
        self.run.refresh_from_db()
        self.assertTrue(inspect_development_history(self.run.pk,
            program_id=self.program.pk, user=self.officer)['historically_complete'])

    def test_cross_program_binding_links_rejected(self):
        request_binding, run_binding = self.bind()
        other = create_program(name='Fictional other program')
        self.bootstrap([other.pk])
        with service._fence(self.officer, [other.pk]):
            from .generation_models import SourceInvalidation, SourceMutationBatch
            row = SourceInvalidation(batch=SourceMutationBatch.objects.first(), program=other,
                before_generation=1, after_generation=2, before_revision=1, after_revision=2,
                cleared_binding=run_binding)
            with self.assertRaises(ValidationError):
                service._persist(row)
        request_binding.expected_current_binding = run_binding
        request_binding.request.program = other
        request_binding.digest = digest(request_binding.payload())
        with self.assertRaises(ValidationError):
            request_binding.full_clean()

    def test_binding_mysql_checks_and_unique_graph_identity(self):
        self.bind()
        for sql in (
            'UPDATE ewaf_requestsourcebinding SET source_generation=0',
            'UPDATE ewaf_requestsourcebinding SET authority_generation=0',
            'UPDATE ewaf_requestsourcebinding SET expected_state_revision=0',
            "UPDATE ewaf_requestsourcebinding SET protocol='invalid'",
            'UPDATE ewaf_requestsourcebinding SET valid_until=recorded_at',
            'UPDATE ewaf_runsourcebinding SET eligible_count=0',
            'UPDATE ewaf_runsourcebinding SET retained_count=0',
            'INSERT INTO ewaf_runsourcebinding SELECT * FROM ewaf_runsourcebinding',
        ):
            with self.subTest(sql=sql), self.assertRaises(DatabaseError):
                with transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(sql)

    def test_five_criteria_and_four_reference_stay_separate(self):
        self.bind()
        self.assertEqual(set(next(iter(self.run.snapshot['eligible'].values()))['inputs']),
                         {'SI', 'ES', 'PA', 'ND', 'PR'})
        self.assertIn('historical-five', RequestSourceBinding.objects.get().engine_profile)
        self.assertFalse(DevelopmentPromotion.objects.exists())

    def test_promotion_sql_shape_constraints_do_not_create_a_usable_pointer(self):
        self.bind()
        with transaction.atomic():
            # Raw SQL is solely a constraint probe in a transaction always rolled back.
            # It intentionally bypasses the service which unconditionally denies promotion.
            with connection.cursor() as cursor:
                cursor.execute('INSERT INTO ewaf_developmentpromotion '
                    '(recorded_at,digest,source_generation,authority_generation,before_revision,after_revision,'
                    'checked_at,actor_label,reason_code,reason,actor_id,program_id,new_binding_id,previous_binding_id) '
                    'VALUES (%s,%s,1,1,1,2,%s,%s,%s,%s,%s,%s,%s,NULL)',
                    [timezone.now().replace(tzinfo=None), '0' * 64, timezone.now().replace(tzinfo=None),
                     'Fictional SQL fixture', 'TEST', 'Fictional rollback-only SQL constraint probe',
                     self.officer.pk, self.program.pk.hex, self.run.pk])
            self.assertIsNone(ProgramSourceState.objects.get().current_binding_id)
            for sql in ('UPDATE ewaf_developmentpromotion SET source_generation=0',
                        'UPDATE ewaf_developmentpromotion SET authority_generation=0',
                        'UPDATE ewaf_developmentpromotion SET after_revision=1',
                        'UPDATE ewaf_developmentpromotion SET previous_binding_id=new_binding_id'):
                with self.subTest(sql=sql), self.assertRaises(DatabaseError):
                    with transaction.atomic(), connection.cursor() as cursor:
                        cursor.execute(sql)
            transaction.set_rollback(True)
        self.assertFalse(DevelopmentPromotion.objects.exists())
