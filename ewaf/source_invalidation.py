"""Gate 2D-1 single-program writers. No activation, promotion or operational API.

The decorator is OUTSIDE the existing Terms/atomic decorators. Imports are lazy
to preserve the existing program/EWAF module dependency graph and startup path.
"""
from functools import wraps
from inspect import signature


def _actor(user):
    from django.contrib.auth import get_user_model
    from django.core.exceptions import PermissionDenied
    current = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    if not current or not current.is_active or not current.is_staff:
        raise PermissionDenied('Current staff authority required.')
    return current


def _authority_identity(user):
    return (user.pk, user.get_username(), user.is_active, user.is_staff,
            user.is_superuser, frozenset(user.get_all_permissions()))


def _projection(program_id):
    """Private equality observation, never a replacement historical digest.

    Includes all selected writer families. Native ProgramLog additions are
    separately significant even if a retained record has identical values.
    """
    from django.apps import apps
    from programs.models import Program
    result = {'program': list(Program.objects.filter(pk=program_id).values())}
    for label in ('programs.ProgramRequirement', 'programs.PDAOApprovalRecord',
                  'programs.ProgramApprovalControl', 'programs.ProgramTermsRevision',
                  'programs.ProgramApprovalBinding', 'ewaf.EvidencePolicyRevision',
                  'ewaf.CriterionAssessment', 'ewaf.ConfigurationRevision',
                  'ewaf.ConfigurationValidation', 'ewaf.ConfigurationReview',
                  'ewaf.ConfigurationAuthorizationEvidence', 'ewaf.ScoringPolicyRevision'):
        result[label] = list(apps.get_model(label).objects.filter(program_id=program_id).order_by('pk').values())
    result['types'] = list(Program.eligible_disability_types.through.objects.filter(
        program_id=program_id).order_by('disabilitytype_id').values_list('disabilitytype_id', flat=True))
    return result


def _audit_actions(action, arguments, before, after):
    if action == 'program_save':
        actions = ['updated' if arguments.get('pk') else 'created']
        if (before or {}).get('types', []) != after['types']:
            actions.append('disability_types_configured')
        return actions
    if action == 'publication':
        requested = arguments['action']
        if requested == 'unpublish' or (requested == 'draft' and before['program'][0]['status'] == 'published'):
            requested = 'archived'
        return ['policy_authorized' if requested == 'authorize_policy' else requested]
    if action == 'requirement':
        return ['requirement_updated' if arguments.get('requirement_id') else 'requirement_added']
    return [action]


def _validate_native(logs, *, program_id, actor, actions, result):
    from django.core.exceptions import ValidationError
    if (sorted(row.action for row in logs) != sorted(actions) or
            any(row.program_id != program_id or row.actor_id != actor.pk for row in logs)):
        raise ValidationError('SOURCE_NATIVE_AUDIT_OR_SCOPE_MISMATCH')
    audit_id = getattr(result, 'audit_entry_id', None)
    if audit_id is not None and (len(logs) != 1 or logs[0].pk != audit_id):
        raise ValidationError('SOURCE_ARTIFACT_AUDIT_MISMATCH')


def _final_validate(state, authority, expected, batch):
    from django.core.exceptions import ValidationError
    from . import generation_services as generation
    current_authority = generation._authority()
    if current_authority.generation != authority.generation:
        raise ValidationError('SOURCE_AUTHORITY_CHANGED')
    generation._validate_batch(batch)
    state.refresh_from_db()
    generation._state(state)
    if (batch.scope_count != 1 or batch.scope_digest != generation._scope([state.program_id]) or
            state.generation != expected['source_generation'] + 1 or
            state.revision != expected['revision'] + 1 or state.last_invalidation.batch_id != batch.pk):
        raise ValidationError('SOURCE_FINAL_STATE_MISMATCH')


def source_writer(scope_argument, *, action, application_scope=False, control=False, creation=False):
    """Require source_expected only inside an already registered test session.

    Existing scope: {str(program_id): exact four-field foundation token}.
    Creation: {'authority_generation': expected_global_generation}; the new
    program is initialized with its native creation audit in the same transaction.
    Tokens are concurrency preconditions, never activation flags or chosen scope.
    """
    def decorate(function):
        spec = signature(function)

        @wraps(function)
        def wrapped(*args, **kwargs):
            from accounts.authority_services import enlisted
            from django.core.exceptions import PermissionDenied, ValidationError
            expected = kwargs.pop('source_expected', None)
            if not enlisted():
                if expected is not None:
                    raise PermissionDenied('Source tokens require a registered disposable session.')
                from programs.terms import terms_lock as operational_terms_lock
                with operational_terms_lock():
                    return function(*args, **kwargs)
            from django.db.models import Max
            from programs.models import Program, ProgramApplication, ProgramLog, ProgramApprovalControl
            from programs.terms import terms_lock
            from . import generation_services as generation
            from .generation_records import _owned_transaction, bounded
            from .generation_models import ProgramSourceState, SourceInvalidation

            generation.durable_services._boundary()
            bound = spec.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            with terms_lock(), _owned_transaction():
                authority = generation._authority()
                reference = arguments[scope_argument]
                new_program = creation and reference is None
                program_id = (ProgramApplication.objects.values_list('program_id', flat=True).get(pk=reference)
                              if application_scope else reference)
                actor = _actor(arguments['user'])
                authority_identity = _authority_identity(actor)
                arguments['user'] = actor
                if new_program:
                    if not isinstance(expected, dict) or set(expected) != {'authority_generation'}:
                        raise ValidationError('NEW_PROGRAM_AUTHORITY_TOKEN_REQUIRED')
                    bounded(expected['authority_generation'], positive=True)
                    if expected['authority_generation'] != authority.generation:
                        raise ValidationError('STALE_AUTHORITY_GENERATION')
                    state, before = None, None
                else:
                    # Resolve the complete (single-program) scope before any P lock.
                    program = Program.objects.select_for_update().get(pk=program_id)
                    program_id = program.pk
                    if not isinstance(expected, dict) or set(expected) != {str(program_id)}:
                        raise ValidationError('INCOMPLETE_SOURCE_SCOPE')
                    state = ProgramSourceState.objects.select_for_update().filter(program_id=program_id).first()
                    generation._expect(state, authority, expected[str(program_id)])
                    if control:
                        list(ProgramApprovalControl.objects.select_for_update().filter(program_id=program_id))
                    before = _projection(program_id)
                start = ProgramLog.objects.aggregate(value=Max('pk'))['value'] or 0
                result = function(*bound.args, **bound.kwargs)
                if not enlisted() or _authority_identity(_actor(actor)) != authority_identity:
                    raise PermissionDenied('Source actor or registered session changed.')
                if new_program:
                    if not isinstance(result, Program) or result._state.adding:
                        raise ValidationError('NEW_PROGRAM_RESULT_REQUIRED')
                    program_id = result.pk
                    if (ProgramSourceState.objects.filter(program_id=program_id).exists() or
                            SourceInvalidation.objects.filter(program_id=program_id).exists()):
                        raise ValidationError('NEW_PROGRAM_STATE_CONFLICT')
                after = _projection(program_id)
                logs = list(ProgramLog.objects.filter(pk__gt=start).order_by('pk'))
                if before == after and not logs:
                    generation._expect(state, generation._authority(), expected[str(program_id)])
                    return result
                _validate_native(logs, program_id=program_id, actor=actor,
                                 actions=_audit_actions(action, arguments, before, after), result=result)
                if new_program:
                    state = ProgramSourceState.objects.create(program_id=program_id)
                    prior = {'source_generation': 0, 'revision': 0}
                else:
                    prior = expected[str(program_id)]
                    generation._expect(state, generation._authority(), prior)
                batch = generation._invalidate([state],
                    metadata=generation._metadata(actor, 'SOURCE_WRITER', 'Explicit program or EWAF source mutation.'),
                    kind='INITIALIZE' if new_program else 'SOURCE_CHANGE', source_kind='program',
                    source_id=str(program_id), native_audits=[generation.native_reference(row) for row in logs])
                _final_validate(state, authority, prior, batch)
                return result
        return wrapped
    return decorate
