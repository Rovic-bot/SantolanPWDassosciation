"""G18-A portable reference replay. No applicant values, ORM or source-file dependency."""
from copy import deepcopy
from decimal import Decimal, Inexact, Rounded, ROUND_UP, localcontext
from fractions import Fraction
import json
from pathlib import Path

from django.test import SimpleTestCase
from .ahp_validation import CRITERIA, PAIRS, validate_ahp


def reference_fixture():
    return json.loads((Path(__file__).parent / 'tests_data/g18/computation-reference-v1.json').read_text(encoding='utf-8'))


class ComputationReferenceTests(SimpleTestCase):
    def setUp(self):
        self.fixture = reference_fixture()

    def named_pairs(self, named):
        # Upper triangle in G14 order happens to have terminating decimal values.
        # Fractions are retained in the source matrix, never sent to the G14 parser.
        with localcontext() as ctx:
            ctx.prec = 60
            values = {}
            for pair in PAIRS:
                a, b = pair.split(':')
                fraction = Fraction(named[a][b])
                values[pair] = format(Decimal(fraction.numerator) / Decimal(fraction.denominator), 'f')
        return {'criteria': list(CRITERIA), 'mode': 'pairs', 'values': values}

    def test_source_matrix_maps_by_both_criterion_names_to_exact_ten_pairs(self):
        self.assertEqual(self.fixture['source_order'], ['PA', 'SI', 'ES', 'ND', 'PR'])
        self.assertEqual(self.named_pairs(self.fixture['matrix_by_criterion']), self.fixture['g14_input'])
        self.assertEqual(self.fixture['g14_input']['values'], {
            'SI:ES': '2', 'SI:PA': '3', 'SI:ND': '5', 'SI:PR': '3',
            'ES:PA': '2', 'ES:ND': '4', 'ES:PR': '2', 'PA:ND': '3',
            'PA:PR': '2', 'ND:PR': '0.5',
        })

    def test_reordered_source_rows_and_columns_produce_identical_report(self):
        named = self.fixture['matrix_by_criterion']
        permuted = {row: {col: named[row][col] for col in reversed(list(named[row]))}
                    for row in reversed(list(named))}
        self.assertEqual(validate_ahp(self.named_pairs(permuted)), validate_ahp(self.fixture['g14_input']))

    def test_exact_canonical_matrix_weights_wsv_cv_lambda_ci_cr(self):
        result = validate_ahp(self.fixture['g14_input'])
        self.assertEqual(result['matrix'], self.fixture['expected_matrix'])
        self.assertEqual(result['calculation'], self.fixture['expected_calculation'])
        self.assertTrue(result['complete'])
        self.assertTrue(result['structurally_valid'])
        self.assertEqual(result['consistency'], 'PASSED')
        self.assertEqual(result['reasons'], [])

    def test_independent_exact_rational_oracle_for_every_calculation_stage(self):
        named = self.fixture['matrix_by_criterion']
        matrix = [[Fraction(named[a][b]) for b in CRITERIA] for a in CRITERIA]
        totals = [sum(row[j] for row in matrix) for j in range(5)]
        normalized = [[value / total for value, total in zip(row, totals)] for row in matrix]
        weights = [sum(row) / 5 for row in normalized]
        wsv = [sum(value * weight for value, weight in zip(row, weights)) for row in matrix]
        cv = [value / weight for value, weight in zip(wsv, weights)]
        lam = sum(cv) / 5
        ci = (lam - 5) / 4
        cr = ci / Fraction(28, 25)
        result = validate_ahp(self.fixture['g14_input'])['calculation']
        actual = [*result['column_totals'], *(v for row in result['normalized_matrix'] for v in row),
                  *(result['weights'][code] for code in CRITERIA), *result['WSV'], *result['CV'],
                  result['lambda_estimate'], result['CI'], result['CR']]
        exact = [*totals, *(v for row in normalized for v in row), *weights, *wsv, *cv, lam, ci, cr]
        self.assertEqual(sum(weights), 1)
        self.assertEqual(len(actual), len(exact))
        for actual_value, rational in zip(actual, exact):
            # Exact Fraction subtraction avoids ambient Decimal/float loss. This
            # bound measures finite 50-digit arithmetic error, not policy tolerance.
            self.assertLess(abs(Fraction(actual_value) - rational), Fraction(1, 10**47))

    def test_positional_copy_cannot_substitute_for_name_mapping(self):
        result = validate_ahp({**self.fixture['g14_input'], 'criteria': self.fixture['source_order']})
        self.assertEqual(result['reasons'][0]['code'], 'CRITERION_ORDER_INVALID')
        # A self-consistent matrix mislabeled as G14 order could still pass CR.
        # Verify the names, not just the overall consistency statistic.
        named = self.fixture['matrix_by_criterion']
        wrong = {a: {b: named[source_a][source_b]
                     for b, source_b in zip(CRITERIA, self.fixture['source_order'])}
                 for a, source_a in zip(CRITERIA, self.fixture['source_order'])}
        self.assertNotEqual(self.named_pairs(wrong), self.fixture['g14_input'])

    def test_source_display_rounding_is_not_canonical_input(self):
        result = validate_ahp(self.fixture['g14_input'])['calculation']
        with localcontext() as ctx:
            ctx.prec = 60
            self.assertEqual(Decimal(result['weights']['ES']).quantize(Decimal('.0001')), Decimal('.2482'))
            self.assertNotEqual(Decimal(result['weights']['ES']), Decimal('.2483'))
            self.assertEqual(Decimal(result['CI']).quantize(Decimal('.0001')), Decimal('.0200'))
            self.assertNotEqual(Decimal(result['CI']), Decimal('.0199'))

    def test_ambient_decimal_context_cannot_change_reference_replay(self):
        expected = validate_ahp(self.fixture['g14_input'])
        with localcontext() as ctx:
            ctx.prec, ctx.rounding, ctx.Emin, ctx.Emax = 3, ROUND_UP, -5, 5
            ctx.traps[Inexact] = ctx.traps[Rounded] = True
            self.assertEqual(validate_ahp(self.fixture['g14_input']), expected)

    def test_reference_pass_never_grants_authority_or_mutates_inputs(self):
        original = deepcopy(self.fixture)
        result = validate_ahp(self.fixture['g14_input'])
        self.assertFalse(result['effective_authorization'])
        self.assertFalse(result['operational_ready'])
        self.assertEqual(self.fixture, original)
        self.assertNotIn('score', result)
        self.assertNotIn('rank', result)
