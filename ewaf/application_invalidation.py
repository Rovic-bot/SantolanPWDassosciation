"""Gate 2D-2A: two application writers in registered disposable sessions only.

Public submission retains the verified-member grant; no staff actor is invented.
The outer file journal also covers failures after the original writer returns.
"""
from contextvars import ContextVar
from functools import wraps
from inspect import signature

_files = ContextVar('generation_submission_files', default=None)


def submission_files():
    journal = _files.get()
    return journal if journal is not None else []


def _graph(program_id):
    from django.apps import apps
    result = {}
    for label, lookup in (
            ('programs.ProgramApplication', 'program_id'),
            ('programs.ProgramDocument', 'application__program_id'),
            ('programs.ApplicationPhoto', 'application__program_id'),
            ('programs.PhotoVerification', 'photo__application__program_id'),
            ('assistance.AssistanceCase', 'application__program_id')):
        result[label] = list(apps.get_model(label).objects.filter(
            **{lookup: program_id}).order_by('pk').values())
    return result


def _native(logs, assistance_logs, *, application, actor, submission, before, before_case):
    from django.core.exceptions import ValidationError
    from assistance.models import AssistanceCase
    from assistance.services import case_snapshot
    expected_action = 'submitted' if submission else 'application_updated'
    actor_id = None if submission else actor.pk
    actor_label = '' if submission else actor.get_username()
    expected_changes = {} if submission else {'status': {'before': before.status, 'after': 'CLOSED'}}
    if (len(logs) != 1 or logs[0].action != expected_action or
            logs[0].application_id != application.pk or logs[0].program_id != application.program_id or
            logs[0].actor_id != actor_id or logs[0].actor_label != actor_label or
            logs[0].changes != expected_changes):
        raise ValidationError('APPLICATION_NATIVE_AUDIT_OR_SCOPE_MISMATCH')
    if len(assistance_logs) != int(before_case is not None):
        raise ValidationError('APPLICATION_ASSISTANCE_AUDIT_SCOPE_MISMATCH')
    if before_case is not None:
        case = AssistanceCase.objects.get(application=application)
        log = assistance_logs[0]
        if (log.application_id != application.pk or log.actor_id != actor_id or
                log.actor_label != actor_label or log.action != 'application_cancelled' or
                log.snapshot != {'before': before_case, 'after': case_snapshot(case)} or
                case.eligibility_id != 'review' or case.decision != 'pending'):
            raise ValidationError('APPLICATION_ASSISTANCE_AUDIT_SCOPE_MISMATCH')


def application_writer(*, submission=False):
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
            from members.models import Member
            from programs.models import Program, ProgramApplication, ProgramLog
            from programs.terms import terms_lock
            from assistance.models import AssistanceCase, AssistanceLog, EligibilityStatus
            from assistance.services import case_snapshot
            from announcements.services import remove_file
            from . import generation_services as generation
            from .generation_models import ProgramSourceState
            from .generation_records import _owned_transaction
            from .source_invalidation import _actor, _authority_identity, _final_validate

            generation.durable_services._boundary()
            bound = spec.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            journal = []
            journal_token = _files.set(journal) if submission else None
            try:
                with terms_lock(), _owned_transaction():
                    authority = generation._authority()
                    # Resolve scope before any Program lock. Tokens never choose it.
                    program_id = (arguments['pk'] if submission else
                        ProgramApplication.objects.values_list('program_id', flat=True).get(pk=arguments['reference']))
                    program = Program.objects.select_for_update().get(pk=program_id)
                    if not isinstance(expected, dict) or set(expected) != {str(program.pk)}:
                        raise ValidationError('INCOMPLETE_SOURCE_SCOPE')
                    state = ProgramSourceState.objects.select_for_update().filter(program=program).first()
                    prior = expected[str(program.pk)]
                    generation._expect(state, authority, prior)
                    actor, identity, before_case = None, None, None
                    if submission:
                        from programs.services import require_open, grant_valid
                        require_open(program)
                        grant = arguments['grant']
                        if not grant_valid(grant, program):
                            raise ValidationError('Verification expired or the program changed. Verify your membership again.')
                        # Grant comes from the existing server-side verification flow.
                        before = ProgramApplication.objects.select_for_update().filter(
                            program=program, member_id=grant.get('member')).first()
                        member_id = grant.get('member')
                    else:
                        actor = _actor(arguments['user'])
                        identity = _authority_identity(actor)
                        arguments['user'] = actor
                        before = ProgramApplication.objects.select_for_update().get(
                            pk=arguments['reference'], program=program)
                        member_id = before.member_id
                    # No joined application/photo query: Application precedes Member.
                    list(Member.objects.select_for_update().filter(pk=member_id))
                    if not submission:
                        list(EligibilityStatus.objects.select_for_update().filter(pk='review'))
                        case = AssistanceCase.objects.select_for_update().filter(application=before).first()
                        before_case = case_snapshot(case) if case else None
                    before_graph = _graph(program.pk)
                    start = ProgramLog.objects.aggregate(value=Max('pk'))['value'] or 0
                    assistance_start = AssistanceLog.objects.aggregate(value=Max('pk'))['value'] or 0
                    result = function(*bound.args, **bound.kwargs)
                    if not enlisted() or (actor is not None and _authority_identity(_actor(actor)) != identity):
                        raise PermissionDenied('Application actor or disposable session changed.')
                    if (not isinstance(result, ProgramApplication) or result.program_id != program.pk or
                            result.member_id != member_id):
                        raise ValidationError('APPLICATION_RESULT_SCOPE_MISMATCH')
                    logs = list(ProgramLog.objects.filter(pk__gt=start).order_by('pk'))
                    assistance_logs = list(AssistanceLog.objects.filter(pk__gt=assistance_start).order_by('pk'))
                    after_graph = _graph(program.pk)
                    if submission and before is not None:
                        if result.pk != before.pk or before_graph != after_graph or logs or assistance_logs or journal:
                            raise ValidationError('DUPLICATE_APPLICATION_CHANGED')
                        generation._expect(state, generation._authority(), prior)
                        return result
                    pk_field = ProgramApplication._meta.pk.attname
                    old_ids = {row[pk_field] for row in before_graph['programs.ProgramApplication']}
                    new_ids = {row[pk_field] for row in after_graph['programs.ProgramApplication']}
                    if submission:
                        if result.pk in old_ids or new_ids != old_ids | {result.pk}:
                            raise ValidationError('APPLICATION_INVENTORY_MISMATCH')
                    elif (result.pk != before.pk or result.status != 'CLOSED' or
                          result.version != before.version + 1 or result.public_reference != before.public_reference or
                          new_ids != old_ids):
                        raise ValidationError('APPLICATION_CLOSURE_MISMATCH')
                    _native(logs, assistance_logs, application=result, actor=actor, submission=submission,
                            before=before, before_case=before_case)
                    generation._expect(state, generation._authority(), prior)
                    metadata = ({'actor': None, 'actor_label': 'Verified member application submission',
                        'system_code': 'VERIFIED_MEMBER_SUBMISSION', 'reason_code': 'APPLICATION_SUBMITTED',
                        'reason': 'Verified member submitted a retained application.'} if submission else
                        generation._metadata(actor, 'APPLICATION_CLOSED', 'Administrative application closure.'))
                    batch = generation._invalidate([state], metadata=metadata, kind='SOURCE_CHANGE',
                        source_kind='application', source_id=str(result.pk),
                        native_audits=[generation.native_reference(row) for row in logs + assistance_logs])
                    _final_validate(state, authority, prior, batch)
                    return result
            except Exception:
                # Original writer cleans failures inside its own try; this also
                # covers native-audit/invalidation/CAS/final-validation/commit failure.
                for storage, name in journal:
                    remove_file(storage, name)
                raise
            finally:
                if journal_token is not None:
                    _files.reset(journal_token)
        return wrapped
    return decorate
