from copy import deepcopy
from decimal import Decimal, localcontext, ROUND_UP, ROUND_DOWN, Inexact, Rounded
from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from .ahp_validation import validate_ahp, reference_verdict, CRITERIA, safe_payload
from .configuration_testsupport import equal_judgments
from .evidence import digest


class AHPValidationTests(SimpleTestCase):
    def matrix(self, matrix):
        return {'criteria': list(CRITERIA), 'mode': 'matrix', 'values': matrix}

    def test_equal_matrix_has_independent_expected_weights_and_consistency(self):
        result = validate_ahp(self.matrix([[1] * 5 for _ in range(5)]))
        self.assertTrue(result['complete'])
        self.assertTrue(result['structurally_valid'])
        self.assertEqual(result['consistency'], 'PASSED')
        self.assertEqual(result['calculation']['weights'], dict.fromkeys(CRITERIA, '0.2'))
        self.assertEqual(result['calculation']['lambda_estimate'], '5')
        self.assertEqual(result['calculation']['CR'], '0')
        self.assertFalse(result['effective_authorization'])

    def test_consistent_ratio_matrix_matches_independent_proportions(self):
        vector = [1, 2, 4, 8, 16]
        with localcontext() as context:
            context.prec = 60
            matrix = [[str(Decimal(a) / b) for b in vector] for a in vector]
            # Exact dyadic ratios fit the supported input precision.
            result = validate_ahp(self.matrix(matrix))
            self.assertEqual(result['consistency'], 'PASSED')
            for code, value in zip(CRITERIA, vector):
                self.assertLess(abs(Decimal(result['calculation']['weights'][code]) - Decimal(value) / 31), Decimal('1e-48'))

    def test_pair_entry_derives_reciprocals_and_diagonal(self):
        data = equal_judgments()
        data['values']['SI:ES'] = '3'
        result = validate_ahp(data)
        self.assertEqual(result['matrix'][0][1], '3')
        self.assertTrue(result['matrix'][1][0].startswith('0.3333333333'))
        self.assertEqual([result['matrix'][i][i] for i in range(5)], ['1'] * 5)

    def test_inconsistent_reciprocal_matrix_retains_failed_evidence(self):
        data = equal_judgments()
        data['values']['SI:ES'] = '100'
        result = validate_ahp(data)
        self.assertEqual(result['consistency'], 'FAILED')
        self.assertIsNotNone(result['calculation'])
        self.assertGreaterEqual(Decimal(result['calculation']['CR']), Decimal('.10'))

    def test_reference_boundary_uses_unrounded_strict_comparison(self):
        for value, expected in [('.09999999999999999999', 'PASSED'), ('.10', 'FAILED'), ('.10000000000000000001', 'FAILED'), ('-1e-49', 'NUMERICAL_ANOMALY')]:
            self.assertEqual(reference_verdict(Decimal(value)), expected)

    def test_order_duplicate_missing_and_additional_criteria_rejected(self):
        for order in (list(reversed(CRITERIA)), ['SI'] * 5, list(CRITERIA)[:4], [*CRITERIA, 'XX']):
            self.assertEqual(validate_ahp({**equal_judgments(), 'criteria': order})['reasons'][0]['code'], 'CRITERION_ORDER_INVALID')

    def test_invalid_matrix_structure_never_calculates(self):
        for matrix in (None, {}, [], [[1] * 4] * 5, [[1] * 5] * 6, [1] * 5):
            result = validate_ahp(self.matrix(matrix))
            self.assertEqual(result['reasons'][0]['code'], 'INVALID_STRUCTURE')
            self.assertIsNone(result['calculation'])

    def test_nonpositive_diagonal_and_nonreciprocal_values(self):
        for i, j, value, code in [(0, 1, 0, 'JUDGMENT_NOT_POSITIVE'), (0, 1, -1, 'JUDGMENT_NOT_POSITIVE'),
                                 (0, 0, 2, 'DIAGONAL_NOT_ONE'), (0, 1, 2, 'RECIPROCITY_FAILED')]:
            matrix = [[1] * 5 for _ in range(5)]
            matrix[i][j] = value
            self.assertEqual(validate_ahp(self.matrix(matrix))['reasons'][0]['code'], code)

    def test_invalid_numbers_and_extreme_exponents_are_structured_failures(self):
        for value in ('NaN', 'Infinity', '-Infinity', True, False, '1/3', 'text', [], '1e1000000', '1e-1000000', '9' * 97, 1.5):
            data = equal_judgments()
            data['values']['SI:ES'] = value
            with self.subTest(value=value):
                result = validate_ahp(data)
                self.assertTrue(result['reasons'])
                self.assertIsNone(result['calculation'])

    def test_missing_judgments_are_retained_as_incomplete(self):
        data = equal_judgments()
        del data['values']['SI:ES']
        result = validate_ahp(data)
        self.assertFalse(result['complete'])
        self.assertEqual(result['consistency'], 'UNAVAILABLE')

    def test_unknown_pair_or_mode_not_silently_ignored(self):
        data = equal_judgments()
        data['values']['ES:SI'] = '1'
        self.assertEqual(validate_ahp(data)['reasons'][0]['code'], 'INVALID_STRUCTURE')
        self.assertEqual(validate_ahp({**equal_judgments(), 'mode': 'weights'})['reasons'][0]['code'], 'INVALID_INPUT_MODE')

    def test_canonical_equivalent_values_have_same_report_and_digest(self):
        first = equal_judgments()
        second = deepcopy(first)
        second['values'] = {key: '1.000' for key in reversed(first['values'])}
        self.assertEqual(validate_ahp(first), validate_ahp(second))
        self.assertEqual(digest(validate_ahp(first)), digest(validate_ahp(second)))

    def test_ambient_precision_rounding_exponents_and_traps_do_not_change_results(self):
        data = equal_judgments()
        data['values']['SI:ES'] = '3'
        expected = validate_ahp(data)
        for rounding in (ROUND_UP, ROUND_DOWN):
            with localcontext() as context:
                context.prec = 3
                context.rounding = rounding
                context.Emax, context.Emin = 5, -5
                context.traps[Inexact] = True
                context.traps[Rounded] = True
                self.assertEqual(validate_ahp(data), expected)

    def test_negative_ci_is_not_silently_clamped_or_passed(self):
        matrix = [[1] * 5 for _ in range(5)]
        matrix[0][1] = '0.999999999'
        result = validate_ahp(self.matrix(matrix))
        self.assertEqual(result['consistency'], 'NUMERICAL_ANOMALY')
        self.assertLess(Decimal(result['calculation']['CI']), 0)

    def test_payload_resource_limits_reject_unsafe_storage(self):
        for data in ([[]] * 26, {'x': '1' * 97}, {'x': float('inf')}, [[[[[[1]]]]]]):
            with self.assertRaises(ValidationError):
                safe_payload(data)

    def test_validator_does_not_mutate_input(self):
        data = equal_judgments()
        before = deepcopy(data)
        validate_ahp(data)
        self.assertEqual(data, before)
