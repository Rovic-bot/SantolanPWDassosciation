"""Slider proposals projected onto the explicit criterion family's discrete AHP.

For positive weights a_ij = w_i / w_j is a consistent reciprocal matrix, but
arbitrary ratios are NOT supported judgments in the validated discrete engine.
We quantize each ratio by minimum multiplicative error, then run that engine.
Its resulting weights, not the proposed percentages, remain authoritative.
"""
from decimal import Decimal
from fractions import Fraction

from django.core import signing
from django.core.exceptions import ValidationError

from .operational_policy import ahp
from .household_criteria import CRITERIA, LEGACY_CRITERIA, NAMES, pairs_for


def proposal_criteria(proposal):
    from .dataset_methods import SES_CRITERIA
    keys = set(proposal.get('weights', {})) if isinstance(proposal, dict) and isinstance(proposal.get('weights'), dict) else set()
    if keys == set(SES_CRITERIA):
        return SES_CRITERIA
    return LEGACY_CRITERIA if keys == set(LEGACY_CRITERIA) else CRITERIA


METHOD = 'slider-ratio-projection-v1'
CURRENT_METHOD = 'slider-ratio-projection-exact-ahp-v2'
SALT = 'ewaf.weight-input.v1'


def validate_proposal(proposal):
    if not isinstance(proposal, dict) or set(proposal) != {'order', 'weights'}:
        raise ValidationError('A complete criterion weight proposal is required.')
    order, weights = proposal['order'], proposal['weights']
    criteria = proposal_criteria(proposal)
    if (not isinstance(order, list) or len(order) != len(criteria) or any(type(code) is not str for code in order)
            or set(order) != set(criteria)
            or not isinstance(weights, dict) or set(weights) != set(criteria)):
        raise ValidationError('Choose every criterion in this version exactly once.')
    values = [weights[code] for code in order]
    if any(type(value) is not int or not 1 <= value <= 10000 for value in values) or sum(values) != 10000:
        raise ValidationError('Positive weights must total exactly 100.00%.')
    if values != sorted(values, reverse=True):
        raise ValidationError('Weights must follow the selected priority order; equal priorities are allowed.')
    if values[0] > 9 * values[-1]:
        raise ValidationError('Keep the highest weight within nine times the lowest for the existing AHP scale.')
    return proposal


def percentages(weights, priority=None):
    """Largest-remainder display rounding; full precision stays in AHP validation."""
    criteria = proposal_criteria({'weights': weights})
    priority = priority or criteria
    exact = {code: Fraction(str(weights[code])) for code in criteria}
    total = sum(exact.values())
    scaled = {code: exact[code] * 10000 / total for code in criteria}
    units = {code: int(scaled[code]) for code in criteria}
    order = sorted(priority, key=lambda code: scaled[code] - units[code], reverse=True)
    for code in order[:10000 - sum(units.values())]:
        units[code] += 1
    return units


def project(proposal, *, method=METHOD):
    validate_proposal(proposal)
    from .dataset_methods import SES_CRITERIA
    if method not in (METHOD, CURRENT_METHOD) or method == CURRENT_METHOD and proposal_criteria(proposal) != SES_CRITERIA:
        raise ValidationError('Select a supported projection for these criteria.')
    judgments = {}
    for pair in pairs_for(proposal_criteria(proposal)):
        a, b = pair.split(':')
        ratio = Fraction(proposal['weights'][a], proposal['weights'][b])
        magnitude = max(ratio, 1 / ratio)
        # Choosing the smaller integer on a distance tie avoids overstating
        # relative importance. Reciprocation is exact and order-independent.
        nearest = min(range(1, 10), key=lambda n: (max(magnitude / n, n / magnitude), n))
        judgments[pair] = f'1/{nearest}' if ratio < 1 and nearest != 1 else str(nearest)
    if method == CURRENT_METHOD:
        from .current_ahp import ahp as current_ahp
        result = current_ahp(judgments)
    else:
        result = ahp(judgments)
    if result['reference_consistency'] != 'PASSED':
        raise ValidationError('The derived comparisons do not pass the existing AHP consistency check. Adjust the proposal.')
    ordered = [Decimal(result['weights'][code]) for code in proposal['order']]
    if ordered != sorted(ordered, reverse=True):
        raise ValidationError('The AHP result does not preserve the proposed priority order. Adjust the proposal.')
    provenance = {'method': method, 'proposal': proposal,
                  'judgment_origin': 'generated_from_slider_ratios_not_independently_elicited'}
    return judgments, result, provenance


def validate_provenance(provenance, judgments):
    if provenance is None:
        return  # Existing configurations retain their exact original payload.
    if not isinstance(provenance, dict):
        raise ValidationError('Weight input provenance is invalid.')
    from .vault_weights import METHOD as DIRECT_METHOD, replay
    if provenance.get('method') == DIRECT_METHOD:
        replay(provenance, judgments)
        return
    projected, _, expected = project(provenance.get('proposal'), method=provenance.get('method'))
    if provenance != expected or projected != judgments:
        raise ValidationError('Slider provenance does not match the stored AHP comparisons.')


def replay_ahp(judgments, provenance=None):
    """Select precision only from retained provenance, never from today's defaults."""
    validate_provenance(provenance, judgments)
    if provenance and provenance.get('method') == CURRENT_METHOD:
        from .current_ahp import ahp as current_ahp
        return current_ahp(judgments)
    return ahp(judgments)


def preview(proposal, *, program, expected, method=METHOD):
    judgments, result, provenance = project(proposal, method=method)
    units = percentages(result['weights'], proposal['order'])
    token = signing.dumps({'program': str(program), 'expected': expected, 'provenance': provenance}, salt=SALT)
    storage_errors = []
    from .dataset_methods import SES_CRITERIA
    if proposal_criteria(proposal) == SES_CRITERIA:
        from .revised.contracts import validate_weight_total
        try:
            validate_weight_total(result['weights'])
        except ValidationError:
            storage_errors = ['The calculated weights do not satisfy the retained precision/total contract. '
                'It rejects any stored total above 1, including a tiny 50-digit rounding excess. '
                'Keep this as an unapproved draft or adjust the proposal. Coefficients are not rescaled.']
    return {'token': token, 'rows': [
        {'code': code, 'name': NAMES[code], 'target': f"{proposal['weights'][code] / 100:.2f}",
         'actual': f'{units[code] / 100:.2f}'} for code in proposal['order']],
        'judgments': judgments, 'consistency': {'result': result['reference_consistency'],
            'CR': result['CR'], 'RI': result['RI'], 'criteria_count': len(result['weights'])},
        'provenance': provenance['judgment_origin'], 'storage_errors': storage_errors}


def accept(token, proposal, *, program, expected):
    try:
        signed = signing.loads(token, salt=SALT, max_age=3600)
    except signing.BadSignature as error:
        raise ValidationError('Review the AHP preview again; its confirmation is missing, expired or invalid.') from error
    if (signed.get('program') != str(program) or signed.get('expected') != expected
            or signed.get('provenance', {}).get('proposal') != proposal):
        raise ValidationError('The proposal changed after preview. Review the current AHP result before saving.')
    judgments, _, provenance = project(proposal, method=signed['provenance'].get('method'))
    if signed['provenance'] != provenance:
        raise ValidationError('Review the current AHP preview before saving.')
    return judgments, provenance


def initial_state(configuration):
    weights = configuration.validation['weights'] if configuration and configuration.validation else None
    criteria = proposal_criteria({'weights': weights})
    order = sorted(criteria, key=lambda code: -Decimal((weights or {}).get(code, 0)))
    if configuration and configuration.policy.get('weight_input'):
        order = configuration.policy['weight_input']['proposal']['order']
    actual = percentages(weights, order) if weights else None
    proposal = {'order': order, 'weights': actual or dict.fromkeys(criteria, 10000 // len(criteria))}
    try:
        validate_proposal(proposal)
    except ValidationError:
        proposal = {'order': order, 'weights': dict.fromkeys(criteria, 10000 // len(criteria))}
    return {'proposal': proposal, 'resetProposal': proposal, 'names': {code: NAMES[code] for code in criteria}, 'hasSavedWeights': actual is not None,
            'startingFromSaved': actual == proposal['weights'] if actual else False}
