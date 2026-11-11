"""Isolated amendment mathematics; no member data or database access."""
from decimal import Decimal, Inexact, Rounded, ROUND_DOWN, ROUND_UP, localcontext
from fractions import Fraction
import inspect
import json
from pathlib import Path
import subprocess
import sys

from django.test import SimpleTestCase
from .four_criterion_reference import calculate_reference, REFERENCE_CRITERIA, REFERENCE_VERSION
from .ahp_validation import CRITERIA, validate_ahp


class FourCriterionReferenceTests(SimpleTestCase):
    def setUp(self):
        directory = Path(__file__).parent / 'tests_data/g18'
        self.fixture = json.loads((directory / 'four-criterion-reference-v1.json').read_text())
        self.historical = json.loads((directory / 'computation-reference-v1.json').read_text())

    def test_exact_decimal_outputs_match_independent_fixture(self):
        result = calculate_reference()
        for key, expected in self.fixture['expected'].items():
            with self.subTest(key=key):
                self.assertEqual(result[key], expected)

    def test_all_six_pairs_are_retained_by_name_from_original_source(self):
        result = calculate_reference()
        named = self.historical['matrix_by_criterion']
        for a in REFERENCE_CRITERIA:
            for b in REFERENCE_CRITERIA:
                self.assertEqual(self.fixture['matrix_by_criterion'][a][b], named[a][b])
        self.assertEqual(result['pairs'], {k: v for k, v in self.historical['g14_input']['values'].items()
                                         if 'PR' not in k.split(':')})
        self.assertEqual(len(result['pairs']), 6)

    def test_independent_fraction_oracle_for_all_stages(self):
        names = REFERENCE_CRITERIA
        named = self.fixture['matrix_by_criterion']
        matrix = [[Fraction(named[a][b]) for b in names] for a in names]
        totals = [sum(row[j] for row in matrix) for j in range(4)]
        normalized = [[v / total for v, total in zip(row, totals)] for row in matrix]
        weights = [sum(row) / 4 for row in normalized]
        wsv = [sum(v * w for v, w in zip(row, weights)) for row in matrix]
        cv = [v / w for v, w in zip(wsv, weights)]
        lam = sum(cv) / 4
        ci = (lam - 4) / 3
        cr = ci / Fraction(9, 10)
        result = calculate_reference()
        actual = [*(result['column_totals'][n] for n in names),
                  *(v for row in result['normalized_matrix'] for v in row),
                  *(result['weights'][n] for n in names), *(result['WSV'][n] for n in names),
                  *(result['CV'][n] for n in names), result['lambda_estimate'], result['CI'], result['CR']]
        exact = [*totals, *(v for row in normalized for v in row), *weights, *wsv, *cv, lam, ci, cr]
        self.assertEqual(sum(weights), 1)
        self.assertEqual(len(actual), len(exact))
        for value, fraction in zip(actual, exact):
            self.assertLess(abs(Fraction(value) - fraction), Fraction(1, 10**47))

    def test_user_verification_targets_match_direct_rounding(self):
        result = calculate_reference()
        targets = {'SI': '0.4708590518', 'ES': '0.2840125218', 'PA': '0.1714829318', 'ND': '0.0736454946',
                   'lambda_estimate': '4.0513654729', 'CI': '0.0171218243', 'CR': '0.0190242492'}
        with localcontext() as ctx:
            ctx.prec = 60
            for key, target in targets.items():
                actual = result['weights'][key] if key in REFERENCE_CRITERIA else result[key]
                self.assertEqual(Decimal(actual).quantize(Decimal('0.0000000001')), Decimal(target))

    def test_four_criterion_structure_reciprocals_and_random_index(self):
        result = calculate_reference()
        self.assertEqual(result['criteria'], ['SI', 'ES', 'PA', 'ND'])
        self.assertEqual(result['n'], 4)
        self.assertEqual(result['RI'], '0.90')
        self.assertNotIn('PR', result['weights'])
        self.assertEqual(result['reference_consistency'], 'PASSED')
        self.assertLess(Decimal(result['CR']), Decimal('0.10'))
        matrix = result['matrix']
        for i in range(4):
            self.assertEqual(matrix[i][i], '1')
            for j in range(4):
                self.assertLess(abs(Fraction(matrix[i][j]) * Fraction(matrix[j][i]) - 1), Fraction(1, 10**47))
        self.assertEqual(result['weight_sum_residual'], '0')

    def test_recomputed_weights_are_not_renormalized_old_weights(self):
        old = self.historical['expected_calculation']['weights']
        denominator = sum(Fraction(old[n]) for n in REFERENCE_CRITERIA)
        for name, value in calculate_reference()['weights'].items():
            self.assertNotEqual(Fraction(value), Fraction(old[name]) / denominator)

    def test_historical_five_criterion_contract_and_exact_replay_unchanged(self):
        self.assertEqual(CRITERIA, ('SI', 'ES', 'PA', 'ND', 'PR'))
        old = validate_ahp(self.historical['g14_input'])
        self.assertEqual(old['calculation'], self.historical['expected_calculation'])
        self.assertEqual(old['reference']['RI'], '1.12')
        self.assertNotEqual(old['engine'], REFERENCE_VERSION)
        result = calculate_reference()
        rejected = validate_ahp({'criteria': result['criteria'], 'mode': 'pairs', 'values': result['pairs']})
        self.assertEqual(rejected['reasons'][0]['code'], 'CRITERION_ORDER_INVALID')

    def test_hostile_ambient_decimal_settings_cannot_change_output(self):
        expected = calculate_reference()
        for rounding in (ROUND_UP, ROUND_DOWN):
            with localcontext() as ctx:
                ctx.prec, ctx.rounding, ctx.Emin, ctx.Emax = 3, rounding, -5, 5
                ctx.traps[Inexact] = ctx.traps[Rounded] = True
                self.assertEqual(calculate_reference(), expected)

    def test_pending_authority_date_and_scope_never_default(self):
        result = calculate_reference()
        self.assertEqual(result['configuration_confirmation'], 'PENDING')
        self.assertIsNone(result['amendment_approval_date'])
        self.assertIsNone(result['effective_date'])
        self.assertEqual(result['authorized_program_ids'], [])
        self.assertFalse(result['effective_authorization'])
        self.assertFalse(result['operational_ready'])
        self.assertNotIn('score', result)
        self.assertNotIn('rank', result)

    def test_no_input_interface_and_no_shared_mutable_output(self):
        self.assertEqual(len(inspect.signature(calculate_reference).parameters), 0)
        result = calculate_reference()
        result['matrix'][0][0] = '999'
        result['weights']['PR'] = '1'
        result['authorized_program_ids'].append('fictional-forgery')
        result['operational_ready'] = True
        fresh = calculate_reference()
        self.assertEqual(fresh['matrix'][0][0], '1')
        self.assertNotIn('PR', fresh['weights'])
        self.assertFalse(fresh['operational_ready'])
        self.assertEqual(fresh['authorized_program_ids'], [])

    def test_standalone_replay_has_no_settings_database_network_or_write_dependency(self):
        code = '''import sys
class Block:
    def find_spec(self, fullname, *args):
        if fullname.split('.')[0] in {'django', 'config', 'MySQLdb', 'socket', 'requests'}:
            raise AssertionError('Forbidden import: ' + fullname)
sys.meta_path.insert(0, Block())
from ewaf.four_criterion_reference import calculate_reference
def audit(event, args):
    if event == 'open' or event.startswith(('socket.', 'subprocess.', 'os.remove', 'os.rename', 'os.mkdir')):
        raise AssertionError('Unexpected side effect: ' + event)
sys.addaudithook(audit)
assert calculate_reference()['configuration_confirmation'] == 'PENDING'
'''
        run = subprocess.run([sys.executable, '-B', '-c', code], cwd=Path(__file__).resolve().parent.parent,
                             capture_output=True, text=True, timeout=20)
        self.assertEqual(run.returncode, 0, run.stderr)
