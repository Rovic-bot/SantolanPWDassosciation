"""Bounded proposals, never approved scoring policy."""
import json
from django.core.exceptions import ValidationError
from .normalization import CRITERIA, ENGINE, PROFILE, number, decimal_text, NumericIssue
from .evidence import SOURCE_TYPES

BARRIERS = ['CRITERION_POLICY_UNAPPROVED', 'CONFIGURATION_AUTHORIZATION_UNAVAILABLE',
            'OPERATIONAL_SCORING_UNAVAILABLE', 'PROCESSING_GATE_UNAVAILABLE']


def proposal(value):
    def bounded(node, depth=0):
        if depth > 5 or type(node) not in (dict, list, str, int, type(None)):
            raise ValidationError('Invalid or excessive proposal structure.')
        if isinstance(node, (dict, list)):
            if len(node) > 30:
                raise ValidationError('Proposal collection limit exceeded.')
            if isinstance(node, dict) and any(not isinstance(key, str) or len(key) > 200 for key in node):
                raise ValidationError('Proposal keys must be bounded text.')
            for child in (node.values() if isinstance(node, dict) else node):
                bounded(child, depth + 1)
        elif isinstance(node, str) and len(node) > 1000:
            raise ValidationError('Proposal text limit exceeded.')
        elif type(node) is int and node.bit_length() > 400:
            raise ValidationError('Proposal numeric limit exceeded.')
    bounded(value)
    if len(json.dumps(value)) > 24000 or not isinstance(value, dict) or set(value) != {'criteria'}:
        raise ValidationError('Supply only the five criterion proposals.')
    if not isinstance(value['criteria'], dict) or set(value['criteria']) != set(CRITERIA):
        raise ValidationError('Exactly SI, ES, PA, ND and PR are required; empty definitions remain pending.')
    output = json.loads(json.dumps(value))
    for code, definition in output['criteria'].items():
        if not isinstance(definition, dict) or set(definition) - {'measure', 'source_type', 'value_type', 'unit',
                'encoding', 'direction', 'bounds', 'observation_period', 'edge_cases', 'pending'}:
            raise ValidationError('Unknown criterion proposal field.')
        for key in ('measure', 'source_type', 'value_type', 'unit', 'direction', 'observation_period', 'edge_cases', 'pending'):
            if key in definition and (not isinstance(definition[key], str) or len(definition[key]) > 1000):
                raise ValidationError('Proposal definitions must be bounded text.')
        if definition.get('source_type') and definition['source_type'] not in SOURCE_TYPES[code]:
            raise ValidationError('Unsupported source type for criterion.')
        if definition.get('direction') and definition['direction'] not in ('benefit', 'inverse'):
            raise ValidationError('Use an explicit benefit/inverse proposal or leave pending.')
        encoding = definition.get('encoding')
        if encoding is not None:
            if not isinstance(encoding, dict) or any(not isinstance(key, str) or not key or len(key) > 200 for key in encoding):
                raise ValidationError('Encodings must map bounded category identifiers to decimal text.')
            try:
                definition['encoding'] = {key: decimal_text(number(value)) for key, value in encoding.items()}
            except NumericIssue as error:
                raise ValidationError(str(error)) from error
        bounds = definition.get('bounds')
        if bounds is not None:
            if not isinstance(bounds, dict) or set(bounds) - {'method', 'lower', 'upper', 'cohort_rule'} or bounds.get('method') not in ('fixed', 'proposed_cohort'):
                raise ValidationError('Explicit fixed or proposed_cohort bounds are required.')
            if 'cohort_rule' in bounds and not isinstance(bounds['cohort_rule'], str):
                raise ValidationError('Cohort proposal must be text.')
            for key in ('lower', 'upper'):
                if bounds.get(key) not in (None, ''):
                    try:
                        bounds[key] = decimal_text(number(bounds[key]))
                    except NumericIssue as error:
                        raise ValidationError(str(error)) from error
    return output


def proposal_reasons(snapshot):
    from . import four_policy
    if snapshot.get('purpose') == four_policy.PURPOSE:
        four_policy.proposal(snapshot)
        return [{'code': 'FOUR_FICTIONAL_POLICY_ONLY', 'source': None}]
    reasons = []
    for code in CRITERIA:
        entry = snapshot['criteria'][code]
        if any(not entry.get(key) for key in ('measure', 'source_type', 'value_type', 'unit', 'observation_period', 'edge_cases')):
            reasons.append({'code': 'SCORING_POLICY_INCOMPLETE', 'source': code})
        if not entry.get('direction'):
            reasons.append({'code': 'NORMALIZATION_DIRECTION_PENDING', 'source': code})
        bounds = entry.get('bounds') or {}
        if bounds.get('method') != 'fixed' or any(bounds.get(key) in (None, '') for key in ('lower', 'upper')):
            reasons.append({'code': 'BOUNDS_PENDING', 'source': code})
        else:
            lo, hi = number(bounds['lower']), number(bounds['upper'])
            if lo >= hi:
                reasons.append({'code': 'ZERO_RANGE' if lo == hi else 'BOUNDS_ORDER_INVALID', 'source': code})
        if entry.get('pending'):
            reasons.append({'code': 'SCORING_POLICY_INCOMPLETE', 'source': code})
    return reasons
