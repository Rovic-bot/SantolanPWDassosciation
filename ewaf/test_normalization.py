from decimal import localcontext, ROUND_DOWN
from django.test import SimpleTestCase
from .normalization import normalize, number, NumericIssue, decimal_text


class NormalizationTests(SimpleTestCase):
    def test_benefit_endpoints_midpoint_and_zero(self):
        for value, expected in [('0', '0'), ('5', '0.5'), ('10', '1')]:
            self.assertEqual(normalize(value, '0', '10', 'benefit')['normalized'], expected)

    def test_inverse_endpoints_midpoint(self):
        for value, expected in [('0', '1'), ('5', '0.5'), ('10', '0')]:
            self.assertEqual(normalize(value, '0', '10', 'inverse')['normalized'], expected)

    def test_signed_explicit_synthetic_domain(self):
        self.assertEqual(normalize('0', '-10', '10', 'benefit')['normalized'], '0.5')

    def test_missing_is_not_zero(self):
        for value in (None, ''):
            self.assertEqual(normalize(value, '0', '10', 'benefit')['reasons'], ['VALUE_MISSING'])

    def test_bounds_and_direction_pending(self):
        self.assertEqual(normalize('0', None, '1', 'benefit')['reasons'], ['BOUNDS_PENDING'])
        self.assertEqual(normalize('0', '0', '1', None)['reasons'], ['NORMALIZATION_DIRECTION_PENDING'])

    def test_equal_reversed_and_outside_bounds(self):
        for args, reason in [(('1', '1', '1'), 'ZERO_RANGE'), (('1', '2', '0'), 'BOUNDS_ORDER_INVALID'),
                             (('11', '0', '10'), 'VALUE_OUT_OF_BOUNDS')]:
            result = normalize(*args, 'benefit')
            self.assertEqual(result['reasons'], [reason])
            self.assertIsNone(result['normalized'])

    def test_invalid_types_and_nonfinite(self):
        for value in (True, False, 0.5, [], {}, 'NaN', 'Infinity', '-inf', 'x'):
            with self.subTest(value=value):
                self.assertEqual(normalize(value, '0', '1', 'benefit')['reasons'], ['INVALID_NUMBER'])

    def test_numeric_resource_limits(self):
        for value in ('1e999999', '1e-10000', '9' * 200, '0.' + '1' * 41):
            self.assertEqual(normalize(value, '0', '1', 'benefit')['reasons'], ['NUMERIC_RESOURCE_LIMIT'])
        self.assertEqual(normalize(10 ** 10000, '0', '1', 'benefit')['reasons'], ['NUMERIC_RESOURCE_LIMIT'])

    def test_precision_loss_is_not_rounded_into_acceptance(self):
        self.assertEqual(normalize('0', '-1e-40', '1e40', 'benefit')['reasons'], ['NUMERIC_PRECISION_INSUFFICIENT'])

    def test_near_equal_representable_bounds(self):
        self.assertEqual(normalize('1.000000000000000000000000000000000000001', '1',
            '1.000000000000000000000000000000000000002', 'benefit')['normalized'], '0.5')

    def test_ambient_context_independence(self):
        expected = normalize('1', '0', '3', 'benefit')
        with localcontext() as context:
            context.prec = 2
            context.rounding = ROUND_DOWN
            context.Emax = 1
            self.assertEqual(normalize('1', '0', '3', 'benefit'), expected)

    def test_separate_calculated_parser_and_canonical_text(self):
        text = '0.' + '1' * 50
        with self.assertRaises(NumericIssue):
            number(text)
        self.assertEqual(str(number(text, calculated=True)), text)
        self.assertEqual(decimal_text(number('1.000e0')), '1')
        self.assertEqual(number('0.' + '0' * 80 + '1' * 50, calculated=True).adjusted(), -81)
