"""Independent configuration diagnostics, never an acceptance token."""
from django.core.exceptions import ValidationError
from core.permissions import require_workspace_permissions
from programs.models import Program
from programs.approval_policy import binding_condition
from .models import ConfigurationRevision
from .configuration_services import VIEW, configuration_context

PENDING = ('SI_MEASUREMENT_POLICY_PENDING', 'ES_ENCODING_POLICY_PENDING', 'PA_SCOPE_POLICY_PENDING',
           'ND_INTERPRETATION_POLICY_PENDING', 'PR_ENCODING_POLICY_PENDING', 'NORMALIZATION_POLICY_PENDING',
           'CLASSIFICATION_POLICY_PENDING', 'AHP_JUDGMENTS_AUTHORIZATION_PENDING', 'TIES_EXCEPTIONS_POLICY_PENDING')


def configuration_diagnostics(program_id, *, user):
    require_workspace_permissions(user, *VIEW)
    program = Program.objects.get(pk=program_id)
    context = configuration_context(program)
    configuration = ConfigurationRevision.objects.filter(pk=context['configuration']).first()
    result = {'draft_recorded': bool(configuration), 'mathematically_complete': None,
              'structurally_valid': None, 'reference_consistency': 'UNAVAILABLE', 'review': 'PENDING',
              'authority_evidence': 'MISSING', 'effective_authorization': False, 'operational_ready': False,
              'context': context, 'reasons': [], 'validation': None}
    def add(code, source=None):
        result['reasons'].append({'code': code, 'source': source})
    if not configuration:
        add('CONFIGURATION_MISSING')
    else:
        stale = configuration.source_context != context['source']
        if stale:
            add('CONFIGURATION_STALE', configuration.pk)
        try:
            configuration.clean()
            if configuration.policy:
                configuration.policy.clean()
        except ValidationError:
            stale = True
            add('ARTIFACT_INTEGRITY_FAILED', configuration.pk)
        validation = configuration.validations.first()
        if validation:
            try:
                validation.clean()
                from .four_policy import PROFILE
                if validation.profile == PROFILE:
                    result.update(mathematically_complete=True, structurally_valid=True,
                        reference_consistency=validation.result['reference_consistency'], validation=validation.pk)
                    add('FOUR_FICTIONAL_POLICY_ONLY', validation.pk)
                else:
                    result.update(mathematically_complete=validation.result['complete'],
                        structurally_valid=validation.result['structurally_valid'],
                        reference_consistency=validation.result['consistency'], validation=validation.pk)
                    result['reasons'].extend(validation.result['reasons'])
            except ValidationError:
                stale = True
                add('ARTIFACT_INTEGRITY_FAILED', validation.pk)
        else:
            add('MATHEMATICAL_VALIDATION_MISSING', configuration.pk)
        for relation, key in (('reviews', 'review'), ('authority_evidence', 'authority_evidence')):
            record = getattr(configuration, relation).first()
            if record:
                try:
                    record.clean()
                    if stale or not validation or record.validation_id != validation.pk:
                        add('CONFIGURATION_REVIEW_STALE', record.pk)
                    else:
                        result[key] = record.finding if key == 'review' else 'RECORDED_NON_EFFECTIVE'
                except ValidationError:
                    add('ARTIFACT_INTEGRITY_FAILED', record.pk)
    authority = context['source']['approval']
    if not context['source']['policy']:
        add('EVIDENCE_POLICY_MISSING')
    if not program.ewaf_applicable:
        add('EWAF_NOT_APPLICABLE', str(program.pk))
    if not Program.objects.filter(pk=program.pk).filter(binding_condition()).exists():
        add('PROGRAM_TERMS_BINDING_UNRESOLVED', authority['binding'])
    if authority['terms_digest'] != authority['actual_terms_digest']:
        add('TERMS_CHANGED', authority['terms_revision'])
    for code in (*PENDING, 'CRITERION_POLICY_UNAPPROVED', 'CONFIGURATION_AUTHORIZATION_UNAVAILABLE',
                 'OPERATIONAL_SCORING_UNAVAILABLE', 'PROCESSING_GATE_UNAVAILABLE'):
        add(code)
    return result
