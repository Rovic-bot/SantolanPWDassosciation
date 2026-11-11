"""Independent boundary and replay checks; no database or fictional approvals."""
from copy import deepcopy
from decimal import Decimal, localcontext
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from . import four_policy as four
from .four_testsupport import FourHelpers


class FourKernelTests(SimpleTestCase):
    def setUp(self):
        self.definitions = FourHelpers().four_proposal()['criteria']
        self.validation = four.ahp()
        self.inputs = {code: {'source_type': rule['source_type'], 'unit': rule['unit'],
            'value': next(iter(rule['encoding'])) if rule['encoding'] else rule['bounds']['upper']}
            for code, rule in self.definitions.items()}

    def calculate(self):
        return four.calculate(inputs=self.inputs, definitions=self.definitions,
            judgments=self.validation['pairs'], validation=self.validation)

    def test_all_upper_bounds_are_exact_weight_sum_with_no_pr(self):
        result = self.calculate()
        with localcontext(four.CONTEXT):
            total = sum(Decimal(weight) for weight in self.validation['weights'].values())
        self.assertEqual(Decimal(result['score_0_1']), total)
        self.assertEqual([row['criterion'] for row in result['traces']], ['SI', 'ES', 'PA', 'ND'])
        self.assertFalse(result['operational_ready'])
        self.assertIsNone(result['classification'])

    def test_inverse_upper_bounds_are_zero(self):
        for rule in self.definitions.values():
            rule['direction'] = 'inverse'
        self.assertEqual(self.calculate()['score_0_100'], '0')

    def test_missing_extra_nonfinite_outside_equal_bound_inputs_fail_closed(self):
        for mutation in ('missing', 'extra', 'nan', 'outside', 'equal'):
            with self.subTest(mutation=mutation):
                original_inputs, original_definitions = deepcopy(self.inputs), deepcopy(self.definitions)
                if mutation == 'missing':
                    self.inputs.pop('SI')
                elif mutation == 'extra':
                    self.inputs['PR'] = self.inputs['SI']
                elif mutation == 'nan':
                    self.inputs['SI']['value'] = 'NaN'
                elif mutation == 'outside':
                    self.inputs['SI']['value'] = '101'
                else:
                    self.definitions['SI']['bounds']['lower'] = '100'
                with self.assertRaises(ValidationError):
                    self.calculate()
                self.inputs, self.definitions = original_inputs, original_definitions

    def test_rounded_or_forged_weights_cannot_replace_exact_replay(self):
        self.validation['weights']['SI'] = '0.4709'
        with self.assertRaisesMessage(ValidationError, 'FOUR_WEIGHT_REPLAY_INVALID'):
            self.calculate()
