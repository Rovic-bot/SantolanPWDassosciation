from copy import deepcopy
from unittest.mock import patch
from decimal import localcontext, ROUND_UP
from django.test import SimpleTestCase
from .ahp_validation import validate_ahp, PAIRS
from .normalization import CRITERIA
from .weighted_scoring import calculate_synthetic


def synthetic_case():
    judgments = {'criteria': list(CRITERIA), 'mode': 'pairs', 'values': {key: '1' for key in PAIRS}}
    return {'criteria': list(CRITERIA), 'judgments': judgments, 'validation': validate_ahp(judgments),
            'inputs': {code: {'value': str(i + 1), 'source_type': 'synthetic', 'unit': 'fixture'} for i, code in enumerate(CRITERIA)},
            'definitions': {code: {'source_type': 'synthetic', 'unit': 'fixture', 'direction': 'benefit',
                'bounds': {'method': 'fixed', 'lower': '0', 'upper': '5'}} for code in CRITERIA}}


class WeightedScoringTests(SimpleTestCase):
    def test_exact_independent_wsm_and_contributions(self):
        result = calculate_synthetic(**synthetic_case())
        self.assertTrue(result['complete'])
        self.assertEqual(result['score_0_1'], '0.6')
        self.assertEqual(result['score_0_100'], '60')
        self.assertEqual([t['contribution'] for t in result['traces']], ['0.04', '0.08', '0.12', '0.16', '0.2'])
        self.assertFalse(result['operational_ready'])

    def test_full_precision_g14_weights_retained(self):
        case = synthetic_case()
        case['judgments']['values']['SI:ES'] = '2'
        case['validation'] = validate_ahp(case['judgments'])
        result = calculate_synthetic(**case)
        self.assertTrue(result['complete'], result['reasons'])
        self.assertTrue(any(len(t['weight']) > 42 for t in result['traces']))
        self.assertEqual([t['weight'] for t in result['traces']], [case['validation']['calculation']['weights'][c] for c in CRITERIA])

    def test_forged_weights_and_engine_rejected(self):
        for field in ('engine', 'weights'):
            case = synthetic_case()
            if field == 'engine':
                case['validation']['engine'] = 'forged'
            else:
                case['validation']['calculation']['weights']['SI'] = '0.9'
            result = calculate_synthetic(**case)
            self.assertIn('WEIGHT_SOURCE_INVALID', result['reasons'])
            self.assertIsNone(result['score_0_1'])

    def test_missing_and_inconsistent_ahp_have_no_score(self):
        for value in ('', '100'):
            case = synthetic_case()
            case['judgments']['values']['SI:ES'] = value
            case['validation'] = validate_ahp(case['judgments'])
            self.assertIsNone(calculate_synthetic(**case)['score_0_1'])

    def test_missing_criterion_never_renormalized(self):
        case = synthetic_case()
        case['inputs']['ND']['value'] = None
        result = calculate_synthetic(**case)
        self.assertIsNone(result['score_0_1'])
        self.assertIn('VALUE_MISSING', result['reasons'])

    def test_exact_order_and_identifier_set(self):
        case = synthetic_case()
        case['criteria'].reverse()
        self.assertEqual(calculate_synthetic(**case)['reasons'], ['CRITERION_ORDER_INVALID'])
        case = synthetic_case()
        case['inputs']['extra'] = {}
        self.assertFalse(calculate_synthetic(**case)['complete'])

    def test_source_and_unit_mismatches(self):
        for field in ('source_type', 'unit'):
            case = synthetic_case()
            case['inputs']['SI'][field] = 'wrong'
            self.assertIn('MEASURE_OR_UNIT_MISMATCH', calculate_synthetic(**case)['reasons'])

    def test_category_mapping_explicit_and_unknown_blocked(self):
        case = synthetic_case()
        case['definitions']['ES']['encoding'] = {'synthetic-category': '2'}
        self.assertIn('ENCODING_UNAVAILABLE', calculate_synthetic(**case)['reasons'])
        case['inputs']['ES']['value'] = 'synthetic-category'
        self.assertEqual(calculate_synthetic(**case)['score_0_1'], '0.6')

    def test_cohort_proposal_never_selects_live_bounds(self):
        case = synthetic_case()
        case['definitions']['SI']['bounds'] = {'method': 'proposed_cohort'}
        self.assertIn('BOUNDS_PENDING', calculate_synthetic(**case)['reasons'])

    def test_ambient_context_and_equivalent_numbers(self):
        case = synthetic_case()
        expected = calculate_synthetic(**case)
        with localcontext() as context:
            context.prec = 3
            context.rounding = ROUND_UP
            context.Emax = 2
            self.assertEqual(calculate_synthetic(**case), expected)
        case['inputs']['SI']['value'] = '1.000e0'
        self.assertEqual(calculate_synthetic(**case), expected)

    def test_weight_residual_and_endpoint_anomaly_not_clamped(self):
        case = synthetic_case()
        for value in case['inputs'].values():
            value['value'] = '5'
        weights = dict.fromkeys(CRITERIA, '0.2')
        weights['SI'] = '0.2' + '0' * 46 + '1'
        with patch('ewaf.weighted_scoring.replay_weights', return_value=weights):
            result = calculate_synthetic(**case)
        self.assertIn('SCORE_RANGE_ANOMALY', result['reasons'])
        self.assertNotEqual(result['score_0_1'], '1')
        self.assertFalse(result['complete'])
        weights['SI'] = '0.3'
        with patch('ewaf.weighted_scoring.replay_weights', return_value=weights):
            result = calculate_synthetic(**case)
        self.assertIn('WEIGHT_VECTOR_INVALID', result['reasons'])
        self.assertIsNone(result['score_0_1'])

    def test_bounded_synthetic_payload(self):
        case = synthetic_case()
        case['inputs']['SI']['value'] = '1' * 40000
        self.assertEqual(calculate_synthetic(**case)['reasons'], ['PAYLOAD_RESOURCE_LIMIT'])
