"""Complete retained-program fan-out for member and evidence review writers."""
from functools import wraps
from inspect import signature

from django.core.exceptions import PermissionDenied, ValidationError


def member_programs(member_id):
    from programs.models import ProgramApplication
    return list(ProgramApplication.objects.filter(member_id=member_id).values_list('program_id', flat=True).distinct())


def member_writer(operation):
    def decorate(function):
        spec = signature(function)

        @wraps(function)
        def wrapped(*args, **kwargs):
            from accounts.authority_services import enlisted
            expected = kwargs.pop('source_expected', None)
            if not enlisted():
                if expected is not None:
                    raise PermissionDenied('Source tokens require a registered disposable session.')
                from programs.terms import terms_lock as operational_terms_lock
                with operational_terms_lock():
                    return function(*args, **kwargs)
            from members.models import Member, MemberEvent
            from membership.forms import PROFILE_FIELDS
            from members.profile import profile_snapshot
            from documents.models import MembershipApplicationDocument, DocumentVerification
            from documents.services import file_digest
            from programs.models import ProgramApplication
            from .shared_invalidation import source_fence, finish, audit_history, audit_delta

            bound = spec.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            # Read-only scope discovery is repeated under T before any P lock.
            def member_id():
                if operation == 'document':
                    intake = MembershipApplicationDocument.objects.values_list('application_id', flat=True).get(
                        pk=arguments['document_id'])
                    return Member.objects.values_list('pk', flat=True).get(application_id=intake)
                return Member.objects.values_list('pk', flat=True).get(pk=arguments['pk'])
            resolve = lambda: member_programs(member_id())
            with source_fence(arguments['user'], expected, resolve) as (actor, authority, states):
                arguments['user'] = actor
                pk = member_id()
                list(ProgramApplication.objects.select_for_update().filter(member_id=pk).order_by('pk'))
                before = Member.objects.select_for_update().get(pk=pk)
                profile = profile_snapshot(before)
                old_row = Member.objects.filter(pk=pk).values().get()
                document = None
                if operation == 'document':
                    document = MembershipApplicationDocument.objects.select_for_update().get(pk=arguments['document_id'])
                    list(DocumentVerification.objects.select_for_update().filter(document=document).order_by('pk'))
                history = audit_history(MemberEvent)
                reviews = audit_history(DocumentVerification)
                result = function(*bound.args, **bound.kwargs)
                current = Member.objects.get(pk=pk)
                logs = audit_delta(MemberEvent, history)
                new_reviews = audit_delta(DocumentVerification, reviews)
                if len(logs) != 1:
                    raise ValidationError('MEMBER_NATIVE_AUDIT_SCOPE')
                if operation == 'document':
                    if Member.objects.filter(pk=pk).values().get() != old_row or len(new_reviews) != 1:
                        raise ValidationError('DOCUMENT_REVIEW_SCOPE')
                    review = new_reviews[0]
                    if (result.pk != review.pk or review.document_id != document.pk or
                            review.reviewer_id != actor.pk or review.reviewer_label != actor.get_username() or
                            review.member_version != before.version or review.verified != arguments['verified'] or
                            review.expires_on != arguments['expires_on'] or review.reason != arguments['reason'].strip() or
                            not review.file_digest or review.file_digest != file_digest(document)):
                        raise ValidationError('DOCUMENT_REVIEW_INVALID')
                    action = 'document_verified' if review.verified else 'document_verification_failed'
                    notes, address = arguments['reason'], None
                    changes = {'document': {'before': None, 'after': str(document.pk)},
                               'review': {'before': None, 'after': review.pk}}
                    audits = [*logs, review]
                else:
                    if result.pk != pk or current.version != before.version + 1 or new_reviews:
                        raise ValidationError('MEMBER_RESULT_SCOPE')
                    if operation == 'profile':
                        action, notes = 'profile_updated', arguments['notes'].strip()
                        after = profile_snapshot(current)
                        changes = {name: {'before': value, 'after': after[name]}
                                   for name, value in profile.items() if value != after[name]}
                        if not changes or current.status != before.status:
                            raise ValidationError('MEMBER_PROFILE_RESULT')
                    else:
                        action, notes = 'status_changed', arguments['notes'].strip()
                        changes = {'status': {'before': before.status, 'after': arguments['status']}}
                        if current.status != arguments['status'] or any(
                                profile_snapshot(current)[name] != value for name, value in profile.items()):
                            raise ValidationError('MEMBER_STATUS_RESULT')
                    address = MemberEvent._meta.get_field('address').get_prep_value(arguments['address'] or None)
                    audits = logs
                log = logs[0]
                if (log.member_id, log.actor_id, log.actor_label, log.action, log.notes, log.changes, log.address) != (
                        pk, actor.pk, actor.get_username(), action, notes, changes, address):
                    raise ValidationError('MEMBER_NATIVE_AUDIT_INVALID')
                finish(states, authority, expected, actor=actor, kind='member_document' if document else 'member',
                    source_id=document.pk if document else pk, audits=audits)
                return result
        return wrapped
    return decorate
