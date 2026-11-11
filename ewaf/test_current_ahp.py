from copy import deepcopy
from decimal import Decimal, ROUND_FLOOR, localcontext
from fractions import Fraction
import random

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .weight_input import CURRENT_METHOD, METHOD, project, validate_provenance
from .revised.contracts import validate_weight_total

ROUNDING_PROPOSAL = {'order': ['HM', 'ES', 'SES', 'PA'],
                    'weights': {'ES': 1791, 'HM': 6715, 'PA': 747, 'SES': 747}}


class CurrentAHPTests(SimpleTestCase):
    def test_reported_rounding_failure_is_fixed_only_for_new_projection(self):
        old_pairs, old, old_origin = project(ROUNDING_PROPOSAL)
        self.assertEqual(sum(Fraction(value) for value in old['weights'].values()) - 1, Fraction(1, 10 ** 50))
        with self.assertRaises(ValidationError):
            validate_weight_total(old['weights'])
        pairs, result, origin = project(ROUNDING_PROPOSAL, method=CURRENT_METHOD)
        self.assertEqual(pairs, old_pairs)
        self.assertEqual(result['reference_consistency'], 'PASSED')
        self.assertLessEqual(validate_weight_total(result['weights']), 1)
        # Independently reproduce the column-normalized row averages as fractions.
        names = ROUNDING_PROPOSAL['order']
        matrix = {a: {b: Fraction(1) for b in names} for a in names}
        for pair, value in pairs.items():
            a, b = pair.split(':')
            matrix[a][b], matrix[b][a] = Fraction(value), 1 / Fraction(value)
        expected = {a: sum(matrix[a][b] / sum(matrix[c][b] for c in names) for b in names) / 4 for a in names}
        with localcontext() as context:
            context.prec, context.rounding = 50, ROUND_FLOOR
            for code, value in expected.items():
                self.assertEqual(Decimal(result['weights'][code]), Decimal(value.numerator) / Decimal(value.denominator))
                self.assertLessEqual(Fraction(result['weights'][code]), value)
        self.assertEqual(project(ROUNDING_PROPOSAL), (old_pairs, old, old_origin))
        validate_provenance(origin, pairs)
        forged = deepcopy(origin)
        forged['method'] = 'unsupported'
        with self.assertRaises(ValidationError):
            validate_provenance(forged, pairs)

    def test_valid_adjustments_have_bounded_weights_without_changing_priority_or_scale(self):
        rng = random.Random(27)
        for _ in range(250):
            values = sorted((rng.randrange(1000, 5000) for _ in range(4)), reverse=True)
            total = sum(values)
            values = [value * 10000 // total for value in values]
            values[0] += 10000 - sum(values)
            proposal = {'order': ['SES', 'ES', 'PA', 'HM'], 'weights': dict(zip(['SES', 'ES', 'PA', 'HM'], values))}
            pairs, result, _ = project(proposal, method=CURRENT_METHOD)
            validate_weight_total(result['weights'])
            actual = [Fraction(result['weights'][code]) for code in proposal['order']]
            self.assertEqual(actual, sorted(actual, reverse=True))
            self.assertTrue(all(Fraction(1, 9) <= Fraction(value) <= 9 for value in pairs.values()))
        bad = deepcopy(ROUNDING_PROPOSAL)
        bad['weights']['HM'] += 1
        for method in (METHOD, CURRENT_METHOD):
            with self.assertRaises(ValidationError):
                project(bad, method=method)
