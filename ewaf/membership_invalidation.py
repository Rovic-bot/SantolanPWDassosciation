"""Onsite intake and manual review: audited zero-program source batches.

Pending intakes have no retained program applications. Approval creates a new
member; it cannot mutate an existing member or invent a program dependency.
"""
from contextvars import ContextVar
from functools import wraps
from inspect import signature

from django.core.exceptions import PermissionDenied, ValidationError

_uploads = ContextVar('membership_generation_uploads', default=None)


def remember_membership_upload(saved_file):
    journal = _uploads.get()
    if journal is not None:
        journal.append(saved_file)


def membership_writer(operation):
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
            from django.core.files.storage import FileSystemStorage
            from announcements.services import remove_file
            from membership.forms import requirements_snapshot, PROFILE_FIELDS
            from membership.models import MembershipApplication, MembershipEvent, MembershipSettings
            from members.models import Member
            from documents.models import MembershipApplicationDocument
            from .shared_invalidation import source_fence, finish, audit_history, audit_delta

            bound = spec.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            journal = []
            context = _uploads.set(journal)
            try:
                with source_fence(arguments['user'], expected, lambda: []) as (actor, authority, states):
                    arguments['user'] = actor
                    old = None
                    if operation != 'submit':
                        old = MembershipApplication.objects.get(reference=arguments['reference'])
                        if Member.objects.filter(application=old).exists():
                            # Existing finalized intakes are not an authorized correction path.
                            raise ValidationError('FINALIZED_MEMBERSHIP_SOURCE')
                    # Leaves are taken only after T/H and the (empty) program scope.
                    MembershipSettings.objects.select_for_update().get(pk=1)
                    if old:
                        old = MembershipApplication.objects.select_for_update().get(pk=old.pk)
                    else:
                        form = arguments['form']
                        if not form.is_valid() or form.snapshot != requirements_snapshot():
                            raise ValidationError('MEMBERSHIP_REQUIREMENTS_CHANGED')
                        old = MembershipApplication.objects.filter(
                            submission_key=form.cleaned_data['submission_token']).first()
                    storage = MembershipApplicationDocument._meta.get_field('file').storage
                    if storage.__class__ is not FileSystemStorage or storage._allow_overwrite:
                        raise ValidationError('NONOVERWRITING_LOCAL_STORAGE_REQUIRED')
                    history = audit_history(MembershipEvent)
                    before = dict(MembershipApplication.objects.filter(pk=old.pk).values().get()) if old else None
                    result = function(*bound.args, **bound.kwargs)
                    current = MembershipApplication.objects.get(pk=result.pk)
                    logs = audit_delta(MembershipEvent, history)
                    if operation == 'submit' and old:
                        if before != MembershipApplication.objects.filter(pk=old.pk).values().get() or logs:
                            raise ValidationError('DUPLICATE_MEMBERSHIP_CHANGED_SOURCE')
                        return result
                    combined = operation == 'approve_checked'
                    if old and (current.pk != old.pk or current.version != old.version + (2 if combined else 1)):
                        raise ValidationError('MEMBERSHIP_RESULT_VERSION')
                    if len(logs) != (2 if combined else 1):
                        raise ValidationError('MEMBERSHIP_NATIVE_AUDIT_SCOPE')
                    if operation == 'submit':
                        action, description = 'onsite_encoded', 'Onsite membership registration encoded for review.'
                        if current.status != 'pending' or current.prpwd_verified is not None:
                            raise ValidationError('MEMBERSHIP_SUBMISSION_RESULT')
                        if any(getattr(current, name) != form.cleaned_data[name] for name in PROFILE_FIELDS):
                            raise ValidationError('MEMBERSHIP_PROFILE_RESULT')
                        if current.disability_ids != sorted(item.pk for item in form.cleaned_data['disability_types']):
                            raise ValidationError('MEMBERSHIP_CLASSIFICATIONS_RESULT')
                        if current.requirements_snapshot != form.snapshot:
                            raise ValidationError('MEMBERSHIP_SNAPSHOT_RESULT')
                        for document in current.documents.all():
                            if not document.file.storage.exists(document.file.name):
                                raise ValidationError('MEMBERSHIP_EVIDENCE_MISSING')
                    elif operation == 'verify':
                        action = 'prpwd_verified' if arguments['verified'] else 'prpwd_not_verified'
                        description = 'Manual PRPWD verification recorded.'
                        if (current.prpwd_verified != arguments['verified'] or
                                current.prpwd_verified_by_id != actor.pk or not current.prpwd_verified_at or
                                current.verification_notes != arguments['notes'] or
                                current.verification_url != MembershipSettings.objects.get(pk=1).prpwd_url):
                            raise ValidationError('MEMBERSHIP_VERIFICATION_RESULT')
                    else:
                        if combined:
                            from membership.services import QUICK_VERIFICATION_NOTE, QUICK_APPROVAL_NOTE
                            if (arguments['verified'] is not True or current.prpwd_verified is not True or
                                    current.prpwd_verified_by_id != actor.pk or not current.prpwd_verified_at or
                                    current.verification_notes != QUICK_VERIFICATION_NOTE or
                                    current.verification_url != MembershipSettings.objects.get(pk=1).prpwd_url):
                                raise ValidationError('MEMBERSHIP_VERIFICATION_RESULT')
                        action = 'approved' if combined else arguments['decision']
                        description = f'Membership application {action}.'
                        if (current.status != action or current.decided_by_id != actor.pk or
                                not current.decided_at or current.decision_notes != (QUICK_APPROVAL_NOTE if combined else arguments['notes'])):
                            raise ValidationError('MEMBERSHIP_DECISION_RESULT')
                        member = Member.objects.filter(application=current).first()
                        if action == 'approved' and (not member or any(
                                getattr(member, name) != getattr(current, name) for name in PROFILE_FIELDS)):
                            raise ValidationError('MEMBERSHIP_APPROVAL_RESULT')
                        if action == 'approved' and member.disability_ids != current.disability_ids:
                            raise ValidationError('MEMBERSHIP_CLASSIFICATIONS_RESULT')
                        if action == 'rejected' and member:
                            raise ValidationError('MEMBERSHIP_REJECTION_RESULT')
                    log = logs[-1]
                    address = MembershipEvent._meta.get_field('address').get_prep_value(arguments['address'] or None)
                    if combined:
                        verification = logs[0]
                        if (verification.application_id, verification.actor_id, verification.actor_label,
                                verification.action, verification.description, verification.address) != (
                                current.pk, actor.pk, actor.get_username(), 'prpwd_verified',
                                'Manual PRPWD verification recorded.', address):
                            raise ValidationError('MEMBERSHIP_NATIVE_AUDIT_INVALID')
                    if (log.application_id, log.actor_id, log.actor_label, log.action, log.description, log.address) != (
                            current.pk, actor.pk, actor.get_username(), action, description, address):
                        raise ValidationError('MEMBERSHIP_NATIVE_AUDIT_INVALID')
                    finish(states, authority, expected, actor=actor, kind='membership', source_id=current.pk, audits=logs)
                    return result
            except Exception:
                for storage, name in journal:
                    remove_file(storage, name)
                raise
            finally:
                _uploads.reset(context)
        return wrapped
    return decorate
