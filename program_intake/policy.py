from copy import deepcopy
from django.core.exceptions import ValidationError
from core.permissions import require_workspace_permissions
from programs.terms import terms_lock
from programs.models import Program
from ewaf.evidence import VIEW, approval_context, digest
from ewaf.evidence_services import record_policy, reasoned
from ewaf.operational_services import latest_configuration, configuration_token, record_configuration
from .sources import CONTRACT


@terms_lock()
def authorize_sources(program_id, *, user, expected, requirement, measure, unit, lower, upper, direction,
                      observation_period, freshness_days, authority_reference, reason, confirmed):
    require_workspace_permissions(user, *VIEW, 'ewaf.authorize_operational', 'ewaf.record_evidencepolicyrevision')
    reasoned(user, reason, confirmed)
    program = Program.objects.select_for_update().get(pk=program_id)
    current = latest_configuration(program)
    if expected != configuration_token(program):
        raise ValidationError('The configuration changed. Reload before authorizing sources.')
    if not program.configured_requirements.filter(pk=requirement.pk, is_active=True, is_required=True, kind='document').exists():
        raise ValidationError('Configure a required socioeconomic document before publishing this program.')
    if current.policy['criteria']['ES']['source_type'] != 'employment_status' or current.policy['criteria']['ND']['source_type'] != 'dependent_count':
        raise ValidationError('Authorize an explicit onsite employment encoding and dependent-count definition in EWAF settings first.')
    if lower >= upper or direction not in ('benefit', 'inverse'):
        raise ValidationError('Use distinct authorized bounds and a supported direction.')
    evidence = deepcopy(current.evidence_policy.snapshot)
    evidence['criteria']['SI'] = {'definition': measure, 'source_types': ['socioeconomic_assessment'],
        'unit': unit, 'rule_authority': authority_reference, 'observation_rule': observation_period,
        'freshness_days': freshness_days}
    record_policy(program_id, user=user, snapshot=evidence, authority_reference=authority_reference,
        expected_revision=current.evidence_policy.revision,
        expected_context=digest({'program_version': program.version, 'approval': approval_context(program)}),
        reason=reason, confirmed=confirmed)
    policy = deepcopy(current.policy)
    policy.update(source_contract=CONTRACT, si_requirement=requirement.pk, authority_reference=authority_reference)
    policy['criteria']['SI'] = {'measure': measure, 'source_type': 'socioeconomic_assessment',
        'value_type': 'decimal', 'unit': unit, 'direction': direction, 'encoding': None,
        'bounds': {'method': 'fixed', 'lower': str(lower), 'upper': str(upper)},
        'observation_period': observation_period, 'edge_cases': 'block'}
    return record_configuration(program_id, user=user, expected=configuration_token(program), proposed=policy,
        judgments=current.judgments, status='LOCKED', reason=reason, attested=confirmed)
