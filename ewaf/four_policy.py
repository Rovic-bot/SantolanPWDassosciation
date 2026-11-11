"""Explicit, inactive four-criterion test policy. No Association defaults."""
from decimal import Decimal, localcontext

from django.core.exceptions import ValidationError

from .four_criterion_development import ahp, CONTEXT, text
from .four_criterion_reference import REFERENCE_CRITERIA
from .normalization import normalize, number, NumericIssue
from .weighted_scoring import bounded_fixture

CRITERIA = REFERENCE_CRITERIA
PROFILE = 'g18-four-fictional-policy-1'
ENGINE = 'g18-four-minmax-wsm-1'
POOL_ENGINE = 'g18-four-complete-pool-1'
BINDING_PROFILE = 'g18-four-complete-pool-1:four-fictional-1'
METHOD = 'normalized-column-row-average'
PURPOSE = 'FICTIONAL_DISPOSABLE_TEST_ONLY'
ELIGIBILITY_KEYS = ('functional_need', 'consent', 'accessible_alternative')
PA_PERIOD = 'Fictional test only: all retained successful nonvoided releases across all programs; no lookback cutoff'


def proposal(value):
    """No omitted policy choice is supplied by the server."""
    try:
        bounded_fixture(value)
        if (not isinstance(value, dict) or set(value) != {'purpose', 'criteria', 'eligibility'} or
                value['purpose'] != PURPOSE or set(value['criteria']) != set(CRITERIA)):
            raise ValueError
        gate = value['eligibility']
        if set(gate) != set(ELIGIBILITY_KEYS) or len({v['item'] for v in gate.values()}) != 3:
            raise ValueError
        for rule in gate.values():
            if (set(rule) != {'item', 'accepted_outcome'} or any(type(v) is not str or not v.strip() or
                    len(v) > 100 for v in rule.values())):
                raise ValueError
        from .evidence import SOURCE_TYPES
        for code, rule in value['criteria'].items():
            if set(rule) != {'measure', 'source_type', 'value_type', 'unit', 'encoding', 'direction',
                             'bounds', 'observation_period', 'edge_cases'}:
                raise ValueError
            for key in ('measure', 'source_type', 'value_type', 'unit', 'observation_period', 'edge_cases'):
                if type(rule[key]) is not str or not rule[key].strip():
                    raise ValueError
            if rule['source_type'] not in SOURCE_TYPES[code] or rule['direction'] not in ('benefit', 'inverse'):
                raise ValueError
            if code == 'PA' and (rule['observation_period'] != PA_PERIOD or rule['unit'] != 'records'):
                raise ValueError
            bounds = rule['bounds']
            if set(bounds) != {'method', 'lower', 'upper'} or bounds['method'] != 'fixed':
                raise ValueError
            if number(bounds['lower']) >= number(bounds['upper']):
                raise ValueError
            encoding = rule['encoding']
            if encoding is not None:
                if not isinstance(encoding, dict) or not encoding:
                    raise ValueError
                for key, item in encoding.items():
                    if not isinstance(key, str) or not key:
                        raise ValueError
                    number(item)
        return value
    except (KeyError, TypeError, ValueError, NumericIssue) as error:
        raise ValidationError('FOUR_TEST_POLICY_INCOMPLETE') from error


def validate_configuration(row):
    result = ahp(row.judgments)
    if (row.criteria_order != list(CRITERIA) or row.method != METHOD or
            row.canonical_judgments != result['pairs'] or not row.policy_id or not row.terms_revision_id):
        raise ValidationError('FOUR_CONFIGURATION_INVALID')


def validate_validation(row):
    row.configuration.clean()
    if (row.configuration.profile != PROFILE or row.engine != ENGINE or
            row.result != ahp(row.configuration.judgments)):
        raise ValidationError('FOUR_VALIDATION_REPLAY_INVALID')


def validate_policy(row):
    if (row.engine != ENGINE or row.criteria_order != list(CRITERIA) or
            not all((row.configuration_id, row.validation_id, row.evidence_policy_id, row.terms_revision_id)) or
            row.configuration.profile != PROFILE or row.validation.profile != PROFILE or
            proposal(row.proposal) != row.proposal):
        raise ValidationError('FOUR_POLICY_PROFILE_INVALID')
    row.configuration.clean()
    row.validation.clean()


def calculate(*, inputs, definitions, judgments, validation):
    """Four traces, exact reference weights; shared scalar normalization only."""
    replay = ahp(judgments)
    if replay != validation or replay['reference_consistency'] != 'PASSED':
        raise ValidationError('FOUR_WEIGHT_REPLAY_INVALID')
    if set(inputs) != set(CRITERIA) or set(definitions) != set(CRITERIA):
        raise ValidationError('FOUR_INPUT_SET_INVALID')
    traces = []
    with localcontext(CONTEXT):
        total = Decimal(0)
        for code in CRITERIA:
            entry, rule = inputs[code], definitions[code]
            if any(entry[key] != rule[key] for key in ('unit', 'source_type')):
                raise ValidationError('FOUR_INPUT_UNIT_INVALID')
            raw = entry['value']
            if rule['encoding'] is not None:
                if type(raw) is not str or raw not in rule['encoding']:
                    raise ValidationError('FOUR_ENCODING_UNAVAILABLE')
                raw = rule['encoding'][raw]
            normalized = normalize(raw, rule['bounds']['lower'], rule['bounds']['upper'], rule['direction'])
            if not normalized['complete']:
                raise ValidationError(normalized['reasons'])
            weight = Decimal(replay['weights'][code])
            contribution = Decimal(normalized['normalized']) * weight
            total += contribution
            traces.append({**normalized, 'criterion': code, 'weight': text(weight),
                'contribution': text(contribution), 'source_type': entry['source_type'], 'unit': entry['unit']})
        if not 0 <= total <= 1:
            raise ValidationError('FOUR_SCORE_RANGE_INVALID')
        return {'engine': ENGINE, 'profile': PROFILE, 'criteria': list(CRITERIA), 'complete': True,
            'traces': traces, 'score_0_1': text(total), 'score_0_100': text(total * 100),
            'operational_ready': False, 'classification': None, 'business_rank': None}
