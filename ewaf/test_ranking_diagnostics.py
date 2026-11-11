import json
import os
from copy import deepcopy
from decimal import Decimal, localcontext, ROUND_UP
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch
from django.test import SimpleTestCase
from .ahp_validation import validate_ahp
from .normalization import CRITERIA
from .ranking_diagnostics import (compare_fixture, _evaluate_payload, _groups, _score,
    content_digest, parse_fixture_json, FixtureIssue, BARRIERS, LIMITS)
from .ranking_fixtures import load_fixture, FIXTURES
from .ranking_testsupport import build_fixture, reseal


class RankingDiagnosticTests(SimpleTestCase):
    def reject(self, fixture, code):
        result = _evaluate_payload(fixture)
        self.assertFalse(result['complete'])
        self.assertEqual(result['groups'], [])
        self.assertIn(code, {row['code'] for row in result['reasons']})
        return result

    def test_high_first_exact_groups_and_spans(self):
        result = compare_fixture('high-first-v1')
        self.assertTrue(result['complete'])
        self.assertEqual([row['score_0_1'] for row in result['groups']], ['1', '0.5', '0'])
        self.assertEqual(result['groups'][1], {'score_0_1': '0.5', 'synthetic_ids': ['SYN-G16-B', 'SYN-G16-C'],
                                             'position_start': 2, 'position_end': 3})

    def test_low_first_explicit_direction(self):
        self.assertEqual([row['score_0_1'] for row in compare_fixture('low-first-v1')['groups']], ['0', '0.5', '1'])

    def test_no_default_direction(self):
        for direction in (None, '', 'descending', True):
            fixture = build_fixture(direction=direction)
            self.reject(fixture, 'RANKING_DIRECTION_PENDING')

    def test_exact_criteria_order(self):
        fixture = build_fixture()
        fixture['contract']['criteria'].reverse()
        self.reject(fixture, 'CRITERION_ORDER_INVALID')

    def test_empty_and_single_pool(self):
        self.reject(build_fixture(values=()), 'EMPTY_POOL')
        result = _evaluate_payload(build_fixture(values=('0',)))
        self.assertTrue(result['complete'])
        self.assertEqual(result['groups'][0]['position_end'], 1)

    def test_missing_extra_and_duplicate_candidates(self):
        for kind in ('missing', 'extra', 'duplicate'):
            fixture = build_fixture()
            if kind == 'missing':
                fixture['candidates'].pop()
            else:
                item = deepcopy(fixture['candidates'][0])
                if kind == 'extra':
                    item['id'] = 'SYN-G16-EXTRA'
                fixture['candidates'].append(item)
            self.reject(fixture, 'POOL_MANIFEST_MISMATCH')

    def test_manifest_duplicates_and_missing_entries(self):
        for field in ('manifest', 'pool_ids'):
            fixture = build_fixture()
            if field == 'manifest':
                fixture[field].append(deepcopy(fixture[field][0]))
                code = 'POOL_MANIFEST_MISMATCH'
            else:
                fixture['contract'][field].append(fixture['contract'][field][0])
                fixture = reseal(fixture)
                code = 'MANIFEST_IDS_INVALID'
            self.reject(fixture, code)

    def test_permutations_have_identical_results_and_digest(self):
        fixture = build_fixture()
        expected = _evaluate_payload(fixture)
        fixture['candidates'].reverse()
        fixture['manifest'].reverse()
        fixture['contract']['definitions'] = dict(reversed(list(fixture['contract']['definitions'].items())))
        self.assertEqual(_evaluate_payload(fixture), expected)

    def test_individual_inputs_and_digests_need_not_match(self):
        result = compare_fixture('high-first-v1')
        self.assertTrue(result['complete'])
        self.assertGreater(len({item['input_digest'] for item in result['items']}), 1)

    def test_wrong_candidate_contract(self):
        fixture = build_fixture()
        fixture['candidates'][0]['contract_digest'] = '0' * 64
        self.reject(fixture, 'COMPARISON_CONTRACT_MISMATCH')

    def test_contract_bound_to_all_definitions_and_context(self):
        for field, value in (('direction', 'LOW_FIRST'), ('scale', '0-100'),
                             ('context', {'scenario': 'SYN-G16-OTHER', 'evaluation': 'SYNTHETIC-EPOCH-1'})):
            fixture = build_fixture()
            fixture['contract'][field] = value
            self.reject(fixture, 'SCORE_SCALE_INVALID' if field == 'scale' else 'CONTRACT_DIGEST_MISMATCH')
        for field, value in (('direction', 'inverse'), ('bounds', {'method': 'fixed', 'lower': '0', 'upper': '2'}),
                             ('encoding', {'SYN-CATEGORY-A': '1'})):
            fixture = build_fixture()
            fixture['contract']['definitions']['SI'][field] = value
            self.reject(fixture, 'CONTRACT_DIGEST_MISMATCH')

    def test_unknown_fields_at_each_boundary(self):
        for path in ((), ('contract',), ('candidates', 0), ('candidates', 0, 'inputs', 'SI'),
                     ('contract', 'definitions', 'SI'), ('manifest', 0)):
            fixture = build_fixture()
            node = fixture
            for key in path:
                node = node[key]
            node['application_id'] = 123
            if path == ('candidates', 0, 'inputs', 'SI'):
                self.assertFalse(_evaluate_payload(fixture)['complete'])
            else:
                self.reject(fixture, 'UNEXPECTED_FIELDS')

    def test_no_real_identifier_or_synthetic_flag_bypass(self):
        for name in (123, {'synthetic': True}, '../precision-v1', 'PWD-123', 'SYN-G16-A'):
            result = compare_fixture(name)
            self.assertFalse(result['complete'])
            self.assertEqual(result['reasons'][0]['code'], 'FIXTURE_NOT_ALLOWLISTED')
        fixture = build_fixture()
        fixture['candidates'][0]['id'] = '123'
        self.reject(fixture, 'SYNTHETIC_ID_INVALID')

    def test_full_precision_g14_g15_replay(self):
        result = compare_fixture('precision-v1')
        self.assertTrue(result['complete'])
        for item in result['items']:
            calculation = item['calculation']
            self.assertEqual([t['criterion'] for t in calculation['traces']], list(CRITERIA))
            self.assertTrue(any(len(t['weight']) > 42 for t in calculation['traces']))
            self.assertEqual(len(Decimal(calculation['score_0_1']).as_tuple().digits), 50)

    def test_near_ties_and_display_collision_remain_distinct(self):
        result = compare_fixture('precision-v1')
        a, b = [Decimal(row['score_0_1']) for row in result['groups']]
        self.assertNotEqual(a, b)
        self.assertEqual(format(a, '.2f'), format(b, '.2f'))
        self.assertEqual(len(result['groups']), 2)

    def test_float_and_negation_pitfalls_do_not_affect_engine(self):
        fixture = load_fixture('precision-v1')
        expected = _evaluate_payload(fixture)
        a, b = [Decimal(row['score_0_1']) for row in expected['groups']]
        self.assertEqual(float(a), float(b))
        with localcontext() as context:
            context.prec = 3
            context.rounding = ROUND_UP
            self.assertEqual(-a, -b)
            self.assertEqual(_evaluate_payload(fixture), expected)

    def test_equivalent_decimal_spellings_form_one_group(self):
        items = [{'id': 'SYN-G16-' + key, 'calculation': {'score_0_1': value}}
                 for key, value in (('B', '0.50'), ('A', '5e-1'))]
        self.assertEqual(_groups(items, 'HIGH_FIRST'), [{'score_0_1': '0.5',
            'synthetic_ids': ['SYN-G16-A', 'SYN-G16-B'], 'position_start': 1, 'position_end': 2}])
        fixture = build_fixture(values=('0.50', '5e-1'))
        self.assertEqual(len(_evaluate_payload(fixture)['groups']), 1)

    def test_ids_only_order_presentation_inside_ties(self):
        fixture = build_fixture()
        fixture['candidates'][1]['id'] = 'SYN-G16-Z'
        fixture['contract']['pool_ids'] = sorted(item['id'] for item in fixture['candidates'])
        result = _evaluate_payload(reseal(fixture))
        self.assertEqual([g['score_0_1'] for g in result['groups']], ['1', '0.5', '0'])
        self.assertEqual(result['groups'][1]['synthetic_ids'], ['SYN-G16-C', 'SYN-G16-Z'])
        self.assertEqual(result['groups'][1]['position_end'], 3)

    def test_forged_g14_weights_and_profile(self):
        for field in ('weight', 'engine', 'profile', 'complete'):
            fixture = build_fixture()
            validation = fixture['contract']['validation']
            if field == 'weight':
                validation['calculation']['weights']['SI'] = '0.9'
            else:
                validation[field] = 'forged'
            self.reject(fixture, 'G14_REPLAY_MISMATCH')

    def test_incomplete_g14_is_not_a_weight_source(self):
        fixture = build_fixture()
        fixture['contract']['judgments']['values']['SI:ES'] = ''
        fixture['contract']['validation'] = validate_ahp(fixture['contract']['judgments'])
        self.reject(reseal(fixture), 'G14_VALIDATION_INCOMPLETE')

    def test_forged_calculated_artifacts_even_with_rehashed_manifest(self):
        for field in ('score_0_1', 'score_0_100', 'complete', 'engine', 'profile', 'traces'):
            fixture = build_fixture()
            item = fixture['candidates'][0]
            item['calculation'][field] = [] if field == 'traces' else False if field == 'complete' else '0.8'
            item['calculation_digest'] = content_digest('calculation', item['calculation'])
            fixture['manifest'][0]['calculation_digest'] = item['calculation_digest']
            fixture['manifest_digest'] = content_digest('manifest', fixture['manifest'])
            self.reject(fixture, 'G15_REPLAY_MISMATCH')

    def test_forged_contribution_and_criterion_trace(self):
        for field in ('contribution', 'weight', 'criterion'):
            fixture = build_fixture()
            fixture['candidates'][0]['calculation']['traces'][0][field] = 'forged'
            self.reject(fixture, 'G15_REPLAY_MISMATCH')

    def test_forged_input_result_and_manifest_digests(self):
        for field in ('input_digest', 'calculation_digest'):
            fixture = build_fixture()
            fixture['candidates'][0][field] = '0' * 64
            self.reject(fixture, 'CANDIDATE_DIGEST_MISMATCH')
        fixture = build_fixture()
        fixture['manifest_digest'] = '0' * 64
        self.reject(fixture, 'MANIFEST_DIGEST_MISMATCH')

    def test_missing_and_malformed_scores(self):
        for value in (None, '', 'NaN', 'Infinity', '-Infinity', True, 0.5, '1e99999', ' 0.5', '-0.1', '1.1'):
            fixture = build_fixture()
            fixture['candidates'][0]['calculation']['score_0_1'] = value
            self.assertFalse(_evaluate_payload(fixture)['complete'], repr(value))
        self.assertEqual(_score('0'), Decimal(0))

    def test_missing_values_never_produce_partial_groups(self):
        result = compare_fixture('incomplete-v1')
        self.assertFalse(result['complete'])
        self.assertEqual(result['groups'], [])
        self.assertEqual(result['items'], [])
        self.assertIn('VALUE_MISSING', {r['code'] for r in result['reasons']})

    def test_server_score_range_anomaly_rejected_despite_present_score(self):
        fixture = build_fixture(values=('1',))
        weights = dict.fromkeys(CRITERIA, '0.2')
        weights['SI'] = '0.2' + '0' * 46 + '1'
        # Inject the existing G15 endpoint anomaly, not a permissive G16 engine.
        with patch('ewaf.weighted_scoring.replay_weights', return_value=weights):
            result = self.reject(fixture, 'SCORE_RANGE_ANOMALY')
        self.assertEqual(result['items'], [])

    def test_source_unit_category_and_bounds_mismatch(self):
        for field in ('source_type', 'unit'):
            fixture = build_fixture()
            fixture['candidates'][0]['inputs']['SI'][field] = 'wrong'
            self.reject(reseal(fixture), 'MEASURE_OR_UNIT_MISMATCH')
        fixture = build_fixture()
        fixture['contract']['definitions']['ES']['encoding'] = {'SYN-CATEGORY-A': '1'}
        self.reject(reseal(fixture), 'ENCODING_UNAVAILABLE')
        fixture = build_fixture()
        fixture['contract']['definitions']['SI']['bounds']['method'] = 'cohort'
        self.reject(fixture, 'FIXED_BOUNDS_REQUIRED')

    def test_unsupported_schema_and_math_profiles(self):
        fixture = build_fixture()
        fixture['schema_version'] = True
        self.reject(fixture, 'UNSUPPORTED_FIXTURE_VERSION')
        for key in ('score_engine', 'score_profile', 'score_settings'):
            fixture = build_fixture()
            fixture['contract'][key] = 'future'
            self.reject(fixture, 'UNSUPPORTED_MATHEMATICAL_PROFILE')

    def test_duplicate_json_keys_and_non_json_numbers(self):
        for data, reason in ((b'{"a":1,"a":2}', 'DUPLICATE_JSON_KEY'),
                             (b'{"a":{"b":0,"b":1}}', 'DUPLICATE_JSON_KEY'),
                             (b'{"a":NaN}', 'INVALID_JSON_NUMBER'), (b'{"a":0.5}', 'INVALID_JSON_NUMBER')):
            with self.assertRaisesRegex(FixtureIssue, reason):
                parse_fixture_json(data)

    def test_resource_limits(self):
        with self.assertRaisesRegex(FixtureIssue, 'PAYLOAD_RESOURCE_LIMIT'):
            parse_fixture_json(b' ' * (LIMITS['bytes'] + 1))
        fixture = build_fixture()
        fixture['candidates'][0]['inputs']['SI']['value'] = '1' * 1101
        self.reject(fixture, 'PAYLOAD_RESOURCE_LIMIT')
        with self.assertRaises(FixtureIssue):
            parse_fixture_json(b'[' * 1000 + b']' * 1000)
        fixture = build_fixture()
        fixture['contract']['pool_ids'] *= 9
        fixture['contract_digest'] = content_digest('contract', fixture['contract'])
        self.reject(fixture, 'POOL_RESOURCE_LIMIT')

    def test_capacity_examples_never_select_or_truncate(self):
        result = compare_fixture('high-first-v1')
        self.assertEqual(result['capacity_diagnostics'], ['ILLUSTRATIVE_CAPACITY_EXCEEDED', 'TIE_CROSSES_ILLUSTRATIVE_BOUNDARY'])
        self.assertEqual(sum(len(g['synthetic_ids']) for g in result['groups']), 4)
        self.assertFalse(any(key in json.dumps(result) for key in ('"selected"', '"rank"', '"winner"', '"waitlist"')))
        fixture = build_fixture()
        fixture['contract']['illustrative_capacity'] = 8
        self.assertEqual(_evaluate_payload(reseal(fixture))['capacity_diagnostics'], [])

    def test_all_barriers_and_repeatable_digests(self):
        for name in FIXTURES:
            first = compare_fixture(name)
            self.assertEqual(first, compare_fixture(name))
            self.assertEqual(first['barriers'], list(BARRIERS))
            self.assertFalse(first['effective_authorization'])
            self.assertFalse(first['operational_ready'])

    def test_source_file_checksum_is_required(self):
        with patch('pathlib.Path.open') as opened:
            opened.return_value.__enter__.return_value.read.return_value = b'{}'
            self.assertEqual(compare_fixture('high-first-v1')['reasons'][0]['code'], 'FIXTURE_CHECKSUM_MISMATCH')

    def test_fixture_registry_immutable_and_no_database_import(self):
        with self.assertRaises(TypeError):
            FIXTURES['new'] = 'forged'
        root = Path(__file__).resolve().parent.parent
        code = """import sys
class Block:
    def find_spec(self, fullname, *args):
        if fullname in ('django.db', 'django.conf', 'config.settings', 'ewaf.models'):
            raise RuntimeError('Forbidden runtime dependency: ' + fullname)
sys.meta_path.insert(0, Block())
from ewaf.ranking_diagnostics import compare_fixture
assert compare_fixture('high-first-v1')['complete']
print('Pure fixture replay; no settings or database imported')
"""
        env = {key: value for key, value in os.environ.items() if key.upper() in
               {'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP'}}
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=root, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cli_accepts_only_allowlisted_name(self):
        root = Path(__file__).resolve().parent.parent
        result = subprocess.run([sys.executable, '-B', 'scripts/g16_synthetic_diagnostics.py', '../other'],
                                cwd=root, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 2)
        self.assertIn('invalid choice', result.stderr)
