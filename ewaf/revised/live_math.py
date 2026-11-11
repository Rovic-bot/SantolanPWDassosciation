"""Exact new-method calculation from a frozen accepted pool and retained weights."""
from fractions import Fraction
from django.core.exceptions import ValidationError
from ewaf.evidence import canonical, digest
from .engine import METHOD
from .math import number, packed, display, CalculationError
from ewaf import dataset_methods as methods


def calculations(snapshot, configuration):
    from . import automatic_inputs, rolling_pool
    configuration = rolling_pool.from_snapshot(snapshot, configuration)
    from ewaf import employment_scoring, household_scoring
    configuration = employment_scoring.runtime(configuration, snapshot)
    employment_scores = employment_scoring.encoding(snapshot)
    household_rule = household_scoring.retained(snapshot, configuration)
    if automatic_inputs.enabled(configuration.policy):
        automatic_inputs.validate_snapshot(snapshot, configuration)
    method = methods.method_of(configuration.policy) if hasattr(configuration, 'policy') else METHOD
    codes, directions = methods.criteria(method), methods.directions(method)
    composite = method == methods.COMPOSITE
    if composite:
        from .composite_ses import FORMULA, calculate as composite_ses
        if configuration.policy.get('ses_formula') != FORMULA:
            raise ValidationError('Retain the exact approved composite-SES formula version and internal 9/10 and 1/10 coefficients.')
    if snapshot.get('engine') != method or snapshot.get('configuration_digest') != configuration.digest:
        raise ValidationError('Calculation must bind the exact new-method configuration snapshot.')
    from ewaf.shared_weights import retained
    selected_weights = retained(snapshot, configuration)
    weight_values = selected_weights['weights'] if selected_weights else configuration.validation['weights']
    weight_digest = selected_weights['digest'] if selected_weights else configuration.validation['weight_digest']
    eligible = snapshot.get('eligible', {})
    if not eligible:
        raise ValidationError('A complete nonempty accepted pool is required at calculation time.')
    try:
        if set(weight_values) != set(codes) or any(set(row['inputs']) != set(codes) for row in eligible.values()):
            raise ValidationError('The accepted inputs and retained weights must match the exact method signature.')
        rows = {key: [number(employment_scores[entry['inputs'][code]['value']] if code == 'ES' else entry['inputs'][code]['value'])
                      for code in codes] for key, entry in eligible.items()}
        weights = [number(weight_values[code]) for code in codes]
        if composite:
            for key, values in rows.items():
                if values[codes.index('SES')] < 0:
                    raise ValidationError('Accepted household income cannot be negative.')
                composite_ses(Fraction(0), eligible[key]['inputs']['SES'].get('household_four_ps'))
    except (CalculationError, KeyError, TypeError) as error:
        raise ValidationError('The accepted pool contains an invalid or unresolved input.') from error
    lower = [min(row[j] for row in rows.values()) for j in range(len(codes))]
    upper = [max(row[j] for row in rows.values()) for j in range(len(codes))]
    constant = [code for j, code in enumerate(codes) if lower[j] == upper[j]
                and not (household_rule and code == 'HM')]
    from ewaf.shared_calculation_rules import retained as retained_rules, FULL_CONSTANTS
    selected_rules = retained_rules(snapshot, configuration)
    constant_rule = (selected_rules or configuration.policy).get('constant_rule')
    constant_value = {rolling_pool.ZERO_CONSTANTS: Fraction(0), FULL_CONSTANTS: Fraction(1)}.get(constant_rule) if composite else None
    if constant and constant_value is None:
        raise ValidationError('Constant-value columns: ' + ', '.join(constant) + '. The bound policy stops calculation; no values are imputed.')
    result, exact = {}, {}
    slots = configuration.source['terms']['program']['slots']
    for key, row in rows.items():
        traces = []
        score = Fraction(0)
        for j, code in enumerate(codes):
            equal_column = upper[j] == lower[j]
            fixed_household = household_rule and code == 'HM'
            if fixed_household:
                normalized = household_scoring.normalize(row[j], upper[j])
            else:
                normalized = (constant_value if equal_column else
                    ((upper[j] - row[j]) if directions[j] == 'inverse' else (row[j] - lower[j])) / (upper[j] - lower[j]))
            adjustment = {}
            if composite and code == 'SES':
                income_need = normalized
                participation = eligible[key]['inputs']['SES']['household_four_ps']
                normalized, multiplier = composite_ses(income_need, participation)
                adjustment = {'ses_formula': FORMULA, 'income_need': packed(income_need),
                    'household_four_ps': participation, 'multiplier': packed(multiplier)}
            contribution = weights[j] * normalized
            score += contribution
            traces.append({'criterion': code, 'input': packed(row[j]), 'minimum': packed(lower[j]),
                'maximum': packed(upper[j]), 'direction': directions[j], 'normalized': packed(normalized),
                'weight': weight_values[code], 'contribution': packed(contribution), **adjustment,
                **({'normalization_rule': household_rule['version'], 'normalization_minimum': packed(Fraction(1))}
                   if fixed_household else {}),
                **({'constant_rule': constant_rule} if equal_column and not fixed_household else {})})
        exact[key] = score
        result[key] = {'engine': method, 'operational_ready': True, 'score_exact': str(score),
            'score_0_1': packed(score)['decimal'], 'score_0_100': packed(score * 100)['decimal'],
            'score_display': display(score * 100),
            'traces': traces, 'policy_digest': (configuration.policy['shared_policy_digest']
                if configuration.policy.get('fixed_scoring_version') else configuration.dataset_policy.digest),
            'weight_digest': weight_digest, 'assessment_cutoff': configuration.assessment_cutoff,
            'pool_digest': digest(snapshot['eligible']),
            **({'calculation_rule_digest': selected_rules['digest']} if selected_rules else {})}
    for key, score in exact.items():
        higher = sum(value > score for value in exact.values())
        equal = sum(value == score for value in exact.values())
        result[key]['comparison'] = {'higher': higher, 'equal': equal, 'business_rank': higher + 1,
            'capacity_boundary_tie': equal > 1 and higher < slots < higher + equal}
    return canonical(result)
