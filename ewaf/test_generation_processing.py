"""Complete fictional development protocol; real disposable MySQL transactions."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import timedelta
from threading import Event
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone

from accounts.tests.test_authority_generation import worker
from documents.services import verify_document
from members.services import change_status
from programs.models import ProgramApplication, ProgramLog
from programs.testsupport import application_fixture
from members.tests import create_member
from . import generation_processing as processing, generation_services as generation, durable_services as durable
from .durable_models import DurableRun, DurableAttempt, DurableOutcome, DurableResult, DurableTrace
from .generation_models import ProgramSourceState, RequestSourceBinding, RunSourceBinding, DevelopmentPromotion, SourceMutationBatch
from .generation_protocol import COVERAGE
from .durable_testsupport import DurableHelpers
from .test_source_writers import SourceHelpers


class ProcessingTests(SourceHelpers, DurableHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()
        self.register()

    def context_new(self):
        return processing.inspect_context(self.program.pk, user=self.officer, contract=self.contract)

    def accept(self, key='fictional-integrated-1', **changes):
        context = self.context_new()
        return processing.accept_request(self.program.pk, **{'user': self.officer, 'request_key': key,
            'expected': context['expected'], 'expected_context': context['context_digest'],
            'contract': self.contract, 'reason': 'Fictional complete-pool calculation', **changes})

    def process_new(self, request):
        return processing.process_request(request.pk, program_id=self.program.pk, user=self.officer)

    def current(self):
        return processing.inspect_current(self.program.pk, user=self.officer)

    def test_complete_graph_promotes_once_and_retries_current(self):
        request = self.accept()
        binding = RequestSourceBinding.objects.get(request=request)
        self.assertEqual(binding.coverage_contract, COVERAGE)
        run = self.process_new(request)
        result = self.current()
        self.assertEqual(result['run_id'], run.pk)
        self.assertTrue(result['atomic_freshness'])
        self.assertFalse(result['operational_ready'])
        self.assertEqual((result['source_generation'], result['revision']), (1, 2))
        self.assertEqual(self.process_new(request).pk, run.pk)
        self.assertEqual(DevelopmentPromotion.objects.count(), 1)
        self.assertEqual(DurableTrace.objects.filter(result__run=run).count(), 5)
        retry = self.accept(expected=processing._expected(binding))
        self.assertEqual(retry.pk, request.pk)

    def test_old_processor_and_inspector_refuse_integrated_request(self):
        request = self.accept()
        with self.assertRaisesMessage(ValidationError, 'USE_GENERATION_DEVELOPMENT_PROTOCOL'):
            self.process(request)
        run = self.process_new(request)
        with self.assertRaisesMessage(ValidationError, 'USE_GENERATION_DEVELOPMENT_PROTOCOL'):
            durable.inspect_development_result(run.pk, program_id=self.program.pk, user=self.officer)
        historical = durable.inspect_development_history(run.pk, program_id=self.program.pk, user=self.officer)
        self.assertIsNone(historical['sources_match_now'])
        with patch('accounts.authority_services.enlisted', return_value=False):
            with self.assertRaisesMessage(ValidationError, 'USE_GENERATION_DEVELOPMENT_PROTOCOL'):
                self.process(request)

    def test_old_unbound_request_remains_historical_only(self):
        request = self.request_run()
        run = self.process(request)
        durable._assert_history(run)
        self.assertFalse(DevelopmentPromotion.objects.exists())
        with self.assertRaisesMessage(ValidationError, 'INTEGRATED_REQUEST_BINDING_REQUIRED'):
            self.process_new(request)

    def test_legacy_foundation_binding_cannot_promote(self):
        request = self.request_run()
        run = self.process(request)
        expected = self.token()
        with generation._fence(self.officer, [self.program.pk]) as (_, authority, _, states):
            generation._bind_request(request, run.snapshot, state=states[self.program.pk], authority=authority,
                expected=expected, valid_until=timezone.now() + timedelta(minutes=1))
        with self.assertRaisesMessage(ValidationError, 'INTEGRATED_REQUEST_BINDING_REQUIRED'):
            self.process_new(request)

    def test_stale_and_inconsistent_expected_tokens(self):
        for field, value in (('source_generation', 2), ('authority_generation', 2), ('revision', 2), ('current_binding', 55)):
            context = self.context_new()
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.accept(expected={**context['expected'], field: value})
        self.assertFalse(RequestSourceBinding.objects.exists())

    def test_source_change_then_restore_does_not_restore_request(self):
        request = self.accept()
        for status in ('inactive', 'active'):
            self.member.refresh_from_db()
            change_status(self.member.pk, user=self.officer, version=self.member.version,
                status=status, notes='Fictional ABA member transition', source_expected=self.expected())
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION_TOKEN'):
            self.process_new(request)
        self.assertFalse(DurableRun.objects.exists())

    def test_document_review_invalidates_promoted_result_and_retains_history(self):
        run = self.process_new(self.accept())
        old = (run.digest, run.context_digest, run.snapshot)
        verify_document(self.document.pk, user=self.officer, member_version=self.member.version,
            verified=False, expires_on=None, reason='Fictional renewed review', source_expected=self.expected())
        with self.assertRaisesMessage(ValidationError, 'NO_CURRENT_DEVELOPMENT_RESULT'):
            self.current()
        run.refresh_from_db()
        self.assertEqual(old, (run.digest, run.context_digest, run.snapshot))
        durable._assert_history(run)
        self.assertEqual(DevelopmentPromotion.objects.count(), 1)

    def test_authority_change_logically_invalidates_without_program_fanout(self):
        run = self.process_new(self.accept())
        self.advance_authority()
        self.assertEqual(ProgramSourceState.objects.get(program=self.program).current_binding_id, run.pk)
        self.assertEqual(ProgramSourceState.objects.get(program=self.program).generation, 1)
        with self.assertRaisesMessage(ValidationError, 'STALE_DEVELOPMENT_GENERATION'):
            self.current()

    def test_expiry_clears_pointer_once_and_clock_rollback_does_not_restore(self):
        run = self.process_new(self.accept())
        limit = RunSourceBinding.objects.get(run=run).request_binding.valid_until
        with patch('ewaf.generation_processing.timezone.now', return_value=limit):
            with self.assertRaisesMessage(ValidationError, 'DEVELOPMENT_RESULT_EXPIRED'):
                self.current()
        self.assertEqual(SourceMutationBatch.objects.filter(kind='EXPIRY').count(), 1)
        with self.assertRaisesMessage(ValidationError, 'NO_CURRENT_DEVELOPMENT_RESULT'):
            self.current()
        self.assertEqual(SourceMutationBatch.objects.filter(kind='EXPIRY').count(), 1)
        durable._assert_history(run)

    def test_expired_request_never_creates_graph(self):
        request = self.accept()
        limit = RequestSourceBinding.objects.get(request=request).valid_until
        with patch('ewaf.generation_processing.timezone.now', return_value=limit):
            with self.assertRaisesMessage(ValidationError, 'DEVELOPMENT_REQUEST_EXPIRED'):
                self.process_new(request)
        self.assertFalse(DurableRun.objects.exists())

    def test_completed_retry_expiry_is_sticky(self):
        request = self.accept()
        run = self.process_new(request)
        limit = RunSourceBinding.objects.get(run=run).request_binding.valid_until
        with patch('ewaf.generation_processing.timezone.now', return_value=limit):
            with self.assertRaisesMessage(ValidationError, 'DEVELOPMENT_RESULT_EXPIRED'):
                self.process_new(request)
        self.assertIsNone(ProgramSourceState.objects.get(program=self.program).current_binding_id)
        self.assertEqual(SourceMutationBatch.objects.filter(kind='EXPIRY').count(), 1)

    def test_context_expiry_commits_invalidation_before_error(self):
        run = self.process_new(self.accept())
        limit = RunSourceBinding.objects.get(run=run).request_binding.valid_until
        with patch('ewaf.generation_processing.timezone.now', return_value=limit):
            with self.assertRaisesMessage(ValidationError, 'DEVELOPMENT_RESULT_EXPIRED'):
                self.context_new()
        self.assertIsNone(ProgramSourceState.objects.get(program=self.program).current_binding_id)

    def test_logically_stale_authority_pointer_can_be_explicitly_replaced(self):
        first = self.process_new(self.accept())
        self.advance_authority()
        request = self.accept('fictional-authority-replacement', previous_id=first.pk)
        second = self.process_new(request)
        self.assertEqual(second.previous_id, first.pk)
        self.assertEqual(self.current()['authority_generation'], 2)

    def test_complete_inventory_rechecks_new_after_cutoff_application(self):
        request = self.accept()
        # Unsupported fixture mutation intentionally bypasses generation to prove
        # dependency capture remains necessary in addition to the counter check.
        application_fixture(self.program, create_member('FICTIONAL-LATE-INVENTORY'))
        with self.assertRaisesMessage(ValidationError, 'CONTEXT_CHANGED'):
            self.process_new(request)
        self.assertFalse(DurableRun.objects.exists())

    def test_incomplete_in_scope_applicant_blocks_instead_of_disappearing(self):
        application_fixture(self.program, create_member('FICTIONAL-PENDING-INVENTORY'))
        self.contract = {**self.contract, 'cutoff': timezone.now().isoformat()}
        with self.assertRaisesMessage(ValidationError, 'ELIGIBILITY_UNRESOLVED'):
            self.accept()
        self.assertEqual(ProgramApplication.objects.filter(program=self.program).count(), 2)

    def test_partial_results_and_traces_never_promote(self):
        request = self.accept()
        original = durable._calculate
        with patch.object(durable, '_calculate', return_value={}):
            with self.assertRaises(ValidationError):
                self.process_new(request)
        self.assertFalse(DurableRun.objects.exists())
        # Leave replay unmodified; omit only one persistence write.
        persist = durable._persist
        def omit(row):
            if isinstance(row, DurableTrace) and row.criterion == 'ND':
                return row
            return persist(row)
        with patch.object(durable, '_persist', side_effect=omit):
            with self.assertRaises(ValidationError):
                self.process_new(request)
        self.assertFalse(DevelopmentPromotion.objects.exists())
        self.assertFalse(DurableRun.objects.exists())
        self.assertEqual(DurableOutcome.objects.filter(status='FAILED').count(), 2)

    def test_promotion_audit_failure_rolls_back_entire_graph(self):
        request = self.accept()
        original = generation._persist
        def fail(row):
            if isinstance(row, DevelopmentPromotion):
                raise ValidationError('Fictional promotion audit failure')
            return original(row)
        with patch.object(generation, '_persist', side_effect=fail), self.assertRaises(ValidationError):
            self.process_new(request)
        self.assertFalse(DurableRun.objects.exists())
        self.assertFalse(RunSourceBinding.objects.exists())
        self.assertIsNone(ProgramSourceState.objects.get(program=self.program).current_binding_id)
        self.assertEqual(DurableOutcome.objects.get().status, 'FAILED')
        self.process_new(request)
        self.assertEqual(DevelopmentPromotion.objects.count(), 1)

    def test_promotion_cas_failure_rolls_back_graph_and_audit(self):
        from .generation_records import StateQuerySet
        request = self.accept()
        original = StateQuerySet.update
        def fail(queryset, **kwargs):
            if 'current_binding' in kwargs and kwargs['current_binding'] is not None:
                return 0
            return original(queryset, **kwargs)
        with patch.object(StateQuerySet, 'update', fail), self.assertRaisesMessage(ValidationError, 'STALE_PROMOTION_CAS'):
            self.process_new(request)
        self.assertFalse(DurableRun.objects.exists())
        self.assertFalse(DevelopmentPromotion.objects.exists())

    def test_explicit_replacement_preserves_predecessor_and_clears_before_processing(self):
        first = self.process_new(self.accept())
        before = first.digest
        context = self.context_new()
        second_request = self.accept('fictional-replacement', previous_id=first.pk)
        self.assertIsNone(ProgramSourceState.objects.get(program=self.program).current_binding_id)
        self.assertEqual(self.accept('fictional-replacement', previous_id=first.pk,
            expected=context['expected']).pk, second_request.pk)
        second = self.process_new(second_request)
        self.assertEqual(second.previous_id, first.pk)
        first.refresh_from_db()
        self.assertEqual(first.digest, before)
        self.assertEqual(self.current()['run_id'], second.pk)
        with self.assertRaises(ValidationError):
            self.process_new(first.request)

    def test_failed_replacement_acceptance_restores_prior_pointer(self):
        first = self.process_new(self.accept())
        with patch.object(generation, '_bind_request', side_effect=ValidationError('Fictional binding failure')):
            with self.assertRaises(ValidationError):
                self.accept('fictional-replacement', previous_id=first.pk)
        self.assertEqual(self.current()['run_id'], first.pk)
        self.assertFalse(SourceMutationBatch.objects.filter(kind='REPLACEMENT').exists())

    def test_failed_replacement_processing_does_not_restore_predecessor(self):
        first = self.process_new(self.accept())
        request = self.accept('fictional-replacement', previous_id=first.pk)
        with patch.object(durable, '_calculate', side_effect=ValidationError('Fictional computation failure')):
            with self.assertRaises(ValidationError):
                self.process_new(request)
        with self.assertRaises(ValidationError):
            self.current()
        durable._assert_history(first)

    def test_explicit_interruption_recovery(self):
        request = self.accept()
        with processing._fence(self.program.pk, self.officer) as (actor, _, program, _, _):
            durable._persist(DurableAttempt(program=program, request=request, ordinal=1,
                **durable.reasoned(actor, 'Fictional interrupted worker', True)))
        with self.assertRaisesMessage(ValidationError, 'ATTEMPT_IN_PROGRESS_OR_INTERRUPTED'):
            self.process_new(request)
        processing.close_interrupted(request.pk, program_id=self.program.pk, user=self.officer,
            reason='Fictional explicit worker recovery')
        self.process_new(request)
        self.assertEqual(DurableAttempt.objects.count(), 2)

    def test_unregistered_and_operational_access_denied(self):
        with patch('accounts.authority_services.enlisted', return_value=False):
            with self.assertRaises(PermissionDenied):
                self.context_new()
        with self.assertRaises(ValidationError):
            durable.require_operational_result()

    def writer_during_calculation(self, mutation):
        request = self.accept()
        entered, release = Event(), Event()
        original = durable._calculate
        def pause(snapshot):
            entered.set()
            if not release.wait(20):
                raise RuntimeError('Fictional writer matrix timeout')
            return original(snapshot)
        with patch.object(durable, '_calculate', side_effect=pause), ThreadPoolExecutor(2) as pool:
            calculation = pool.submit(worker, lambda: self.process_new(request))
            self.assertTrue(entered.wait(15))
            try:
                pool.submit(worker, mutation).result(timeout=15)
            finally:
                release.set()
            with self.assertRaises(ValidationError):
                calculation.result(timeout=25)
        self.assertFalse(DevelopmentPromotion.objects.exists())
        self.assertFalse(DurableRun.objects.exists())

    def test_member_writer_race(self):
        self.writer_during_calculation(lambda: change_status(self.member.pk, user=self.officer,
            version=self.member.version, status='inactive', notes='Fictional member race', source_expected=self.expected()))

    def test_document_writer_race(self):
        self.writer_during_calculation(lambda: verify_document(self.document.pk, user=self.officer,
            member_version=self.member.version, verified=True, expires_on=None,
            reason='Fictional evidence race', source_expected=self.expected()))

    def test_eligibility_writer_race(self):
        from assistance.services import review_eligibility
        from assistance.tests import review_data
        self.writer_during_calculation(lambda: review_eligibility(self.application.pk, user=self.officer,
            data=review_data(self.application, **{f'check_{self.relevance_requirement.pk}': 'pass'}),
            source_expected=self.expected()))

    def test_reference_admin_writer_race(self):
        from django.urls import reverse
        from django.test import Client
        client = Client()
        client.force_login(self.officer)
        def mutation():
            response = client.post(reverse('admin:documents_documenttype_add'),
                {'name': 'Fictional metadata racing promotion', 'description': ''})
            self.assertEqual(response.status_code, 302)
        self.writer_during_calculation(mutation)

    def test_authority_writer_race(self):
        self.writer_during_calculation(lambda: self.advance_authority())

    def test_program_publication_writer_race(self):
        from programs.services import change_publication
        self.writer_during_calculation(lambda: change_publication(self.program.pk, user=self.officer,
            version=self.program.version, action='cancelled', notes='Fictional publication race', source_expected=self.expected()))

    def test_deadline_crossed_during_calculation(self):
        request = self.accept()
        limit = RequestSourceBinding.objects.get(request=request).valid_until
        original = durable._calculate
        clock = patch('ewaf.generation_processing.timezone.now', return_value=limit)
        def calculate(snapshot):
            result = original(snapshot)
            clock.start()
            return result
        try:
            with patch.object(durable, '_calculate', side_effect=calculate), self.assertRaises(ValidationError):
                self.process_new(request)
        finally:
            clock.stop()
        self.assertFalse(DurableRun.objects.exists())

    def test_deadline_after_cas_rolls_back_graph_before_return(self):
        request = self.accept()
        limit = RequestSourceBinding.objects.get(request=request).valid_until
        original = processing._promote
        clock = patch('ewaf.generation_processing.timezone.now', return_value=limit)
        def promote(*args):
            result = original(*args)
            clock.start()
            return result
        try:
            with patch.object(processing, '_promote', side_effect=promote), self.assertRaises(ValidationError):
                self.process_new(request)
        finally:
            clock.stop()
        self.assertFalse(DurableRun.objects.exists())
        self.assertFalse(DevelopmentPromotion.objects.exists())
        self.assertIsNone(ProgramSourceState.objects.get(program=self.program).current_binding_id)

    def test_exported_fictional_end_to_end_evidence(self):
        from .four_criterion_development import fictional_demonstration
        from .evidence import canonical
        import json
        import os
        from pathlib import Path
        request = self.accept()
        run = self.process_new(request)
        result = self.current()
        binding = RunSourceBinding.objects.get(run=run)
        example = fictional_demonstration(selected='DEMO-B')
        before = run.digest
        self.review(source_expected=self.expected())
        with self.assertRaises(ValidationError):
            self.current()
        historical = durable.inspect_development_history(run.pk, program_id=self.program.pk, user=self.officer)
        run.refresh_from_db()
        self.assertEqual(before, run.digest)
        if os.environ.get('G12_ARTIFACT_DIR'):
            evidence = {'purpose': 'FICTIONAL_DISPOSABLE_REVIEW_EVIDENCE', 'four_criterion': example,
                'five_criterion_development': result, 'run_digest': run.digest, 'graph_digest': binding.graph_digest,
                'request_binding_digest': binding.request_binding.digest, 'history_after_source_invalidation': historical,
                'pointer_cleared': ProgramSourceState.objects.get(program=self.program).current_binding_id is None,
                'scores': [row.calculation for row in run.results.all()], 'operational_ready': False}
            Path(os.environ['G12_ARTIFACT_DIR'], 'stage8-fictional-demonstration.json').write_text(
                json.dumps(canonical(evidence), indent=2), encoding='utf-8')

    def test_separate_connection_writer_during_calculation_rejects_promotion(self):
        request = self.accept()
        entered, release = Event(), Event()
        original = durable._calculate
        def pause(snapshot):
            entered.set()
            if not release.wait(20):
                raise RuntimeError('Fictional race timeout')
            return original(snapshot)
        with patch.object(durable, '_calculate', side_effect=pause), ThreadPoolExecutor(2) as pool:
            calculation = pool.submit(worker, lambda: self.process_new(request))
            self.assertTrue(entered.wait(15))
            try:
                writer = pool.submit(worker, lambda: self.review(source_expected=self.expected()))
                writer.result(timeout=15)
            finally:
                release.set()
            with self.assertRaises(ValidationError):
                calculation.result(timeout=20)
        self.assertFalse(DevelopmentPromotion.objects.exists())
        self.assertFalse(DurableRun.objects.exists())

    def test_separate_connection_writer_waits_for_promotion_then_clears(self):
        request = self.accept()
        entered, release = Event(), Event()
        original = processing._promote
        def pause(*args):
            result = original(*args)
            entered.set()
            if not release.wait(20):
                raise RuntimeError('Fictional race timeout')
            return result
        with patch.object(processing, '_promote', side_effect=pause), ThreadPoolExecutor(2) as pool:
            calculation = pool.submit(worker, lambda: self.process_new(request))
            self.assertTrue(entered.wait(15))
            writer = pool.submit(worker, lambda: self.review(source_expected=self.expected()))
            try:
                with self.assertRaises(TimeoutError):
                    writer.result(timeout=.25)
            finally:
                release.set()
            calc_id, run = calculation.result(timeout=25)
            writer_id, _ = writer.result(timeout=25)
            self.assertNotEqual(calc_id, writer_id)
        self.assertEqual(DevelopmentPromotion.objects.count(), 1)
        self.assertIsNone(ProgramSourceState.objects.get(program=self.program).current_binding_id)
        durable._assert_history(run)

    def test_separate_connection_competing_requests_have_one_promotion(self):
        first, second = self.accept(), self.accept('fictional-competing-request')
        entered, release = Event(), Event()
        original = durable._calculate
        def pause(snapshot):
            if not entered.is_set():
                entered.set()
                if not release.wait(20):
                    raise RuntimeError('Fictional race timeout')
            return original(snapshot)
        with patch.object(durable, '_calculate', side_effect=pause), ThreadPoolExecutor(2) as pool:
            loser = pool.submit(worker, lambda: self.process_new(first))
            self.assertTrue(entered.wait(15))
            try:
                winner = pool.submit(worker, lambda: self.process_new(second))
                _, run = winner.result(timeout=20)
            finally:
                release.set()
            with self.assertRaises(ValidationError):
                loser.result(timeout=25)
        self.assertEqual(self.current()['run_id'], run.pk)
        self.assertEqual(DevelopmentPromotion.objects.count(), 1)



class CrossProgramReceiptProcessingTests(SourceHelpers, DurableHelpers, TransactionTestCase):
    context_new = ProcessingTests.context_new
    accept = ProcessingTests.accept
    process_new = ProcessingTests.process_new
    writer_during_calculation = ProcessingTests.writer_during_calculation

    def setUp(self):
        from programs.tests import create_program
        from assistance.tests import create_application, review_data, decision_data, release_data
        from assistance.services import review_eligibility, decide_assistance, record_release
        from programs.testsupport import close_non_ewaf_program
        self.setup_durable()
        self.receipt_program = create_program(name='Fictional receipt-only source program')
        self.receipt_application = create_application(program=self.receipt_program, member=self.member)
        review_eligibility(self.receipt_application.pk, user=self.officer, data=review_data(self.receipt_application))
        close_non_ewaf_program(self.receipt_program)
        decide_assistance(self.receipt_application.pk, user=self.officer, data=decision_data(self.receipt_application))
        if 'void' in self._testMethodName:
            self.receipt = record_release(self.receipt_application.pk, user=self.officer, data=release_data(self.receipt_application))
            for code in ('SI', 'ES', 'PA', 'ND', 'PR'):
                self.assess(code)
        self.bootstrap([self.program.pk, self.receipt_program.pk])
        self.register()

    def receipt_expected(self):
        return {str(program.pk): self.token(program) for program in (self.program, self.receipt_program)}

    def test_cross_program_release_racing_calculation_rejects_promotion(self):
        from assistance.services import record_release, previous_assistance_count
        from assistance.tests import release_data
        self.writer_during_calculation(lambda: record_release(self.receipt_application.pk, user=self.officer,
            data=release_data(self.receipt_application), source_expected=self.receipt_expected()))
        self.assertEqual(previous_assistance_count(self.member), 1)
        self.assertEqual(ProgramSourceState.objects.get(program=self.program).generation, 2)

    def test_cross_program_void_racing_calculation_rejects_promotion(self):
        from assistance.services import void_release, previous_assistance_count
        def mutation():
            self.receipt_application.refresh_from_db()
            return void_release(self.receipt_application.pk, self.receipt.pk, user=self.officer,
                data={'version': self.receipt_application.version, 'notes': 'Fictional race void', 'confirm': True},
                source_expected=self.receipt_expected())
        self.writer_during_calculation(mutation)
        self.assertEqual(previous_assistance_count(self.member), 0)
        self.assertEqual(ProgramSourceState.objects.get(program=self.program).generation, 2)
