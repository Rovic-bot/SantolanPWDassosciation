"""Four-criterion configuration persistence using existing protected envelopes."""
from django.core.exceptions import PermissionDenied, ValidationError
from core.permissions import require_workspace_permissions
from . import four_policy as four, configuration_services as configurations, scoring_services as scoring
from .evidence import digest
from .evidence_services import reasoned
from .models import EvidencePolicyRevision, ConfigurationRevision, ConfigurationValidation, ScoringPolicyRevision
from .shared_invalidation import source_fence, finish, audit_history, audit_delta


def record_configuration(program_id, *, user, expected, expected_context, judgments, proposed, reason):
    from accounts.authority_services import enlisted
    from programs.models import Program, ProgramLog
    if not enlisted():
        raise PermissionDenied('Verified disposable session required.')
    with source_fence(user, expected, lambda: [Program.objects.get(pk=program_id).pk]) as (actor, authority, states):
        require_workspace_permissions(actor, *configurations.VIEW, 'ewaf.record_configurationrevision',
            'ewaf.record_configurationvalidation', 'ewaf.record_scoringpolicyrevision')
        program = states[0].program
        context = configurations.configuration_context(program)
        if digest(context) != expected_context:
            raise ValidationError('FOUR_CONFIGURATION_CONTEXT_CHANGED')
        four.proposal(proposed)
        result = four.ahp(judgments)
        if result['reference_consistency'] != 'PASSED':
            raise ValidationError('FOUR_CONSISTENCY_NOT_PASSED')
        source = context['source']
        policy = EvidencePolicyRevision.objects.get(pk=source['policy'], program=program)
        policy.clean()
        rubric = policy.snapshot['criteria']['PR'].get('rubric_definition') or {}
        items = {item['id']: item for item in rubric.get('items', [])}
        for rule in proposed['eligibility'].values():
            if rule['item'] not in items or rule['accepted_outcome'] not in items[rule['item']]['outcomes']:
                raise ValidationError('FOUR_FUNCTIONAL_NEED_RUBRIC_REQUIRED')
        fields = reasoned(actor, reason, True)
        before = audit_history(ProgramLog)
        configuration = configurations.persist(ConfigurationRevision(program=program,
            **configurations.predecessor(ConfigurationRevision, program=program), criteria_order=list(four.CRITERIA),
            judgments=judgments, canonical_judgments=result['pairs'], method=four.METHOD, profile=four.PROFILE,
            policy=policy, policy_digest=policy.digest, terms_revision_id=source['approval']['terms_revision'],
            terms_digest=source['approval']['terms_digest'], source_context=source, **fields))
        validation = configurations.persist(ConfigurationValidation(program=program, revision=1,
            configuration=configuration, configuration_digest=configuration.digest,
            engine=four.ENGINE, profile=four.PROFILE, result=result, **fields))
        proposal = scoring.persist(ScoringPolicyRevision(program=program,
            **configurations.predecessor(ScoringPolicyRevision, program=program), criteria_order=list(four.CRITERIA),
            proposal=proposed, engine=four.ENGINE, profile=four.PROFILE,
            evidence_policy=policy, evidence_policy_digest=policy.digest,
            configuration=configuration, configuration_digest=configuration.digest,
            validation=validation, validation_digest=validation.digest,
            terms_revision_id=source['approval']['terms_revision'], terms_revision_digest=source['approval']['terms_digest'],
            source_context=configurations.configuration_context(program), **fields))
        audits = audit_delta(ProgramLog, before)
        if {row.pk for row in audits} != {row.audit_entry_id for row in (configuration, validation, proposal)} or len(audits) != 3:
            raise ValidationError('FOUR_CONFIGURATION_AUDIT_SCOPE_INVALID')
        finish(states, authority, expected, actor=actor, kind='four_configuration', source_id=proposal.pk, audits=audits)
        for row in (configuration, validation, proposal):
            row.clean()
        return proposal
