from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from core.permissions import require_workspace_permissions
from ewaf.member_invalidation import member_writer
from .forms import MEMBER_STATUSES
from .registration_form import member_edit_form, MemberRegistrationForm
from .models import Member, MemberEvent
from .profile import profile_snapshot
from documents.capture import cleanup_uploads, save_uploads


def record_event(member, user, action, notes, changes=None, address=None):
    return MemberEvent.objects.create(member=member, actor=user, actor_label=user.get_username(),
        action=action, notes=notes, changes=changes or {}, address=address or None)


def locked_member(pk, version):
    member = Member.objects.select_for_update().get(pk=pk)
    if member.version != version:
        raise ValidationError('Another administrator changed this member. Reload the page before continuing.')
    return member


def fill_application_email(member, *, email, reference):
    """Fill only an empty contact under the verified submission's member lock.

    The caller owns the transaction and has revalidated the membership grant
    and application form. The original onsite declaration stays unchanged.
    """
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError('Application email must commit with the verified submission.')
    if member.email.strip():
        return
    from django.core.validators import validate_email
    validate_email(email)
    previous = member.email
    member.email = email
    member.version += 1
    member.save(update_fields=['email', 'version', 'updated_at'])
    MemberEvent.objects.create(member=member, actor=None, actor_label='Verified program applicant',
        action='email_added_from_application',
        notes=f'Filled the empty member email from verified program application {reference}.',
        changes={'email': {'before': previous, 'after': email}})


@cleanup_uploads
@member_writer('profile')
def update_member(pk, *, user, version, data, notes, address=None, files=None):
    require_workspace_permissions(user, 'members.view_member', 'members.change_member')
    try:
        with transaction.atomic():
            member = locked_member(pk, version)
            if member.archived_at:
                raise ValidationError('Restore this archived member before editing their profile.')
            before = profile_snapshot(member)
            submitted = data.copy()
            submitted['version'], submitted['notes'] = version, notes
            form = member_edit_form(submitted, files=files, instance=member)
            if not form.is_valid():
                raise ValidationError([str(message) for errors in form.errors.values() for message in errors])
            classifications = (form.apply_to_member() if isinstance(form, MemberRegistrationForm)
                               else form.cleaned_data['disability_types'])
            if isinstance(form, MemberRegistrationForm) and (profile_snapshot(member) != before or files):
                member.registration_profile = {**member.registration_profile, 'update_acknowledgement': {
                    'confirmed': form.cleaned_data['acknowledgement'], 'recorded_at': timezone.now().isoformat()}}
            member.version += 1
            member.save()
            member.disability_types.set(classifications)
            if isinstance(form, MemberRegistrationForm):
                from .document_services import save_member_uploads
                save_member_uploads(form, member, user)
            else:
                save_uploads(form, member.application)
            if isinstance(form, MemberRegistrationForm):
                # Audit the persisted JSON ordering and decimal precision, matching
                # the enclosing source-writer's independent database snapshot.
                member.refresh_from_db()
            after = profile_snapshot(member)
            changes = {name: {'before': value, 'after': after[name]}
                       for name, value in before.items() if value != after[name]}
            if not changes:
                raise ValidationError('No profile changes were made.')
            record_event(member, user, 'profile_updated', form.cleaned_data['notes'], changes, address)
            return member
    except IntegrityError as error:
        if error.args[0] != 1062:
            raise
        raise ValidationError('A member with this control number already exists.') from error


@member_writer('status')
@transaction.atomic
def change_status(pk, *, user, version, status, notes, address=None):
    require_workspace_permissions(user, 'members.view_member', 'members.change_member_status')
    member = locked_member(pk, version)
    if status not in dict(MEMBER_STATUSES) or not notes.strip() or len(notes) > 2000:
        raise ValidationError('Select a valid status and provide a reason (up to 2,000 characters).')
    previous = member.status
    if status == previous:
        raise ValidationError('Select a different status.')
    member.is_active = status == 'active'
    member.archived_at = timezone.now() if status == 'archived' else None
    member.version += 1
    member.save()
    record_event(member, user, 'status_changed', notes.strip(),
                 {'status': {'before': previous, 'after': status}}, address)
    return member


@member_writer('profile')
@transaction.atomic
def repair_disability_link(pk, *, user, version, notes, address=None):
    """Audit a missing link for an unchanged, exact Association declaration."""
    from membership.pdf_registration_forms import ASSOCIATION_PDF_KIND
    from .disability_catalog import ASSOCIATION_LABELS, association_types
    require_workspace_permissions(user, 'members.view_member', 'members.change_member')
    member = locked_member(pk, version)
    if member.archived_at or not member.is_active or member.application.status != 'approved':
        raise ValidationError('Only an active approved member can have this classification link repaired.')
    if not notes.strip() or len(notes) > 2000:
        raise ValidationError('Provide a reason for the classification correction (up to 2,000 characters).')
    profile = member.registration_profile
    label = profile.get('disability_type', '')
    if (member.disability_ids or profile.get('profile_kind') != ASSOCIATION_PDF_KIND
            or label not in ASSOCIATION_LABELS.values() or label != member.disability_information):
        raise ValidationError('Review this member manually; this correction only fills a missing exact classification link.')
    classifications = list(association_types(label))
    if len(classifications) != 1:
        raise ValidationError('The recorded classification must have one active catalog entry.')
    before = profile_snapshot(member)
    member.disability_types.set(classifications)
    member.version += 1
    member.save(update_fields=['version', 'updated_at'])
    after = profile_snapshot(member)
    changes = {name: {'before': value, 'after': after[name]}
               for name, value in before.items() if value != after[name]}
    record_event(member, user, 'profile_updated', notes.strip(), changes, address)
    return member
