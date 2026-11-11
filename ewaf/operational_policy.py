"""Explicit policy validation and exact four-criterion mathematics. No policy defaults."""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime

from .household_criteria import CRITERIA, LEGACY_CRITERIA, criteria_for, pairs_for, engine_for, SOURCES
from .four_criterion_development import PAIRS as LEGACY_PAIRS


def ahp(judgments):
    from .dataset_methods import SES_CRITERIA
    if isinstance(judgments, dict) and set(judgments) == set(pairs_for(SES_CRITERIA)):
        from .ses_math import ahp as calculate_weights
    elif isinstance(judgments, dict) and set(judgments) == set(LEGACY_PAIRS):
        from .four_criterion_development import ahp as calculate_weights
    else:
        from .household_math import ahp as calculate_weights
    return calculate_weights(judgments)

from .evidence import canonical, SOURCE_TYPES
from .normalization import number, NumericIssue

ENGINE = 'ewaf-operational-four-1'
MAX_POOL = 2000  # Engineering ceiling, never an application/beneficiary quota.


def findings(policy, judgments):
    from .vault_policy import scoring_pending, SCORING_PENDING_MESSAGE
    if isinstance(policy, dict) and scoring_pending(policy):
        return [SCORING_PENDING_MESSAGE]
    errors = []
    def missing(path, value):
        if value is None or value == '' or isinstance(value, str) and not value.strip():
            errors.append(path + ': required')
            return True
        return False
    if not isinstance(policy, dict) or not isinstance(judgments, dict):
        return ['policy: invalid structure']
    for key in ('authority_reference', 'authorized_scope', 'approval_date', 'effective_from', 'effective_until',
                'selection_rule', 'tie_rule', 'tie_procedure', 'classification_mode', 'edge_cases', 'pa_scope', 'pa_period'):
        missing(key, policy.get(key))
    criteria = criteria_for(policy)
    if set(policy.get('criteria', {})) != set(criteria):
        errors.append('criteria: record the complete criterion set for this version')
    for code in criteria:
        rule = policy.get('criteria', {}).get(code, {})
        for key in ('measure', 'source_type', 'value_type', 'unit', 'direction', 'observation_period'):
            missing(f'{code}.{key}', rule.get(key))
        for key in ('lower', 'upper'):
            missing(f'{code}.bounds.{key}', rule.get('bounds', {}).get(key))
        if criteria == CRITERIA and rule.get('source_type') not in ('', None, SOURCES[code]):
            errors.append(f'{code}.source_type: use the registered household source')
        if rule.get('source_type') and rule['source_type'] not in SOURCE_TYPES[code]:
            errors.append(f'{code}.source_type: unsupported source')
        if rule.get('source_type') in ('income_category', 'employment_status', 'four_ps_membership'):
            from members.profile import INCOME, EMPLOYMENT
            choices = [('Yes', 'Yes'), ('No', 'No')] if rule['source_type'] == 'four_ps_membership' else INCOME if rule['source_type'] == 'income_category' else EMPLOYMENT
            encoding = rule.get('encoding')
            if (rule.get('value_type') != 'category' or not isinstance(encoding, dict) or
                    not encoding or set(encoding) - set(dict(choices))):
                errors.append(f'{code}.encoding: explicitly map recorded membership category identifiers; legacy encodings are not interchangeable')
        if rule.get('direction') and rule['direction'] not in ('benefit', 'inverse'):
            errors.append(f'{code}.direction: choose benefit or inverse')
        try:
            bounds = rule.get('bounds', {})
            if bounds.get('lower') not in (None, '') and bounds.get('upper') not in (None, ''):
                if number(bounds['lower']) >= number(bounds['upper']):
                    errors.append(f'{code}.bounds: upper must exceed lower; equal bounds cannot calculate')
            encoding = rule.get('encoding')
            if rule.get('value_type') in ('text', 'category') and not encoding:
                errors.append(f'{code}.encoding: approved category-to-value mapping required')
            if encoding:
                if not isinstance(encoding, dict):
                    raise ValueError
                for label, value in encoding.items():
                    if not isinstance(label, str) or not label.strip():
                        raise ValueError
                    number(value)
        except (NumericIssue, ValueError, TypeError):
            errors.append(f'{code}: invalid exact number or encoding')
    from .vault_policy import CONTRACT as VAULT_CONTRACT
    for role in (() if policy.get('source_contract') == VAULT_CONTRACT else ('functional_need', 'consent', 'accessible_alternative')):
        rule = policy.get('eligibility', {}).get(role, {})
        for key in ('item', 'accepted_outcome'):
            missing(f'PR.{role}.{key}', rule.get(key))
    if policy.get('selection_rule') not in (None, '', 'reasoned_human_within_slots'):
        errors.append('selection_rule: unsupported procedure; never automatically select')
    if policy.get('tie_rule') not in (None, '', 'hold', 'reasoned_human'):
        errors.append('tie_rule: unsupported procedure; no automatic tie-break')
    if policy.get('edge_cases') not in (None, '', 'block'):
        errors.append('edge_cases: missing/disputed/stale/out-of-range values must block')
    if policy.get('pa_scope') not in (None, '', 'all_programs', 'this_program'):
        errors.append('pa_scope: unsupported scope')
    if policy.get('pa_period') not in (None, '', 'all_retained', 'date_range'):
        errors.append('pa_period: unsupported period')
    if policy.get('pa_period') == 'date_range':
        try:
            start, end = date.fromisoformat(policy['pa_start']), date.fromisoformat(policy['pa_end'])
            if start > end:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            errors.append('pa_start / pa_end: an explicit valid inclusive date range is required')
    try:
        approved = date.fromisoformat(policy['approval_date'])
        start, end = parse_datetime(policy['effective_from']), parse_datetime(policy['effective_until'])
        if not start or not end or not start.tzinfo or not end.tzinfo or start >= end or approved > start.date():
            raise ValueError
    except (KeyError, TypeError, ValueError):
        errors.append('approval_date / effective_from / effective_until: valid authorized dates and timezone required')
    mode = policy.get('classification_mode')
    if mode not in (None, '', 'none', 'thresholds'):
        errors.append('classification_mode: select explicitly none or approved thresholds')
    if mode == 'thresholds':
        try:
            rows = policy['classifications']
            if not isinstance(rows, list) or not rows:
                raise ValueError
            lower = Decimal(0)
            for row in rows:
                if set(row) != {'label', 'lower', 'upper'} or not str(row['label']).strip():
                    raise ValueError
                a, b = number(row['lower']), number(row['upper'])
                if a != lower or b <= a:
                    raise ValueError
                lower = b
            if lower != 100:
                raise ValueError
        except (KeyError, TypeError, ValueError, NumericIssue):
            errors.append('classifications: contiguous approved [lower, upper) ranges from 0 to 100 required; final upper inclusive')
    for pair in pairs_for(criteria):
        missing('AHP.' + pair, judgments.get(pair))
    try:
        if ahp(judgments)['reference_consistency'] != 'PASSED':
            errors.append('AHP.CR: consistency must satisfy 0 <= CR < 0.10')
    except ValidationError:
        errors.append('AHP: complete valid reciprocal-scale comparisons are required')
    return errors


def validate(policy, judgments):
    errors = findings(policy, judgments)
    if errors:
        raise ValidationError(errors)
    return policy


def calculations(snapshot, configuration):
    if getattr(configuration, 'uses_dataset_scoring', getattr(configuration, 'dataset_policy_id', None)):
        from .revised.live_math import calculations as dataset_calculations
        return dataset_calculations(snapshot, configuration)
    if criteria_for(configuration.policy) == LEGACY_CRITERIA:
        from .four_policy import calculate
    else:
        from .household_math import calculate
    engine = engine_for(configuration.policy)
    result = {}
    for key, entry in snapshot['eligible'].items():
        row = calculate(inputs=entry['inputs'], definitions=configuration.policy['criteria'],
                        judgments=configuration.judgments, validation=configuration.validation)
        row.update(engine=engine, profile=engine, operational_ready=True)
        if configuration.policy['classification_mode'] == 'thresholds':
            score = Decimal(row['score_0_100'])
            row['classification'] = next(item['label'] for item in configuration.policy['classifications']
                if Decimal(item['lower']) <= score < Decimal(item['upper']) or score == Decimal(item['upper']) == 100)
        result[key] = row
    for row in result.values():
        score = Decimal(row['score_0_1'])
        row['comparison'] = {'higher': sum(Decimal(r['score_0_1']) > score for r in result.values()),
                             'equal': sum(Decimal(r['score_0_1']) == score for r in result.values()),
                             'business_rank': None}
    return canonical(result)
