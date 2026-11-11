"""Explicit review choices for the new operational dataset method; no live defaults."""
from copy import deepcopy
from datetime import date
from fractions import Fraction
from django.core.exceptions import ValidationError
from django.utils.dateparse import parse_datetime
from .engine import METHOD, CRITERIA, ES, DIRECTIONS
from .policy import load_draft
from . import si
from ewaf import dataset_methods as methods

DECISIONS = {
    'A': ('WEIGHT_AUTHORITY',),
    'B': ('SI_RUBRIC_AUTHORITY',),
    'C': ('DOCUMENT_RULE_ADOPTION', 'CONSTANT_COLUMNS', 'INCOME_SOURCE_RULES', 'EMPLOYMENT_UNLISTED',
          'EVIDENCE_ACCEPTANCE', 'HISTORY_COMPLETENESS', 'ASSESSMENT_PERIODS', 'HOUSEHOLD_DEFINITION',
          'PA_SCOPE_AND_HISTORY', 'RANKING_AND_TIES', 'COMPLETE_POOL_AND_CORRECTIONS',
          'PRECISION_AND_CLASSIFICATION', 'POLICY_AUTHORITY_AND_EFFECTIVITY'),
}
NAMES = dict(zip(CRITERIA, ('Household Monthly Income', 'Socioeconomic Indicator', 'Employment Status',
                           'Previous Assistance Received', 'Number of Household Members')))
NAMES['SES'] = 'Socioeconomic Status (income-based proxy)'
# Options are supported proposals, not automatic policy adoption. Blank stays unspecified.
SPECS = {
    'weight_use': ('A', 'Weight reuse and precision', {'stored_vector': 'Reuse exact locked decimals, without rescaling; retain their recorded origin and rounding residue'}),
    'si_rubric': ('B', 'SI assessment rubric', {'barriers_v1': 'Essential-needs barriers: none=1, occasional=2, one recurrent domain=3, critical or two recurrent domains=4', si.METHOD: si.LABEL}),
    'si_occasional': ('B', 'Definition of occasional shortfall', None),
    'si_recurrent': ('B', 'Definition of recurrent shortfall', None),
    'si_critical': ('B', 'Definition of a current critical barrier', None),
    'si_authority': ('B', 'Authority to adopt SI and authorize assessors', None),
    'si_quality': ('B', 'Assessor qualifications, calibration, consistency checks and SI correction procedure', None),
    'method_rules': ('C', 'Document rules', {'dataset_v1': 'Full-Time Worker=1; Part-Time Worker=2; Seasonal Worker=3; Unemployed=4. Dataset Min-Max: HI/PA=(max-x)/(max-min); SI/ES/HM=(x-min)/(max-min). Sum exact weight times normalized value, then multiply by 100.'}),
    'input_domain': ('C', 'Accepted numerical domains', {'reviewed_values': 'HI: finite nonnegative reviewed monthly amounts; SI: supported levels 1-4; ES: one of the four disclosed categories; PA: nonnegative ledger count; HM: positive whole-person count. Invalid or unresolved values block calculation.'}),
    'income_sources': ('C', 'Income inclusions, exclusions, gross/net basis and ambiguous amounts', None),
    'income_months': ('C', 'Number of complete calendar months for HI', 'integer'),
    'income_period': ('C', 'HI assessment period', {'before_close': 'Complete calendar months immediately before the approved application-closing month'}),
    'si_period': ('C', 'SI assessment period', {'income_and_cutoff': 'HI assessment period plus current barriers at the bound evaluation cutoff'}),
    'current_period': ('C', 'ES and HM observation date', {'cutoff': 'The immutable program assessment cutoff'}),
    'household_definition': ('C', 'Household definition and treatment of ambiguous living arrangements', None),
    'unlisted_employment': ('C', 'Unlisted or mixed employment', {'block': 'Unresolved; block usable scoring until evidence or a new authorized policy resolves the category'}),
    'pa_scope': ('C', 'Previous-assistance scope', {'all_programs': 'Confirmed non-voided Association releases across programs', 'this_program': 'Confirmed non-voided releases from this program only'}),
    'pa_months': ('C', 'Previous-assistance window in calendar months', 'integer'),
    'pa_dates': ('C', 'Previous-assistance date boundaries', {'clamped_inclusive': 'Cutoff minus calendar months through cutoff, inclusive; clamp a missing day to month end'}),
    'pa_knowledge': ('C', 'Release recording time and retrospective entries', {'recorded_by_cutoff': 'Count only qualifying releases recorded at or before the bound cutoff. Later entries are outside that cutoff snapshot; changed release history invalidates current use and requires renewed coverage review.'}),
    'pa_units': ('C', 'Release counting unit', {'existing_unique_release': 'Existing one successful release per application; exclude voids, applications, undelivered selections, referrals and attendance'}),
    'pa_history': ('C', 'Incomplete history and zero counts', {'verified_coverage': 'Require verified supporting evidence of complete coverage; unknown history is not zero'}),
    'history_coverage': ('C', 'Evidence establishing complete PA coverage, justified zero, legacy imports and external assistance', None),
    'pa_record_rules': ('C', 'Release units, installments, duplicate records and reconciliation with the one-release-per-application ledger', None),
    'evidence_rule': ('C', 'Accepted evidence', {'verified_documents': 'Current verified supporting documents of the selected types, including any authorized documented accessible alternative; notes alone are insufficient'}),
    'evidence_procedure': ('C', 'Evidence acceptance, rejection, dispute resolution, unavailable evidence and authorized accessible alternatives', None),
    'evidence_authority': ('C', 'Authority and qualifications for evidence verification and numerical-input acceptance', None),
    'evidence_max_age_days': ('C', 'Maximum supporting-review age at acceptance and use, in days', 'integer'),
    'missing_rule': ('C', 'Missing, stale, disputed or invalid inputs', {'block': 'Block the complete-pool calculation; do not impute values or silently remove the applicant'}),
    'constant_rule': ('C', 'Constant-value columns and single-person pools', {'block': 'Stop calculation with no score, imputation or weight redistribution'}),
    'ranking_rule': ('C', 'Internal ranking and precision', {'competition_exact': 'Descending exact rational scores; competition ranks 1,2,2,4; half-even two-decimal display only'}),
    'tie_rule': ('C', 'Capacity-boundary ties', {'hold_boundary': 'Hold selection decisions at the capacity boundary', 'reasoned_human': 'Authorized human decision within slots, with a recorded tie explanation'}),
    'tie_procedure': ('C', 'Authorized tie procedure', None),
    'classification_rule': ('C', 'Need classifications', {'none': 'Omit classifications; do not activate example bands'}),
    'correction_rule': ('C', 'Evidence changes and corrections', {'reassess_recalculate': 'Invalidate current use, reassess accepted evidence, recalculate the complete pool and retain all prior runs'}),
    'correction_procedure': ('C', 'Late corrections and treatment of already selected, published or released cases', None),
    'pool_rule': ('C', 'Complete eligible pool', {'closed_complete': 'After approved closing and cutoff, resolve every application; retain verified ineligible outcomes outside the scored pool'}),
    'authority_reference': ('C', 'Policy approval authority and scope reference', None),
    'applicable_scope': ('C', 'Programs and circumstances to which this policy applies', None),
    'effective_from': ('C', 'Policy effective from, with timezone', 'datetime'),
    'effective_until': ('C', 'Policy effective until, with timezone', 'datetime'),
}
for _code in CRITERIA:
    SPECS[f'evidence_{_code}'] = ('C', f'{_code}: authorized supporting document types', 'documents')

# Append choices so the retained historical proposal text remains byte-for-byte
# compatible with policies already saved under the earlier contract.
SPECS['input_domain'][2]['document_values'] = (
    'HI: finite nonnegative reviewed monthly amounts; SI: 0, 2.5 or 5 from reviewed 4Ps and indigency findings; '
    'ES: the four document categories; PA: nonnegative ledger count; HM: positive whole-person count. '
    'Invalid or unresolved values block calculation.')


def applicable(content, key, *, specs=None):
    from .member_record_evidence import enabled
    from .automatic_inputs import enabled as automatic
    if automatic(content) and key in ('income_months', 'evidence_max_age_days'):
        return False
    if (enabled(content) or automatic(content)) and key in {'evidence_' + code for code in methods.criteria(content)}:
        return False
    if methods.is_ses(content):
        return key in (specifications(content) if specs is None else specs)
    return not (content['choices']['si_rubric']['value'] == si.METHOD and key in si.LEGACY_DEFINITIONS)


def specifications(content):
    if methods.is_composite(content):
        from .composite_ses_policy import specifications as composite_specs
        return composite_specs(SPECS)
    if methods.is_ses(content):
        from .ses_policy import specifications as ses_specs
        return ses_specs(SPECS)
    return SPECS


def decisions(content):
    return content['decision_groups']


def document_content(content=None, *, method=METHOD):
    if method in methods.SES_METHODS:
        return deepcopy(content) if content and content.get('method') == method else initial_content(method)
    result = deepcopy(content) if content is not None and not methods.is_ses(content) else initial_content()
    for key, value in {'si_rubric': si.METHOD, 'input_domain': 'document_values',
                       'method_rules': 'dataset_v1', 'constant_rule': 'block'}.items():
        result['choices'][key] = {'value': value, 'specified': True}
    for key in si.LEGACY_DEFINITIONS:
        result['choices'][key] = {'value': '', 'specified': False}
    return result


def initial_content(method=METHOD):
    if method == methods.COMPOSITE:
        from .composite_ses_policy import initial_content as composite_content
        return composite_content(SPECS)
    if method == methods.SES:
        from .ses_policy import initial_content as ses_content
        return ses_content(SPECS)
    if method != METHOD:
        raise ValidationError('Unsupported dataset method.')
    draft = load_draft().data
    choices = {key: {'value': '', 'specified': False} for key in SPECS}
    # Proposals remain unselected. No missing operational policy is silently filled.
    proposals = {key: next(iter(options.values())) if isinstance(options, dict) else 'Unspecified'
                 for key, (_, _, options) in SPECS.items()}
    proposals.update(si_occasional='Unspecified: define occasional shortfall for the adopted assessment period.',
        si_recurrent='Unspecified: define recurrent shortfall for the adopted assessment period.',
        si_critical='Unspecified: define a current critical unmet barrier.',
        income_months='3 (proposal)', pa_months='12 (proposal)',
        household_definition=draft['proposals']['household_definition']['description'],
        income_sources='Unspecified: decide gross/net basis, wages, self-employment, irregular work, pensions, remittances, benefits, one-off transfers, in-kind income, exclusions, duplicate counting and zero/negative adjustments.')
    return {'method': METHOD, 'choices': choices, 'proposals': proposals, 'evidence_catalog': {},
            'si_proposal': deepcopy(draft['proposals']['si_rubric']), 'decision_groups': deepcopy(DECISIONS)}


def evidence_catalog(content):
    from documents.models import DocumentType
    identifiers = set()
    specs = specifications(content)
    for key, (_, _, kind) in specs.items():
        if not applicable(content, key, specs=specs):
            continue
        value = content['choices'][key]['value']
        if kind == 'documents' and isinstance(value, list):
            identifiers.update(item for item in value if type(item) is int)
    return {str(row.pk): {'name': row.name, 'description': row.description}
            for row in DocumentType.objects.filter(pk__in=identifiers)}


def validate_weight_total(weights, *, direct=False):
    """Retained one-sided storage contract; never repair/rescale coefficients."""
    if any(not isinstance(value, str) for value in weights.values()):
        raise ValidationError('Retain the exact stored decimal weight strings.')
    try:
        values = [Fraction(value) for value in weights.values()]
        total = sum(values)
        precision_residue = sum(Fraction(1, 10 ** len(value.partition('.')[2])) for value in weights.values())
        invalid = any(value < 0 or value > 1 for value in values) if direct else any(value <= 0 or value > 1 for value in values)
        if invalid or total > 1 or 1 - total > precision_residue:
            raise ValueError
    except (ValueError, ZeroDivisionError):
        raise ValidationError('The stored vector is not usable without a separately authorized precision correction.') from None
    return total


def weight_snapshot(row, method=METHOD):
    from ewaf.vault_policy import source_policy
    row.clean()
    weight_method = methods.method_of(row.policy)
    expected_source = source_policy(weight_method)
    codes = methods.criteria(method)
    if (row.status != 'LOCKED' or row.policy.get('source_contract') != expected_source['source_contract']
            or weight_method not in methods.compatible_weight_methods(method)):
        raise ValidationError('Select a compatible, approved and locked ' + '/'.join(codes) + ' weight version.')
    if set(row.validation.get('weights', {})) != set(codes):
        raise ValidationError('Historical criterion codes cannot be relabeled for the new method.')
    # Require the explicit method's source definitions, not merely its length.
    # Historical SI (income/4Ps points) must never be relabeled as SES.
    if row.policy.get('criteria') != expected_source['criteria']:
        raise ValidationError('The stored criterion definitions need a separate compatibility review; no relabeling is allowed.')
    weights = row.validation['weights']
    from ewaf.vault_weights import is_direct
    total = validate_weight_total(weights, direct=is_direct(row.policy))
    names = {code: NAMES[code] for code in codes}
    return {'id': row.pk, 'digest': row.digest, 'weights': deepcopy(weights), 'names': names,
            'criteria': deepcopy(row.policy['criteria']), 'origin': deepcopy(row.policy.get('weight_input')),
            'approval_actor_id': row.actor_id, 'approved_at': row.recorded_at.isoformat(),
            'exact_total': str(total), 'residue_from_one': str(total - 1)}


def structural(content):
    if (not isinstance(content, dict) or content.get('method') not in methods.SIGNATURES
            or set(content.get('choices', {})) != set(specifications(content)) or len(str(content)) > 100000):
        raise ValidationError('Use the complete dataset-policy draft with all three decision groups.')
    reference = initial_content(content['method'])
    for key in ('proposals', 'ses_definition' if methods.is_ses(content) else 'si_proposal', 'decision_groups'):
        from ewaf.evidence import canonical
        if canonical(content.get(key)) != canonical(reference[key]):
            raise ValidationError('Retain the disclosed proposal text and unresolved-decision mapping; specify decisions in the explicit choice fields.')
    for entry in content['choices'].values():
        if not isinstance(entry, dict) or set(entry) != {'value', 'specified'} or type(entry['specified']) is not bool:
            raise ValidationError('Each policy choice needs its value and explicit review state.')
    from .shared_application import structural as shared_structure
    shared_structure(content)
    from ewaf.shared_calculation_rules import structural as calculation_structure
    calculation_structure(content)
    from . import automatic_inputs
    if automatic_inputs.enabled(content):
        automatic_inputs.validate_mapping(content, complete=False)


def findings(content, weight=None, *, live=True):
    structural(content)
    from .shared_application import findings as shared_findings
    errors = shared_findings(content)
    from . import automatic_inputs
    from . import rolling_pool
    selected = {key: entry['value'] for key, entry in content['choices'].items()}
    if selected.get('pool_rule') == rolling_pool.RULE and not automatic_inputs.enabled(content):
        errors.append('C: ranking during registration requires automatic current member-record inputs.')
    if (selected.get('constant_rule') == rolling_pool.ZERO_CONSTANTS) != (selected.get('method_rules') == rolling_pool.ZERO_METHOD):
        errors.append('C: explicitly approve both the zero-contribution constant rule and its matching calculation method.')
    from ewaf.shared_calculation_rules import FULL_CONSTANTS, FULL_METHOD
    if (selected.get('constant_rule') == FULL_CONSTANTS) != (selected.get('method_rules') == FULL_METHOD):
        errors.append('C: explicitly approve both the full-contribution constant rule and its matching calculation method.')
    if automatic_inputs.enabled(content):
        try:
            automatic_inputs.validate_mapping(content)
        except ValidationError as error:
            errors.extend(error.messages)
        required = {'income_period': 'current_record', 'current_period': 'current_record',
                    'four_ps_period': 'current_record', 'pa_history': 'association_ledger'}
        if any(content['choices'][key]['value'] != value for key, value in required.items()):
            errors.append('C: automatic member inputs require current-record income, employment, household and 4Ps sources and the Association ledger.')
    elif methods.is_composite(content) and any(
            content['choices'][key]['value'] == 'current_record'
            for key in ('income_period', 'current_period', 'four_ps_period')):
        errors.append('C: current-record periods require the automatic member-input source.')
    if weight is None:
        errors.append('A: select a compatible approved locked weight version.')
    specs = specifications(content)
    for key, (group, label, kind) in specs.items():
        if not applicable(content, key, specs=specs):
            continue
        entry = content['choices'][key]
        value = entry['value']
        if not entry['specified'] or value in ('', None, []):
            errors.append(f'{group}: {label} is unspecified or not reviewed.')
            continue
        valid = isinstance(value, str) and bool(value.strip()) and len(value) <= 4000
        if isinstance(kind, dict):
            valid = isinstance(value, str) and value in kind
        elif kind == 'integer':
            valid = type(value) is int and 1 <= value <= (3660 if key == 'evidence_max_age_days' else 120)
        elif kind == 'datetime':
            try:
                parsed = parse_datetime(value)
                valid = bool(parsed and parsed.tzinfo)
            except (ValueError, TypeError):
                valid = False
        elif kind == 'documents':
            from documents.models import DocumentType
            valid = (isinstance(value, list) and bool(value) and all(type(item) is int for item in value)
                     and len(set(value)) == len(value)
                     and (not live or DocumentType.objects.filter(pk__in=value).count() == len(value)))
        if not valid:
            errors.append(f'{group}: {label} is invalid or unsupported.')
    if (not methods.is_ses(content) and content['choices']['si_rubric']['value'] == si.METHOD
            and content['choices']['input_domain']['value'] != 'document_values'):
        errors.append('B: the 4Ps/indigency rubric requires the SI values 0, 2.5 and 5.')
    if not errors:
        values = {key: item['value'] for key, item in content['choices'].items()}
        if parse_datetime(values['effective_from']) >= parse_datetime(values['effective_until']):
            errors.append('C: the policy effective end must follow its start.')
        if live and content.get('evidence_catalog') != evidence_catalog(content):
            errors.append('C: supporting document definitions changed. Save and review a new policy version.')
    return errors


def values(content):
    return {key: entry['value'] for key, entry in content['choices'].items()}


def configuration_policy(policy):
    result = values(policy.content)
    result.update(method=policy.method, criteria={code: {'measure': NAMES[code], 'direction': direction}
        for code, direction in zip(methods.criteria(policy.method), methods.directions(policy.method))}, shared_policy_digest=policy.digest,
        selection_rule='reasoned_human_within_slots', classification_mode='none')
    if methods.is_composite(result):
        from .composite_ses import FORMULA
        result['ses_formula'] = deepcopy(FORMULA)
        result['criteria']['SES']['measure'] = 'Income-based SES with a verified 4Ps adjustment'
    if 'program_application' in policy.content:
        result['program_application'] = deepcopy(policy.content['program_application'])
    if 'registration_inputs' in policy.content:
        result['registration_inputs'] = deepcopy(policy.content['registration_inputs'])
    return result
