"""Verified fictional applications; no application database or operational use."""
from copy import deepcopy
from unittest.mock import patch
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TransactionTestCase
from .four_testsupport import FourHelpers
from .test_source_writers import SourceHelpers
from . import test_generation_processing as previous_tests
from . import generation_processing as processing, durable_services as durable, four_policy as four
from .durable_models import DurableTrace, DurableRun
from .generation_models import RequestSourceBinding, DevelopmentPromotion


class FourWorkflowTests(SourceHelpers, FourHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()
        if self._testMethodName == "test_four_persistence_and_historical_five_replay":
            self.old_request = self.request_run()
            self.old_run = self.process(self.old_request)
            self.old_digest = self.old_run.digest
        self.register()
        self.install_four()

    context_new = previous_tests.ProcessingTests.context_new
    accept = previous_tests.ProcessingTests.accept
    process_new = previous_tests.ProcessingTests.process_new
    current = previous_tests.ProcessingTests.current
    writer_during_calculation = previous_tests.ProcessingTests.writer_during_calculation

    def test_four_persistence_and_historical_five_replay(self):
        run = self.process_new(self.accept())
        durable._assert_history(run)
        self.assertEqual(run.snapshot['engine'], four.POOL_ENGINE)
        self.assertEqual(DurableTrace.objects.filter(result__run=run).count(), 4)
        self.assertFalse(DurableTrace.objects.filter(result__run=run, criterion='PR').exists())
        binding = RequestSourceBinding.objects.get(request=run.request)
        self.assertEqual(binding.engine_profile, four.BINDING_PROFILE)
        self.assertEqual(self.current()['run_id'], run.pk)
        self.assertFalse(self.current()['operational_ready'])
        self.old_run.refresh_from_db()
        self.assertEqual(self.old_digest, self.old_run.digest)
        durable._assert_history(self.old_run)
        self.assertEqual(self.old_run.results.first().traces.count(), 5)
        result = run.results.first()
        self.assertEqual(result.calculation['criteria'], list(four.CRITERIA))
        self.assertIsNone(result.comparison['business_rank'])

    def test_recalculation_preserves_both_versions(self):
        first = self.process_new(self.accept())
        second = self.process_new(self.accept(key='four-replacement', previous_id=first.pk))
        self.assertEqual(second.previous_id, first.pk)
        self.assertEqual(self.current()['run_id'], second.pk)
        durable._assert_history(first)
        self.assertEqual(DevelopmentPromotion.objects.count(), 2)

    def test_no_five_contract_can_reinterpret_four_policy(self):
        self.contract.pop('profile')
        with self.assertRaisesMessage(ValidationError, 'FOUR_REQUEST_PROFILE_REQUIRED'):
            self.accept()

    def test_no_old_capture_without_generation_owner(self):
        with self.assertRaises(ValidationError):
            self.inspect_pool()

    def test_missing_pr_trace_or_functional_need_blocks_whole_pool(self):
        from .models import CriterionAssessment
        with patch('ewaf.four_pool.eligibility', side_effect=ValidationError('Functional need disputed')):
            with self.assertRaisesMessage(ValidationError, 'Functional need disputed'):
                self.accept()
        self.assertFalse(RequestSourceBinding.objects.exists())
        row = CriterionAssessment.objects.filter(application=self.application, criterion='PR').first()
        from .four_pool import eligibility
        rules = deepcopy(self.four_proposal()['eligibility'])
        rules['functional_need']['accepted_outcome'] = 'disability-label-only'
        with self.assertRaises(ValidationError):
            eligibility(row, rules)

    def test_profile_and_trace_tampering_rejected(self):
        request = self.accept()
        snapshot = RequestSourceBinding.objects.get(request=request).accepted_snapshot
        for mutation in ('profile', 'input', 'eligibility'):
            altered = deepcopy(snapshot)
            key = next(iter(altered['eligible']))
            if mutation == 'profile':
                altered['configuration']['profile'] = 'historical-five'
            elif mutation == 'input':
                altered['eligible'][key]['inputs']['PR'] = {}
            else:
                altered['eligible'][key]['program_relevance_eligibility']['contributes_to_score'] = True
            with self.subTest(mutation=mutation), self.assertRaises(ValidationError):
                durable.validate_snapshot(altered)

    def test_configuration_rollback(self):
        from .models import ConfigurationRevision
        before = ConfigurationRevision.objects.count()
        with patch('ewaf.shared_invalidation.finish', side_effect=ValidationError('audit failure')):
            # The service's imported finish is patched at its use boundary.
            with patch('ewaf.four_services.finish', side_effect=ValidationError('audit failure')):
                with self.assertRaises(ValidationError):
                    self.install_four()
        self.assertEqual(ConfigurationRevision.objects.count(), before)

    def test_policy_requires_every_explicit_test_rule(self):
        for field in ('criteria', 'eligibility', 'purpose'):
            proposed = self.four_proposal()
            proposed.pop(field)
            with self.subTest(field=field), self.assertRaises(ValidationError):
                four.proposal(proposed)

    def test_stale_and_inconsistent_expected_tokens(self):
        for field in ('source_generation', 'authority_generation', 'revision', 'current_binding'):
            context = self.context_new()
            bad = {**context['expected'], field: (context['expected'][field] or 0) + 1}
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.accept(expected=bad)
        self.assertFalse(RequestSourceBinding.objects.exists())

    test_source_change_then_restore_does_not_restore_request = previous_tests.ProcessingTests.test_source_change_then_restore_does_not_restore_request
    test_document_review_invalidates_promoted_result_and_retains_history = previous_tests.ProcessingTests.test_document_review_invalidates_promoted_result_and_retains_history
    test_expiry_clears_pointer_once_and_clock_rollback_does_not_restore = previous_tests.ProcessingTests.test_expiry_clears_pointer_once_and_clock_rollback_does_not_restore
    test_complete_inventory_rechecks_new_after_cutoff_application = previous_tests.ProcessingTests.test_complete_inventory_rechecks_new_after_cutoff_application
    test_incomplete_in_scope_applicant_blocks_instead_of_disappearing = previous_tests.ProcessingTests.test_incomplete_in_scope_applicant_blocks_instead_of_disappearing
    test_partial_results_and_traces_never_promote = previous_tests.ProcessingTests.test_partial_results_and_traces_never_promote
    test_promotion_audit_failure_rolls_back_entire_graph = previous_tests.ProcessingTests.test_promotion_audit_failure_rolls_back_entire_graph
    test_promotion_cas_failure_rolls_back_graph_and_audit = previous_tests.ProcessingTests.test_promotion_cas_failure_rolls_back_graph_and_audit
    test_failed_replacement_processing_does_not_restore_predecessor = previous_tests.ProcessingTests.test_failed_replacement_processing_does_not_restore_predecessor
    test_explicit_interruption_recovery = previous_tests.ProcessingTests.test_explicit_interruption_recovery
    test_member_writer_race = previous_tests.ProcessingTests.test_member_writer_race
    test_document_writer_race = previous_tests.ProcessingTests.test_document_writer_race
    test_authority_writer_race = previous_tests.ProcessingTests.test_authority_writer_race
    test_separate_connection_competing_requests_have_one_promotion = previous_tests.ProcessingTests.test_separate_connection_competing_requests_have_one_promotion
    test_separate_connection_writer_waits_for_promotion_then_clears = previous_tests.ProcessingTests.test_separate_connection_writer_waits_for_promotion_then_clears
    test_separate_connection_writer_during_calculation_rejects_promotion = previous_tests.ProcessingTests.test_separate_connection_writer_during_calculation_rejects_promotion

    def test_oversized_pool_is_rejected_before_capture(self):
        from programs.testsupport import application_fixture
        from members.tests import create_member
        for index in range(128):
            application_fixture(self.program, create_member('FICTIONAL-OVERFLOW-' + str(index)))
        with self.assertRaisesMessage(ValidationError, 'WHOLE_POOL_UNSUPPORTED'):
            self.accept()
        self.assertFalse(RequestSourceBinding.objects.exists())

    def test_arbitrary_pa_window_cannot_mislabel_all_receipts(self):
        proposed = self.four_proposal()
        proposed['criteria']['PA']['observation_period'] = 'Fictional last twelve months'
        with self.assertRaisesMessage(ValidationError, 'FOUR_TEST_POLICY_INCOMPLETE'):
            four.proposal(proposed)
    test_unregistered_and_operational_access_denied = previous_tests.ProcessingTests.test_unregistered_and_operational_access_denied
    test_deadline_crossed_during_calculation = previous_tests.ProcessingTests.test_deadline_crossed_during_calculation
    test_deadline_after_cas_rolls_back_graph_before_return = previous_tests.ProcessingTests.test_deadline_after_cas_rolls_back_graph_before_return
