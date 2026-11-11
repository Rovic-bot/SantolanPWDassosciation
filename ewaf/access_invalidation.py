"""Private access audits remain conservative Gate 1 source dependencies.

The DB audit/invalidation commits before streaming. Delivery and filesystem
reads are not claimed atomic with MySQL; late failures close the response handle.
"""
from functools import wraps
from inspect import signature

from django.core.exceptions import PermissionDenied, ValidationError


def private_access_writer(action):
    def decorate(function):
        spec = signature(function)

        @wraps(function)
        def wrapped(*args, **kwargs):
            from accounts.authority_services import enlisted
            if not enlisted():
                from programs.terms import terms_lock as operational_terms_lock
                with operational_terms_lock():
                    return function(*args, **kwargs)
            from django.shortcuts import get_object_or_404
            from core.permissions import require_workspace_permissions
            from members.models import Member
            from programs.models import Program, ProgramApplication, ProgramLog
            from programs.terms import terms_lock
            from programs.workflow import PHOTO_VIEW
            from . import generation_services as generation
            from .generation_models import ProgramSourceState
            from .generation_records import _owned_transaction
            from .source_invalidation import _actor, _authority_identity
            from .shared_invalidation import audit_history, audit_delta, finish

            generation.durable_services._boundary()
            bound = spec.bind(*args, **kwargs)
            bound.apply_defaults()
            values = bound.arguments
            request = values['request']
            response = None
            try:
                with terms_lock(), _owned_transaction():
                    authority = generation._authority()
                    actor = _actor(request.user)
                    identity = _authority_identity(actor)
                    request.user = actor
                    require_workspace_permissions(actor, *(PHOTO_VIEW if action == 'photo_viewed' else
                        ('programs.view_program', 'programs.view_programapplication', 'programs.view_programdocument')))
                    if action == 'document_downloaded' and values.get('revision_id') is not None:
                        require_workspace_permissions(actor, 'programs.view_programdocumentrevision')
                    app = get_object_or_404(ProgramApplication, pk=values['reference'])
                    program = Program.objects.select_for_update().get(pk=app.program_id)
                    state = generation._state(ProgramSourceState.objects.select_for_update().filter(program=program).first())
                    expected = {str(program.pk): generation._token(state, authority)}
                    app = ProgramApplication.objects.select_for_update().get(pk=app.pk)
                    Member.objects.select_for_update().get(pk=app.member_id)
                    before = ProgramApplication.objects.filter(pk=app.pk).values().get()
                    history = audit_history(ProgramLog)
                    response = function(*bound.args, **bound.kwargs)
                    logs = audit_delta(ProgramLog, history)
                    if (len(logs) != 1 or response.status_code != 200 or
                            ProgramApplication.objects.filter(pk=app.pk).values().get() != before):
                        raise ValidationError('PRIVATE_ACCESS_NATIVE_SCOPE')
                    notes = ('Authorized private calendar-photo access.' if action == 'photo_viewed' else
                        f'Private program document downloaded: {values["document_id"]}; revision: {values["revision_id"] or "current"}.')
                    changes = {'photo': {'before': None, 'after': str(values['photo_id'])}} if action == 'photo_viewed' else {}
                    address = ProgramLog._meta.get_field('address').get_prep_value(request.META.get('REMOTE_ADDR') or None)
                    log = logs[0]
                    if (log.program_id, log.application_id, log.actor_id, log.actor_label, log.action,
                            log.notes, log.changes, log.address) != (program.pk, app.pk, actor.pk, actor.get_username(),
                            action, notes, changes, address):
                        raise ValidationError('PRIVATE_ACCESS_NATIVE_AUDIT_INVALID')
                    if not enlisted() or _authority_identity(_actor(actor)) != identity:
                        raise PermissionDenied('Private access authority changed.')
                    finish([state], authority, expected, actor=actor, kind='private_access', source_id=app.pk, audits=logs)
                    return response
            except Exception:
                if response is not None:
                    response.close()
                raise
        return wrapped
    return decorate


def membership_access_writer(*, intake=False, member_upload=False):
    def decorate(function):
        spec = signature(function)

        @wraps(function)
        def wrapped(*args, **kwargs):
            from accounts.authority_services import enlisted
            if not enlisted():
                from programs.terms import terms_lock as operational_terms_lock
                with operational_terms_lock():
                    return function(*args, **kwargs)
            from django.shortcuts import get_object_or_404
            from core.permissions import require_workspace_permissions
            from members.models import Member, MemberEvent
            from membership.models import MembershipApplication, MembershipEvent
            from membership.services import require_capability
            from documents.models import MembershipApplicationDocument
            from programs.models import Program, ProgramApplication
            from programs.terms import terms_lock
            from . import generation_services as generation
            from .generation_models import ProgramSourceState
            from .generation_records import _owned_transaction
            from .source_invalidation import _actor, _authority_identity
            from .shared_invalidation import audit_history, audit_delta, finish
            from .member_invalidation import member_programs

            generation.durable_services._boundary()
            bound = spec.bind(*args, **kwargs)
            bound.apply_defaults()
            values = bound.arguments
            request, response = values['request'], None
            try:
                with terms_lock(), _owned_transaction():
                    authority = generation._authority()
                    actor = _actor(request.user)
                    identity = _authority_identity(actor)
                    request.user = actor
                    if intake:
                        require_capability(actor, 'documents.view_membershipapplicationdocument')
                    else:
                        require_workspace_permissions(actor, 'members.view_member', 'documents.view_membershipapplicationdocument')
                    document_model = MembershipApplicationDocument
                    if member_upload:
                        from members.document_models import MemberDocumentUpload
                        document_model = MemberDocumentUpload
                    document = get_object_or_404(document_model, pk=values['document_id'])
                    member = Member.objects.filter(application_id=document.application_id).first()
                    if not intake and (not member or str(member.pk) != str(values['pk'])):
                        from django.http import Http404
                        raise Http404
                    ids = sorted(set(member_programs(member.pk))) if member else []
                    programs = [Program.objects.select_for_update().get(pk=pk) for pk in ids]
                    states = [generation._state(ProgramSourceState.objects.select_for_update().filter(program=p).first())
                              for p in programs]
                    expected = {str(s.program_id): generation._token(s, authority) for s in states}
                    if member:
                        list(ProgramApplication.objects.select_for_update().filter(member=member).order_by('pk'))
                        member = Member.objects.select_for_update().get(pk=member.pk)
                    MembershipApplication.objects.select_for_update().get(pk=document.application_id)
                    document_model.objects.select_for_update().get(pk=document.pk)
                    model = MembershipEvent if intake else MemberEvent
                    history = audit_history(model)
                    response = function(*bound.args, **bound.kwargs)
                    logs = audit_delta(model, history)
                    if len(logs) != 1 or response.status_code != 200:
                        raise ValidationError('MEMBERSHIP_ACCESS_NATIVE_SCOPE')
                    log = logs[0]
                    address = model._meta.get_field('address').get_prep_value(request.META.get('REMOTE_ADDR') or None)
                    if (log.actor_id, log.actor_label, log.action, log.address) != (
                            actor.pk, actor.get_username(), 'document_downloaded', address):
                        raise ValidationError('MEMBERSHIP_ACCESS_NATIVE_AUDIT_INVALID')
                    if intake:
                        valid = log.application_id == document.application_id and log.description == 'Private application document downloaded.'
                    else:
                        valid = log.member_id == member.pk and log.notes == 'Private membership document downloaded.' and log.changes == {}
                    if not valid or (member and sorted(set(member_programs(member.pk))) != ids):
                        raise ValidationError('MEMBERSHIP_ACCESS_NATIVE_AUDIT_INVALID')
                    if not enlisted() or _authority_identity(_actor(actor)) != identity:
                        raise PermissionDenied('Private membership access authority changed.')
                    finish(states, authority, expected, actor=actor, kind='private_membership_access',
                        source_id=document.pk, audits=logs)
                    return response
            except Exception:
                if response is not None:
                    response.close()
                raise
        return wrapped
    return decorate
