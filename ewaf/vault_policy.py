"""Shared household scoring contract; eligibility remains the program's Admin review."""
from datetime import date
from django.conf import settings
from django.core.exceptions import ValidationError
from .household_criteria import CRITERIA, SOURCES

CONTRACT = 'registered_household_vault_v1'
SOURCE_ONLY = 'weights_and_sources'
SCORING_PENDING_MESSAGE = (
    'Weights and data sources are approved. Programs can be published and accept applications during their approved schedule. '
    'Scoring is pending approved calculation rules. Calculation, ranking and beneficiary selection remain blocked until those rules and verified inputs are ready.'
)
SOURCE_LABELS = {
    'HI': 'Household monthly income (PHP) from member registration',
    'SI': 'Verified supporting documents and 4Ps membership, when available',
    'ES': 'Employment Status from member registration',
    'PA': 'Confirmed, non-voided assistance releases in this system',
    'HM': 'Number of Household members from member registration',
}


def source_policy(method=None):
    """The confirmed sources, without inventing a category score or range."""
    from .dataset_methods import (SES, HOUSEHOLD, SES_SOURCE, SES_CRITERIA, SES_METHODS,
                                 COMPOSITE, COMPOSITE_SOURCE, ses_description)
    if method in SES_METHODS:
        labels = {'SES': ses_description(method), 'ES': 'Accepted employment finding',
            'PA': SOURCE_LABELS['PA'], 'HM': 'Accepted household count under the approved definition'}
        sources = {'SES': 'accepted_household_income', 'ES': 'accepted_employment_category',
            'PA': 'successful_releases', 'HM': 'accepted_household_assessment'}
        units = {'SES': 'PHP/month', 'ES': 'category', 'PA': 'records', 'HM': 'persons'}
        if method == COMPOSITE:
            sources['SES'] = 'accepted_household_income_and_4ps'
        return {'method': method, 'source_contract': COMPOSITE_SOURCE if method == COMPOSITE else SES_SOURCE,
            'configuration_scope': SOURCE_ONLY, 'eligibility': {},
            'criteria': {code: {'source_type': sources[code],
                'value_type': 'decimal' if code == 'SES' else 'category' if code == 'ES' else 'integer',
                'unit': units[code], 'measure': labels[code]} for code in SES_CRITERIA}}
    if method not in (None, HOUSEHOLD):
        raise ValidationError('Select a supported Vault method.')
    kinds = {'HI': 'decimal', 'SI': 'category', 'ES': 'category', 'PA': 'integer', 'HM': 'integer'}
    units = {'HI': 'PHP/month', 'SI': 'category', 'ES': 'category', 'PA': 'records', 'HM': 'persons'}
    return {'source_contract': CONTRACT, 'configuration_scope': SOURCE_ONLY, 'eligibility': {},
        'criteria': {code: {'source_type': SOURCES[code], 'value_type': kinds[code],
            'unit': units[code], 'measure': SOURCE_LABELS[code]} for code in CRITERIA}}


def scoring_pending(policy):
    return policy.get('configuration_scope') == SOURCE_ONLY


def require_scoring_rules(policy):
    if scoring_pending(policy):
        raise ValidationError(SCORING_PENDING_MESSAGE)


def enabled():
    return getattr(settings, 'EWAF_VAULT_ENABLED', False)


def validate(policy, judgments):
    from .operational_policy import validate as validate_calculation
    from .weight_input import validate_provenance
    validate_provenance(policy.get('weight_input'), judgments)
    if scoring_pending(policy):
        from .dataset_methods import method_of
        from .vault_weights import is_direct, replay
        if {key: value for key, value in policy.items() if key != 'weight_input'} != source_policy(method_of(policy)):
            raise ValidationError('Use the confirmed member-registration and assistance-release sources.')
        from .weight_input import proposal_criteria
        from .weight_input import replay_ahp, METHOD, CURRENT_METHOD
        calculated = replay_ahp(judgments, policy.get('weight_input')) if not is_direct(policy) else None
        from .household_criteria import criteria_for
        if not is_direct(policy) and proposal_criteria({'weights': calculated['weights']}) != criteria_for(policy):
            raise ValidationError('The weight signature must match the selected method.')
        if is_direct(policy):
            if criteria_for(policy) != CRITERIA:
                raise ValidationError('SES weights require the four-criterion slider-generated AHP method.')
            replay(policy['weight_input'], judgments)
            return
        if calculated['reference_consistency'] != 'PASSED':
            raise ValidationError('The weights must pass the AHP consistency check.')
        from .dataset_methods import is_ses
        if is_ses(policy):
            from .dataset_methods import is_composite
            allowed = (METHOD, CURRENT_METHOD) if is_composite(policy) else (METHOD,)
            if (policy.get('weight_input') or {}).get('method') not in allowed:
                raise ValidationError('Retain the reviewed SES slider-generated comparison provenance.')
            from .revised.contracts import validate_weight_total
            validate_weight_total(calculated['weights'])
        return
    from .vault_weights import is_direct
    if is_direct(policy):
        raise ValidationError('Percentage weights require the document-based dataset scoring policy.')
    validate_calculation(policy, judgments)
    if (policy.get('source_contract') != CONTRACT or set(policy['criteria']) != set(CRITERIA)
            or policy.get('eligibility') != {}):
        raise ValidationError('Use the five registered household criteria and the program eligibility review.')
    try:
        start, end = (date.fromisoformat(policy[key]) for key in ('assessment_start', 'assessment_end'))
        if start > end:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValidationError('Record a valid shared assessment period and cutoff.') from None
    from documents.models import DocumentType
    expected_types = {'HI': 'decimal', 'SI': 'category', 'ES': 'category', 'PA': 'integer', 'HM': 'integer'}
    expected_units = {'HI': 'PHP/month', 'SI': 'category', 'ES': 'category', 'PA': 'records', 'HM': 'persons'}
    for code, rule in policy['criteria'].items():
        if (rule['source_type'] != SOURCES[code] or rule['value_type'] != expected_types[code]
                or rule['unit'] != expected_units[code]):
            raise ValidationError(f'{code}: use the registered source and its correct value format.')
        if code == 'PA':
            if rule['unit'] != 'records':
                raise ValidationError('Previous assistance counts verified successful release records.')
        else:
            types = rule.get('evidence_document_types')
            if (not isinstance(types, list) or not types or any(type(item) is not int for item in types)
                    or len(set(types)) != len(types)
                    or DocumentType.objects.filter(pk__in=types).count() != len(types)):
                raise ValidationError(f'{code}: select the approved document types used to verify registered values.')
