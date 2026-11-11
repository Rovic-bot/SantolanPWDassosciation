"""Versioned member-record review without an extra ranking document upload."""
from copy import deepcopy

from django.core.exceptions import ValidationError

from ewaf import dataset_methods as methods
from ewaf.evidence import digest

RULE = 'association_records_v1'
LABEL = 'Review Association member records and the assistance ledger; uploads are required only by the program requirements'


def enabled(policy):
    value = policy.get('choices', {}).get('evidence_rule', {}).get('value', policy.get('evidence_rule'))
    return methods.is_composite(policy) and value == RULE


def content_for_records(content):
    """Prepare a new policy revision; never modify the retained policy."""
    if not methods.is_composite(content):
        raise ValidationError('Member-record review requires the composite SES method.')
    result = deepcopy(content)
    result['choices']['evidence_rule'] = {'value': RULE, 'specified': True}
    for code in methods.criteria(content):
        result['choices']['evidence_' + code] = {'value': [], 'specified': False}
    result['evidence_catalog'] = {}
    return result


def source_transition(before, after):
    from . import automatic_inputs
    return (methods.is_composite(before) and methods.is_composite(after)
            and ((enabled(after) and not enabled(before) and not automatic_inputs.enabled(before))
                 or (automatic_inputs.enabled(after) and not automatic_inputs.enabled(before))))


def permits_evidence_revision(program, previous, policy, cutoff):
    """Allow only the authorized evidence-source change before inputs or scoring."""
    if not (previous and previous.dataset_policy_id and source_transition(previous.policy, policy.content)):
        return False
    from .live_models import DatasetInputReview
    from ewaf.operational_models import OperationalRun
    if (program.status not in ('draft', 'published')
            or OperationalRun.objects.filter(program=program).exists()
            or DatasetInputReview.objects.filter(program=program, state='ACCEPTED').exists()):
        raise ValidationError('Programs with accepted inputs or calculations retain their existing evidence rules.')
    if cutoff != previous.assessment_cutoff or policy.weight_snapshot != previous.dataset_policy.weight_snapshot:
        raise ValidationError('An evidence-source revision must preserve the exact weights and assessment cutoff.')
    if not same_assessment_rules(previous.dataset_policy.content, policy.content):
        raise ValidationError('Only evidence-source rules may change; preserve all calculation rules, periods and scope.')
    return True


def same_assessment_rules(before, after):
    old = deepcopy(before)
    new = deepcopy(after)
    allowed = {'evidence_rule', 'evidence_procedure', 'evidence_authority', 'history_coverage',
               'four_ps_evidence_procedure', 'four_ps_procedure'} | {'evidence_' + code for code in methods.criteria(old)}
    from . import automatic_inputs
    if automatic_inputs.enabled(after):
        allowed |= {'income_period', 'current_period', 'four_ps_period', 'pa_history',
                    'income_months', 'evidence_max_age_days', 'income_sources', 'ses_review_procedure'}
        old.pop('registration_inputs', None)
        new.pop('registration_inputs', None)
    for value in (old, new):
        value.pop('evidence_catalog', None)
        for key in allowed:
            value['choices'].pop(key, None)
    return old == new


def preserves_information_review(previous, current):
    """An evidence-only revision does not undo a reviewed member correction."""
    from .rolling_pool import same_revision_rules
    ranking_revision = bool(previous and previous.dataset_policy_id and current.dataset_policy_id
        and same_revision_rules(previous.dataset_policy.content, current.dataset_policy.content))
    if not (previous and previous.dataset_policy_id and current.dataset_policy_id
            and current.previous_id == previous.pk and current.program_id == previous.program_id
            and (source_transition(previous.policy, current.policy) or ranking_revision)):
        return False
    previous.clean()
    current.clean()
    return (previous.source == current.source and previous.validation == current.validation
            and previous.assessment_cutoff == current.assessment_cutoff
            and previous.dataset_policy.weight_snapshot == current.dataset_policy.weight_snapshot
            and (same_assessment_rules(previous.dataset_policy.content, current.dataset_policy.content)
                 or ranking_revision))


def supporting(source, configuration):
    """Capture record provenance, without claiming a file was verified."""
    record = {'source_type': RULE, 'member': source['member'],
              'member_version': source['member_version'], 'profile_digest': source['profile_digest'],
              'application': source['application'], 'eligibility_digest': digest(source['case']),
              'configuration_digest': configuration.digest}
    return {code: [{**record, **({'ledger_digest': source['pa']['all_release_state_digest']}
                                if code == 'PA' else {})}]
            for code in methods.criteria(configuration.policy)}


def initial_values(member):
    """Prefill recorded facts; period-specific income and attestations stay blank."""
    from ewaf.employment_scoring import MAPPING, SCORES as ES
    employment = MAPPING.get(member.employment_status, '')
    participation = member.registration_profile.get('four_ps_member')
    return {'employment': employment if employment in ES else '',
            'household_members': member.household_members,
            'household_four_ps': str(participation).lower() if participation in ('Yes', 'No', 'yes', 'no') else ''}
