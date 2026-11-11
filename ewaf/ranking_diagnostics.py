"""G16 pure synthetic comparisons. Public entry accepts pinned fixture names only.

The private payload evaluator exists for source-fixture validation and adversarial
tests, not as an applicant scoring API. No ORM, settings, requests or file uploads.
"""
import hashlib
import json
import re
from decimal import Decimal

from .ahp_validation import validate_ahp
from .normalization import CRITERIA, ENGINE as SCORE_ENGINE, PROFILE as SCORE_PROFILE
from .normalization import SETTINGS as SCORE_SETTINGS, NumericIssue, number, decimal_text
from .weighted_scoring import calculate_synthetic

ENGINE = 'g16-synthetic-comparison-1'
PROFILE = 'exact-decimal-groups-1'
DOMAIN = 'g16-synthetic-content-v1'
LABEL = 'DIAGNOSTIC ONLY — NOT AUTHORIZED FOR BENEFICIARY PROCESSING'
LIMITS = {'bytes': 524288, 'candidates': 32, 'depth': 16, 'nodes': 30000,
          'container': 256, 'text': 1100}
BARRIERS = ('CRITERION_POLICY_UNAPPROVED', 'CONFIGURATION_AUTHORIZATION_UNAVAILABLE',
            'OPERATIONAL_SCORING_UNAVAILABLE', 'PROCESSING_GATE_UNAVAILABLE',
            'OPERATIONAL_RANKING_UNAVAILABLE')
IDENTITY = re.compile(r'SYN-G16-[A-Z]{1,16}\Z')


class FixtureIssue(ValueError):
    """Stable diagnostic code; never includes submitted values."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False)


def content_digest(kind, value):
    return hashlib.sha256(canonical([DOMAIN, kind, value]).encode('ascii')).hexdigest()


def _bounded(value):
    nodes = 0

    def visit(item, depth=0):
        nonlocal nodes
        nodes += 1
        if nodes > LIMITS['nodes'] or depth > LIMITS['depth']:
            raise FixtureIssue('PAYLOAD_RESOURCE_LIMIT')
        if type(item) in (dict, list):
            if len(item) > LIMITS['container']:
                raise FixtureIssue('PAYLOAD_RESOURCE_LIMIT')
            if type(item) is dict and any(type(k) is not str or len(k) > 100 for k in item):
                raise FixtureIssue('INVALID_STRUCTURE')
            for child in (item.values() if type(item) is dict else item):
                visit(child, depth + 1)
        elif type(item) is str:
            if len(item) > LIMITS['text']:
                raise FixtureIssue('PAYLOAD_RESOURCE_LIMIT')
        elif type(item) is int:
            if item.bit_length() > 400:
                raise FixtureIssue('PAYLOAD_RESOURCE_LIMIT')
        elif item is not None and type(item) is not bool:
            raise FixtureIssue('INVALID_JSON_TYPE')
    visit(value)
    if len(canonical(value)) > LIMITS['bytes']:
        raise FixtureIssue('PAYLOAD_RESOURCE_LIMIT')


def parse_fixture_json(data):
    """Strict bounded decoder; decoding alone never authorizes comparison."""
    if type(data) is not bytes or len(data) > LIMITS['bytes']:
        raise FixtureIssue('PAYLOAD_RESOURCE_LIMIT')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise FixtureIssue('DUPLICATE_JSON_KEY')
            result[key] = value
        return result

    def reject_number(value):
        raise FixtureIssue('INVALID_JSON_NUMBER')

    def integer(value):
        if len(value) > 100:
            raise FixtureIssue('PAYLOAD_RESOURCE_LIMIT')
        return int(value)
    try:
        result = json.loads(data.decode('utf-8'), object_pairs_hook=pairs,
                            parse_float=reject_number, parse_constant=reject_number,
                            parse_int=integer)
        _bounded(result)
        return result
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise FixtureIssue('INVALID_JSON') from None


def _fields(value, expected):
    if type(value) is not dict or set(value) != set(expected.split()):
        raise FixtureIssue('UNEXPECTED_FIELDS')


def _identity(value):
    if type(value) is not str or not IDENTITY.fullmatch(value):
        raise FixtureIssue('SYNTHETIC_ID_INVALID')


def _score(text):
    if text is None or text == '':
        raise FixtureIssue('SCORE_MISSING')
    try:
        if type(text) is not str:
            raise NumericIssue('INVALID_NUMBER')
        value = number(text, calculated=True)
    except NumericIssue as error:
        raise FixtureIssue(str(error)) from None
    if not value.is_finite() or not Decimal(0) <= value <= Decimal(1):
        raise FixtureIssue('SCORE_RANGE_ANOMALY')
    return value


def _groups(items, direction):
    """Only called after the complete pool passes replay. No arithmetic sort key."""
    ordered = sorted(items, key=lambda row: row['id'])
    ordered.sort(key=lambda row: _score(row['calculation']['score_0_1']),
                 reverse=direction == 'HIGH_FIRST')
    groups = []
    previous = None
    for position, item in enumerate(ordered, 1):
        score = _score(item['calculation']['score_0_1'])
        if not groups or score != previous:
            groups.append({'score_0_1': decimal_text(score), 'synthetic_ids': [],
                           'position_start': position, 'position_end': position})
        groups[-1]['synthetic_ids'].append(item['id'])
        groups[-1]['position_end'] = position
        previous = score
    return groups


def _contract(contract):
    _fields(contract, 'criteria definitions judgments validation score_engine score_profile score_settings scale context direction pool_ids illustrative_capacity')
    if contract['criteria'] != list(CRITERIA):
        raise FixtureIssue('CRITERION_ORDER_INVALID')
    if contract['direction'] not in ('HIGH_FIRST', 'LOW_FIRST'):
        raise FixtureIssue('RANKING_DIRECTION_PENDING')
    if (contract['score_engine'] != SCORE_ENGINE or contract['score_profile'] != SCORE_PROFILE or
            canonical(contract['score_settings']) != canonical(SCORE_SETTINGS)):
        raise FixtureIssue('UNSUPPORTED_MATHEMATICAL_PROFILE')
    if contract['scale'] != '0-1':
        raise FixtureIssue('SCORE_SCALE_INVALID')
    _fields(contract['context'], 'scenario evaluation')
    _identity(contract['context']['scenario'])
    if contract['context']['evaluation'] != 'SYNTHETIC-EPOCH-1':
        raise FixtureIssue('SCENARIO_CONTEXT_INVALID')
    capacity = contract['illustrative_capacity']
    if capacity is not None and (type(capacity) is not int or not 1 <= capacity <= LIMITS['candidates']):
        raise FixtureIssue('ILLUSTRATIVE_CAPACITY_INVALID')
    _fields(contract['definitions'], ' '.join(CRITERIA))
    for definition in contract['definitions'].values():
        _fields(definition, 'source_type unit direction bounds encoding')
        if definition['source_type'] != 'synthetic' or definition['unit'] != 'fixture':
            raise FixtureIssue('SYNTHETIC_MEASURE_REQUIRED')
        _fields(definition['bounds'], 'method lower upper')
        if definition['bounds']['method'] != 'fixed':
            raise FixtureIssue('FIXED_BOUNDS_REQUIRED')
        encoding = definition['encoding']
        if encoding is not None and (type(encoding) is not dict or any(
                not re.fullmatch(r'SYN-CATEGORY-[A-Z]{1,16}', key) for key in encoding)):
            raise FixtureIssue('SYNTHETIC_ENCODING_INVALID')
    validation = validate_ahp(contract['judgments'])
    if canonical(validation) != canonical(contract['validation']):
        raise FixtureIssue('G14_REPLAY_MISMATCH')
    if not validation['complete'] or not validation['structurally_valid'] or validation['consistency'] != 'PASSED':
        raise FixtureIssue('G14_VALIDATION_INCOMPLETE')


def _empty_result():
    return {'schema_version': 1, 'engine': ENGINE, 'profile': PROFILE, 'limits': dict(LIMITS),
            'label': LABEL, 'complete': False, 'effective_authorization': False,
            'operational_ready': False, 'barriers': list(BARRIERS), 'reasons': [],
            'groups': [], 'items': [], 'contract_digest': None, 'manifest_digest': None,
            'capacity_diagnostics': []}


def _evaluate_payload(fixture):
    """Internal source-validation seam. Public callers must use compare_fixture."""
    result = _empty_result()
    try:
        _bounded(fixture)
        _fields(fixture, 'schema_version fixture_id revision contract contract_digest manifest manifest_digest candidates')
        if type(fixture['schema_version']) is not int or fixture['schema_version'] != 1 or type(fixture['revision']) is not int or fixture['revision'] != 1:
            raise FixtureIssue('UNSUPPORTED_FIXTURE_VERSION')
        _identity(fixture['fixture_id'])
        contract = fixture['contract']
        _contract(contract)
        digest = content_digest('contract', contract)
        if digest != fixture['contract_digest']:
            raise FixtureIssue('CONTRACT_DIGEST_MISMATCH')
        result['contract_digest'] = digest
        candidates, manifest, ids = fixture['candidates'], fixture['manifest'], contract['pool_ids']
        if any(type(value) is not list for value in (candidates, manifest, ids)):
            raise FixtureIssue('MANIFEST_INVALID')
        if not 1 <= len(ids) <= LIMITS['candidates']:
            raise FixtureIssue('EMPTY_POOL' if not ids else 'POOL_RESOURCE_LIMIT')
        for identity in ids:
            _identity(identity)
        if len(set(ids)) != len(ids) or ids != sorted(ids):
            raise FixtureIssue('MANIFEST_IDS_INVALID')
        for entry in manifest:
            _fields(entry, 'id input_digest calculation_digest')
            _identity(entry['id'])
        for entry in candidates:
            _fields(entry, 'id contract_digest inputs calculation input_digest calculation_digest')
            _identity(entry['id'])
        if (sorted(row['id'] for row in candidates) != ids or
                sorted(row['id'] for row in manifest) != ids):
            raise FixtureIssue('POOL_MANIFEST_MISMATCH')
        manifest = sorted(manifest, key=lambda row: row['id'])
        manifest_digest = content_digest('manifest', manifest)
        if fixture['manifest_digest'] != manifest_digest:
            raise FixtureIssue('MANIFEST_DIGEST_MISMATCH')
        result['manifest_digest'] = manifest_digest
        manifest_by_id = {row['id']: row for row in manifest}
        for candidate in sorted(candidates, key=lambda row: row['id']):
            try:
                if candidate['contract_digest'] != digest:
                    raise FixtureIssue('COMPARISON_CONTRACT_MISMATCH')
                inputs = candidate['inputs']
                _fields(inputs, ' '.join(CRITERIA))
                for value in inputs.values():
                    _fields(value, 'value source_type unit')
                calculated = calculate_synthetic(criteria=contract['criteria'], inputs=inputs,
                    definitions=contract['definitions'], judgments=contract['judgments'],
                    validation=contract['validation'])
                if not calculated['complete'] or calculated['reasons']:
                    for code in calculated['reasons']:
                        result['reasons'].append({'code': code, 'synthetic_id': candidate['id']})
                    raise FixtureIssue('CALCULATION_INCOMPLETE')
                # Explicit score parsing gives malformed/absent scores useful reasons.
                if type(candidate['calculation']) is not dict:
                    raise FixtureIssue('G15_REPLAY_MISMATCH')
                _score(candidate['calculation'].get('score_0_1'))
                if canonical(calculated) != canonical(candidate['calculation']):
                    raise FixtureIssue('G15_REPLAY_MISMATCH')
                if [row['criterion'] for row in calculated['traces']] != list(CRITERIA):
                    raise FixtureIssue('TRACE_ORDER_INVALID')
                input_digest = content_digest('inputs', inputs)
                calculation_digest = content_digest('calculation', calculated)
                expected = {'id': candidate['id'], 'input_digest': input_digest,
                            'calculation_digest': calculation_digest}
                if (candidate['input_digest'] != input_digest or candidate['calculation_digest'] != calculation_digest or
                        manifest_by_id[candidate['id']] != expected):
                    raise FixtureIssue('CANDIDATE_DIGEST_MISMATCH')
                result['items'].append({'id': candidate['id'], 'input_digest': input_digest,
                    'calculation_digest': calculation_digest, 'calculation': calculated})
            except FixtureIssue as error:
                result['reasons'].append({'code': str(error), 'synthetic_id': candidate['id']})
        if not result['reasons']:
            result['groups'] = _groups(result['items'], contract['direction'])
            result['complete'] = True
            capacity = contract['illustrative_capacity']
            if capacity is not None:
                if len(ids) > capacity:
                    result['capacity_diagnostics'].append('ILLUSTRATIVE_CAPACITY_EXCEEDED')
                if any(row['position_start'] <= capacity < row['position_end'] for row in result['groups']):
                    result['capacity_diagnostics'].append('TIE_CROSSES_ILLUSTRATIVE_BOUNDARY')
        else:
            # Never expose a valid-subset comparison as a complete pool.
            result['items'] = []
    except FixtureIssue as error:
        result['reasons'].append({'code': str(error), 'synthetic_id': None})
    result['digest'] = content_digest('result', result)
    return result


def compare_fixture(fixture_name):
    """Only supported numerical entry: a name in the checksum-pinned registry."""
    from .ranking_fixtures import load_fixture
    try:
        fixture = load_fixture(fixture_name)
    except FixtureIssue as error:
        result = _empty_result()
        result['reasons'] = [{'code': str(error), 'synthetic_id': None}]
        result['digest'] = content_digest('result', result)
        return result
    return _evaluate_payload(fixture)
