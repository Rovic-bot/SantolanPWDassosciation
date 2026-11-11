"""Separate four-criterion Decimal reference and fictional workflow tests."""
from decimal import Decimal, localcontext

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import SimpleTestCase, TransactionTestCase

from .four_criterion_reference import calculate_reference
from .four_criterion_development import ahp, PAIRS, fictional_demonstration, policy_readiness
from .test_source_writers import SourceHelpers


class FourMathematicsTests(SimpleTestCase):
    def test_exact_reference_outputs_preserved(self):
        reference, actual = calculate_reference(), ahp()
        for key in ('matrix', 'normalized_matrix', 'column_totals', 'weights', 'WSV', 'CV', 'lambda_estimate', 'CI', 'RI', 'CR'):
            self.assertEqual(actual[key], reference[key])

    def test_equal_comparisons_derive_equal_weights(self):
        result = ahp({pair: '1' for pair in PAIRS})
        self.assertEqual(set(result['weights'].values()), {'0.25'})
        self.assertEqual(result['CR'], '0')

    def test_missing_extra_invalid_and_nonfinite_judgments_rejected(self):
        values = {pair: '1' for pair in PAIRS}
        for changed in ({}, {**values, 'PR:SI': '1'}, {**values, PAIRS[0]: 'NaN'},
                        {**values, PAIRS[0]: 2}, {**values, PAIRS[0]: '0'}, {**values, PAIRS[0]: '10'}):
            with self.subTest(value=changed), self.assertRaises(ValidationError):
                ahp(changed)

    def test_reciprocal_scale_and_local_decimal_context(self):
        pairs = {pair: '1' for pair in PAIRS}
        pairs[PAIRS[0]] = '1/3'
        with localcontext() as context:
            context.prec = 7
            result = ahp(pairs)
        self.assertEqual(result['matrix'][1][0], '3.0000000000000000000000000000000000000000000000000'.rstrip('0').rstrip('.'))
        self.assertGreater(len(result['weights']['SI']), 30)

    def test_policy_stays_blocked_without_inferred_dates(self):
        result = policy_readiness()
        self.assertEqual(result['state'], 'BLOCKED_POLICY')
        self.assertFalse(result['operational_ready'])
        self.assertIsNone(result['amendment_approval_date'])
        self.assertEqual(result['authorized_programs'], [])

    def test_no_historical_criterion_constant_changed(self):
        from .normalization import CRITERIA
        self.assertEqual(tuple(CRITERIA), ('SI', 'ES', 'PA', 'ND', 'PR'))
        self.assertEqual(ahp()['criteria'], ['SI', 'ES', 'PA', 'ND'])

    def test_fictional_workflow_unavailable_without_session(self):
        with self.assertRaises(PermissionDenied):
            fictional_demonstration()


class FourWorkflowTests(SourceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_foundation()
        self.register()

    def test_complete_inventory_and_four_traces_without_pr_contribution(self):
        result = fictional_demonstration()
        self.assertEqual((result['retained_count'], result['eligible_count']), (3, 2))
        self.assertEqual(len(result['results']), 2)
        for row in result['results']:
            self.assertEqual([t['criterion'] for t in row['traces']], ['SI', 'ES', 'PA', 'ND'])
            self.assertFalse(row['actually_assisted'])
            self.assertIsNone(row['business_rank'])
        self.assertFalse(result['operational_ready'])
        self.assertEqual(result, fictional_demonstration())

    def test_pending_evidence_blocks_complete_pool_without_dropping_inventory(self):
        result = fictional_demonstration(pending=True)
        self.assertEqual(len(result['inventory']), 3)
        self.assertFalse(result['complete_demonstration'])
        self.assertEqual(result['results'], [])

    def test_human_choice_changes_no_application_or_release(self):
        from assistance.models import AssistanceRelease, AssistanceCase
        from programs.models import ProgramApplication
        before = (AssistanceRelease.objects.count(), AssistanceCase.objects.count(), ProgramApplication.objects.count())
        result = fictional_demonstration(selected='DEMO-B')
        self.assertEqual(result['selected'], 'DEMO-B')
        self.assertEqual(result['selection_effect'], 'NONE')
        self.assertEqual(before, (AssistanceRelease.objects.count(), AssistanceCase.objects.count(), ProgramApplication.objects.count()))

    def test_pending_or_foreign_selection_denied(self):
        for values in ({'pending': True, 'selected': 'DEMO-A'}, {'selected': 'actual-member'}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                fictional_demonstration(**values)

    def test_inconsistent_comparisons_block_example(self):
        pairs = {pair: '1' for pair in PAIRS}
        pairs.update({'SI:ES': '9', 'ES:PA': '9', 'SI:PA': '1/9'})
        result = fictional_demonstration(judgments=pairs)
        self.assertIn('AHP_CONSISTENCY_NOT_PASSED', result['blockers'])
        self.assertEqual(result['results'], [])
