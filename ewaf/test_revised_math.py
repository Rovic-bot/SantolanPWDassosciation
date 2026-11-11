"""Exact reference and failure cases; no database or real applicant data."""
from copy import deepcopy
from dataclasses import FrozenInstanceError
from decimal import Decimal, Inexact, ROUND_DOWN, localcontext
from fractions import Fraction as F
import unittest

from ewaf.revised import engine as e
from ewaf.revised import math as m
from ewaf.revised.fixtures import example_pool


def refreeze(data):
    return e.freeze_pool(**{key: data[key] for key in ('program', 'version', 'cutoff', 'expected_ids', 'applicants', 'unresolved_ids')})


class RevisedMathTests(unittest.TestCase):
    def setUp(self):
        self.config = e.configure()
        self.pool = example_pool()

    def test_every_exact_ahp_intermediate_from_unrounded_document_ratios(self):
        q = tuple(F(value) for value in ('0.3421', '0.2360', '0.1774', '0.1223', '0.1222'))
        matrix = tuple(tuple(x / y for y in q) for x in q)
        result = m.ahp(matrix)
        self.assertEqual(result['matrix'], matrix)
        self.assertEqual(result['column_sums'], tuple(1 / value for value in q))
        self.assertEqual(result['normalized_matrix'], tuple((value,) * 5 for value in q))
        self.assertEqual(result['weights'], q)
        self.assertEqual(result['wsv'], tuple(F(value) for value in ('1.7105', '1.1800', '0.8870', '0.6115', '0.6110')))
        self.assertEqual(result['cv'], (F(5),) * 5)
        for key, value in (('lambda_max_estimate', 5), ('ci', 0), ('cr', 0), ('ri', F('1.12'))):
            self.assertEqual(result[key], value)
        self.assertTrue(result['consistent'])
        self.assertEqual(self.config.data['weight_provenance'], 'Illustrative reconstructed matrix.')
        self.assertFalse(self.config.data['official'])

    def test_nonperfect_matrix_uses_column_normalized_row_average(self):
        matrix = [[F(1) for _ in range(5)] for _ in range(5)]
        matrix[0][1], matrix[1][0] = F(2), F(1, 2)
        result = m.ahp(matrix)
        self.assertEqual(result['column_sums'], (F(9, 2), F(6), F(5), F(5), F(5)))
        self.assertEqual(result['weights'], (F(52, 225), F(79, 450), F(89, 450), F(89, 450), F(89, 450)))
        self.assertEqual(result['wsv'], (F(529, 450), F(199, 225), F(1), F(1), F(1)))
        self.assertEqual(result['cv'], (F(529, 104), F(398, 79), F(450, 89), F(450, 89), F(450, 89)))
        self.assertTrue(result['consistent'])

    def test_fixture_bounds_all_normalized_values_and_exact_scores(self):
        result = e.calculate(self.pool, self.config)
        self.assertEqual([r['lower']['exact'] for r in result['bounds']], ['5000', '1', '1', '0', '2'])
        self.assertEqual([r['upper']['exact'] for r in result['bounds']], ['20000', '4', '4', '3', '6'])
        normalized = ((1, 1, F(2, 3), F(2, 3), F(1, 2)), (F(1, 2), F(2, 3), 1, 1, 0), (0, 0, 0, 0, 1))
        q = tuple(F(item['exact']) for item in self.config.data['weights'])
        for row, expected, score, label, rank in zip(result['applicants'], normalized,
                (F('83.90'), F(7537, 120), F('12.22')), ('High', 'Moderate', 'Minimal'), (1, 2, 3)):
            self.assertEqual(tuple(F(t['normalized']['exact']) for t in row['traces']), expected)
            self.assertEqual(tuple(F(t['contribution_0_1']['exact']) for t in row['traces']), tuple(w * z for w, z in zip(q, expected)))
            self.assertEqual(F(row['score_0_100']['exact']), score)
            self.assertEqual(F(row['score_0_1']['exact']) * 100, score)
            self.assertEqual(sum(F(t['contribution_points']['exact']) for t in row['traces']), score)
            self.assertEqual(row['rank'], rank)
            self.assertEqual(row['classification'], label + ' Assistance Need')
        self.assertEqual([row['display_score'] for row in result['applicants']], ['83.90', '62.81', '12.22'])

    def test_directions_raw_categories_encodings_and_scales_remain_distinct(self):
        a, b, c = e.calculate(self.pool, self.config)['applicants']
        self.assertEqual([t['direction'] for t in a['traces']], list(e.DIRECTIONS))
        self.assertEqual(a['traces'][2]['input']['value'], 'Seasonal Worker')
        self.assertEqual(a['traces'][2]['encoded']['exact'], '3')
        self.assertEqual(a['traces'][2]['normalized']['exact'], '2/3')
        self.assertEqual(a['score_0_1']['exact'], '839/1000')
        self.assertEqual(c['traces'][4]['normalized']['exact'], '1')
        self.assertEqual(b['traces'][3]['normalized']['exact'], '1')

    def test_raw_numeric_format_and_hostile_decimal_context_do_not_change_exact_scores(self):
        original = e.calculate(self.pool, self.config)
        data = self.pool.data; data['applicants'][0]['inputs']['HI']['value'] = '5000.00'
        row = e.calculate(refreeze(data), self.config)['applicants'][0]
        self.assertEqual(row['traces'][0]['input']['value'], '5000.00')
        self.assertEqual(row['traces'][0]['encoded']['exact'], '5000')
        self.assertEqual(row['score_0_100'], original['applicants'][0]['score_0_100'])
        with localcontext() as context:
            context.prec = 3; context.rounding = ROUND_DOWN; context.traps[Inexact] = True
            self.assertEqual(e.configure().data, self.config.data)
            self.assertEqual(e.calculate(self.pool, e.configure()), original)

    def test_unrounded_classification_and_exact_display_boundaries(self):
        for value, expected in (('0', 'Minimal'), ('39.999999', 'Minimal'), ('40', 'Low'),
                ('59.999999', 'Low'), ('60', 'Moderate'), ('79.999999', 'Moderate'), ('80', 'High'), ('100', 'High')):
            self.assertEqual(m.classification(F(value)), expected + ' Assistance Need')
        self.assertEqual(m.display(F('79.999999')), '80.00')
        self.assertEqual(m.classification(F('79.999999')), 'Moderate Assistance Need')
        self.assertEqual(m.display(F('62.805')), '62.80')
        self.assertEqual(m.display(F('62.815')), '62.82')

    def test_close_scores_never_rank_from_display_values(self):
        values = [F('80.00000000000000000000000000000000000000001'), F('80'), F('79.99999999999999999999999999999999999999999')]
        self.assertEqual([m.display(value) for value in values], ['80.00'] * 3)
        self.assertEqual([row['rank'] for row in m.ranks(values).values()], [1, 2, 3])
        self.assertTrue(all(row['tie_size'] == 1 for row in m.ranks(values).values()))
        with self.assertRaises(m.CalculationError):
            m.ranks([0.1, 0.2])

    def test_competition_ties_and_capacity_boundary_never_choose_winner(self):
        result = m.ranks([F(90), F(80), F(80), F(70)], capacity=2)
        self.assertEqual([result[i]['rank'] for i in range(4)], [1, 2, 2, 4])
        self.assertEqual([result[i]['capacity_boundary_tie'] for i in range(4)], [False, True, True, False])
        self.assertEqual(result[1]['tie_group'], result[2]['tie_group'])
        self.assertFalse(any(r['capacity_boundary_tie'] for r in m.ranks([90, 80, 80, 70], 3).values()))
        self.assertFalse(any(r['capacity_boundary_tie'] for r in m.ranks([90, 80, 80, 70], 0).values()))

    def test_pipeline_exact_ties_stay_tied_under_row_reordering(self):
        data = self.pool.data
        duplicate = deepcopy(data['applicants'][0]); duplicate['id'] = 'D'
        data['applicants'].append(duplicate); data['expected_ids'].append('D')
        result = e.calculate(refreeze(data), self.config, capacity=1)
        self.assertEqual([r['rank'] for r in result['applicants']], [1, 1, 3, 4])
        self.assertTrue(result['capacity_boundary_tie'])
        first = {r['applicant']: r['rank'] for r in result['applicants']}
        data['applicants'].reverse()
        second = e.calculate(refreeze(data), self.config, capacity=1)
        self.assertEqual(first, {r['applicant']: r['rank'] for r in second['applicants']})
        self.assertTrue(all('synthetic' in r['human_decision'] for r in second['applicants']))

    def test_close_scores_through_full_pipeline_are_not_false_ties(self):
        data = self.pool.data
        row = deepcopy(data['applicants'][0]); row['id'] = 'D'
        row['inputs']['HI']['value'] = str(F(5000) + F(1, 10**40))
        data['applicants'].append(row); data['expected_ids'].append('D')
        result = e.calculate(refreeze(data), self.config)
        a, d = result['applicants'][:2]
        self.assertEqual((a['applicant'], d['applicant']), ('A', 'D'))
        self.assertEqual(a['display_score'], d['display_score'])
        self.assertGreater(F(a['score_0_100']['exact']), F(d['score_0_100']['exact']))
        self.assertEqual((a['rank'], d['rank']), (1, 2))
        self.assertEqual((a['tie_size'], d['tie_size']), (1, 1))

    def test_no_classification_needed_for_ordering(self):
        result = e.calculate(self.pool, e.configure(classify=False))
        self.assertEqual([r['rank'] for r in result['applicants']], [1, 2, 3])
        self.assertTrue(all(r['classification'] is None for r in result['applicants']))

    def test_empty_single_and_each_constant_column_stop(self):
        data = self.pool.data
        data['applicants'] = []; data['expected_ids'] = []
        with self.assertRaisesRegex(m.CalculationError, 'empty'):
            refreeze(data)
        data = self.pool.data
        data['applicants'] = data['applicants'][:1]; data['expected_ids'] = ['A']
        with self.assertRaisesRegex(m.CalculationError, 'Constant column.*HI, SI, ES, PA, HM'):
            e.calculate(refreeze(data), self.config)
        for code in m.CRITERIA:
            data = self.pool.data
            for row in data['applicants']:
                row['inputs'][code]['value'] = data['applicants'][0]['inputs'][code]['value']
            with self.assertRaisesRegex(m.CalculationError, f'Constant column.*{code}'):
                e.calculate(refreeze(data), self.config)

    def test_missing_disputed_stale_unaccepted_and_expired_inputs_block(self):
        for code in m.CRITERIA:
            for key, value in (('state', 'DECLARED'), ('stale', True), ('disputed', True),
                    ('evidence_version', 0), ('evidence_id', ''), ('period', ''),
                    ('valid_until', '2026-10-24T00:00:00+00:00'), ('accepted_at', '2026-10-26T00:00:00+00:00')):
                with self.subTest(code=code, field=key):
                    data = self.pool.data; data['applicants'][0]['inputs'][code][key] = value
                    with self.assertRaises(m.CalculationError):
                        refreeze(data)
            data = self.pool.data; del data['applicants'][0]['inputs'][code]
            with self.assertRaises(m.CalculationError):
                refreeze(data)

    def test_no_raw_registration_or_fourps_substitution(self):
        for code, source in (('SI', 'four_ps_membership'), ('HI', 'raw_profile'), ('PA', 'selected_application'), ('HM', 'dependent_count')):
            data = self.pool.data; data['applicants'][0]['inputs'][code]['source'] = source
            with self.assertRaises(m.CalculationError):
                refreeze(data)
        for code, value in (('SI', '4Ps'), ('ES', 'Student'), ('ES', 3), ('HI', None), ('PA', '-1'), ('HM', '1.5')):
            data = self.pool.data; data['applicants'][0]['inputs'][code]['value'] = value
            with self.assertRaises(m.CalculationError):
                refreeze(data)

    def test_missing_invalid_numeric_inputs_and_binary_floats_refused(self):
        for value in (None, True, 0.1, '', 'NaN', 'Infinity', Decimal('NaN'), '1e999999999', '1/0'):
            with self.subTest(value=value), self.assertRaises(m.CalculationError):
                m.number(value)

    def test_complete_pool_inventory_is_not_an_optional_filter(self):
        for mutate in (lambda d: d['applicants'].pop(), lambda d: d['expected_ids'].append('D'),
                       lambda d: d['unresolved_ids'].append('pending-D'),
                       lambda d: d['applicants'][0].update(eligibility='PENDING'),
                       lambda d: d['applicants'].append(deepcopy(d['applicants'][0]))):
            data = self.pool.data; mutate(data)
            with self.assertRaises(m.CalculationError):
                refreeze(data)

    def test_frozen_inputs_and_new_pool_recompute_shared_bounds_without_mutating_history(self):
        original = e.calculate(self.pool, self.config)
        data = self.pool.data
        data['version'] = 2
        data['applicants'][2]['inputs']['HI'].update(value='30000', evidence_version=2)
        new_pool = refreeze(data)
        new = e.calculate(new_pool, self.config)
        self.assertNotEqual(new['pool_digest'], original['pool_digest'])
        self.assertEqual(new['bounds'][0]['upper']['exact'], '30000')
        self.assertNotEqual(new['applicants'][1]['score_0_100'], original['applicants'][1]['score_0_100'])
        self.assertEqual(e.calculate(self.pool, self.config), original)
        with self.assertRaises(FrozenInstanceError):
            self.pool.snapshot = '{}'

    def test_independent_slider_defaults_and_remaining_hm(self):
        values = dict(zip(m.CRITERIA, m.DEFAULTS))
        self.assertEqual(m.proposal(values), tuple(F(v['exact']) for v in self.config.data['weights']))
        values['HI'] = '40'
        weights = m.proposal(values)
        self.assertEqual(weights[1:4], (F('.2360'), F('.1774'), F('.1223')))
        self.assertEqual(weights[4], F('.0643'))
        self.assertEqual(sum(weights), 1)

    def test_invalid_slider_combination_and_no_invented_hm_minimum(self):
        values = {'HI': '62.55', 'SI': '19.48', 'ES': '14.07', 'PA': '12.23'}
        with self.assertRaisesRegex(m.CalculationError, '-8.33'):
            m.proposal(values)
        values['HI'] = '54.22'
        weights = m.proposal(values)
        self.assertEqual(weights[4], 0)
        with self.assertRaises(m.CalculationError):
            m.validate_weights(weights, positive=True)
        self.assertIsNone(e.configure('DRAFT_SENSITIVITY', values).data['ahp'])
        values['HI'] = '26.40'
        self.assertEqual(m.proposal(values)[4], F('0.2782'))

    def test_slider_range_steps_totals_and_extra_hm_rejected(self):
        for change in ({'HI': '26.39'}, {'SI': '34.22'}, {'ES': '14.071'}, {'PA': '-1'}, {'HM': '12.22'}):
            values = dict(zip(m.CRITERIA, m.DEFAULTS)); values.update(change)
            with self.assertRaises(m.CalculationError):
                m.proposal(values)
        with self.assertRaises(m.CalculationError):
            m.validate_weights((F('.2'),) * 4 + (F('.19'),), positive=True)

    def test_manual_weights_have_no_matrix_or_ahp_claim_and_provenance_tampering_fails(self):
        config = e.configure('DRAFT_SENSITIVITY', dict(zip(m.CRITERIA, m.DEFAULTS)))
        self.assertIsNone(config.data['ahp'])
        self.assertIn('not AHP-derived', config.data['weight_provenance'])
        altered = config.data; altered['weight_provenance'] = 'Client-validated pairwise judgments.'
        with self.assertRaisesRegex(m.CalculationError, 'provenance mismatch'):
            e.calculate(self.pool, e.Configuration(e.canonical(altered)))
        with self.assertRaises(m.CalculationError):
            e.configure('OFFICIAL')
        with self.assertRaises(m.CalculationError):
            e.configure(proposed=dict(zip(m.CRITERIA, m.DEFAULTS)))

    def test_genuine_inconsistent_pairwise_judgments_fail_strict_consistency(self):
        matrix = [[F(1) for _ in range(5)] for _ in range(5)]
        for i, j in ((0, 1), (1, 2), (2, 0)):
            matrix[i][j] = F(9); matrix[j][i] = F(1, 9)
        result = m.ahp(matrix)
        self.assertGreater(result['cr'], F(1, 10))
        self.assertFalse(result['consistent'])
        with self.assertRaises(m.CalculationError):
            m.require_consistency(result)
        for value, accepted in ((F(-1, 10**30), False), (F(0), True),
                (F(1, 10) - F(1, 10**30), True), (F(1, 10), False), (F(1, 10) + F(1, 10**30), False)):
            self.assertEqual(m.consistent(value), accepted)

    def test_matrix_shape_positive_diagonal_reciprocity_and_no_rounded_cell_repair(self):
        good = [[F(cell['exact']) for cell in row] for row in self.config.data['ahp']['matrix']]
        for value in (0, -1, F(1449576, 1000000)):
            matrix = deepcopy(good); matrix[0][1] = value
            with self.assertRaises(m.CalculationError):
                m.ahp(matrix)
        matrix = deepcopy(good); matrix[0][0] = 2
        with self.assertRaises(m.CalculationError):
            m.ahp(matrix)
        with self.assertRaises(m.CalculationError):
            m.ahp([[1] * 4] * 4)

    def test_tampered_frozen_encoding_and_non_synthetic_pool_rejected(self):
        data = self.pool.data; data['applicants'][0]['inputs']['ES']['encoded'] = '4'
        with self.assertRaisesRegex(m.CalculationError, 'encoding mismatch'):
            e.calculate(e.FrozenPool(e.canonical(data)), self.config)
        data = self.pool.data; data['synthetic'] = False
        with self.assertRaisesRegex(m.CalculationError, 'handoff'):
            e.calculate(e.FrozenPool(e.canonical(data)), self.config)
