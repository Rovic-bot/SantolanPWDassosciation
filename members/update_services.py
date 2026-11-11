"""Verified member declarations, staff comparison, interview and accepted updates."""
from datetime import date, timedelta
from decimal import Decimal
from functools import partial
import secrets
from uuid import UUID

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import OperationalError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from accounts.backends import reserve_windows
from core.permissions import require_workspace_permissions
from events.services import normalize_name
from membership.pdf_registration_forms import AssociationPDFForm
from programs.terms import terms_lock
from .models import Member, MemberEvent
from .registration_form import MemberRegistrationForm
from .update_forms import PublicMemberUpdateForm
from .update_models import MemberUpdateWindow, MemberUpdateAccess, MemberUpdateRequest, MemberUpdateAction, update_write
from . import update_mail

SESSION_KEY = 'member_information_update'
CODE_LIFETIME = timedelta(minutes=10)
ACCESS_LIFETIME = timedelta(minutes=30)
FAILED = 'Unable to verify these details. Check your information or contact the Association Help Desk.'
EXPIRED = 'This verification expired or the member record changed. Verify your details again.'


def digest(kind, value):
    return salted_hmac('members.update.' + kind, str(value), algorithm='sha256').hexdigest()


def reserve_access(control_number, address):
    try:
        return reserve_windows({digest('number', control_number.strip().upper()): 5,
            digest('address', address): 25}, 3600, MemberUpdateWindow)
    except (OperationalError, MemberUpdateWindow.DoesNotExist):
        return False


def can_request(member):
    return bool(member and member.is_active and not member.archived_at and member.application.status == 'approved')


def requires_verification(member):
    return bool(member and MemberUpdateRequest.objects.filter(member=member, state='needs_verification').exists())


def pending_request(member):
    return MemberUpdateRequest.objects.filter(member=member, state__in=MemberUpdateRequest.OPEN_STATES).first()


@transaction.atomic
def start_access(*, nonce, control_number, full_name):
    member = Member.objects.select_related('application').filter(control_number=control_number.strip().upper()).first()
    matched = can_request(member) and normalize_name(member.full_name) == normalize_name(full_name)
    recipient = member.email.strip() if matched else ''
    try:
        validate_email(recipient)
    except ValidationError:
        matched = False
    # A decoy challenge gives unmatched details the same public response.
    code = f'{secrets.randbelow(1000000):06d}'
    with update_write():
        access = MemberUpdateAccess(id=UUID(bytes=secrets.token_bytes(16), version=4),
            member=member if matched else None, member_version=member.version if matched else None,
            session_digest=digest('session', nonce), recipient=recipient if matched else '',
            expires_at=timezone.now() + CODE_LIFETIME)
        access.code_digest = digest('code', f'{access.pk}:{code}')
        access.save()
        if matched:
            update_mail.queue_email(access=access, recipient=recipient,
                subject='Your member information verification code',
                body=f'Your verification code is {code}. It expires in 10 minutes.\n\n'
                     'Use it only on the Santolan PWD Association website to review your own member information. '
                     'Do not share this code. If you did not request it, you can ignore this message.')
    return access


def access_record(identifier, nonce, *, lock=False):
    try:
        rows = MemberUpdateAccess.objects.select_for_update() if lock else MemberUpdateAccess.objects
        access = rows.filter(pk=identifier).first()
    except (ValueError, TypeError, ValidationError):
        return None
    if not access or not constant_time_compare(access.session_digest, digest('session', nonce)):
        return None
    return access


@transaction.atomic
def verify_code(identifier, *, nonce, code):
    access = access_record(identifier, nonce, lock=True)
    now = timezone.now()
    if not access or access.verified_at or access.expires_at <= now or access.attempts >= 5:
        return False
    with update_write():
        access.attempts += 1
        access.save(update_fields=['attempts'])
        if (not constant_time_compare(access.code_digest, digest('code', f'{access.pk}:{code}'))
                or not can_request(access.member) or access.member.version != access.member_version
                or access.member.email.strip() != access.recipient):
            return False
        access.verified_at = now
        access.access_expires_at = now + ACCESS_LIFETIME
        access.save(update_fields=['verified_at', 'access_expires_at'])
    return True


def verified_access(identifier, nonce, *, allow_submitted=False):
    access = access_record(identifier, nonce)
    if not (access and access.verified_at and access.access_expires_at > timezone.now()
            and can_request(access.member)):
        raise ValidationError(EXPIRED)
    if access.submitted_at and allow_submitted:
        return access
    if access.submitted_at or access.member.version != access.member_version or access.member.email.strip() != access.recipient:
        raise ValidationError(EXPIRED)
    return access


def scalar(value):
    if value is None:
        return ''
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, 'f')
    return str(value)


def initial_values(member):
    form = MemberRegistrationForm(instance=member)
    return {name: scalar(form.initial.get(name)) for name in AssociationPDFForm.base_fields}


def action(record, *, name, reason, before='', actor=None, details=None):
    actor_label = actor.get_username() if actor else 'Verified member'
    with update_write():
        MemberUpdateAction.objects.create(request=record, actor=actor, actor_label=actor_label,
            action=name, reason=reason, before=before, after=record.state, details=details or {})
    MemberEvent.objects.create(member=record.member, actor=actor, actor_label=actor_label,
        action='member_update_' + name, notes=reason,
        changes={'update_request': {'before': before, 'after': record.state}})


@terms_lock()
def submit_update(identifier, *, nonce, data):
    access = verified_access(identifier, nonce, allow_submitted=True)
    member = Member.objects.select_for_update().select_related('application').get(pk=access.member_id)
    access = access_record(identifier, nonce, lock=True)
    if access.access_expires_at <= timezone.now():
        raise ValidationError(EXPIRED)
    form = PublicMemberUpdateForm(data, instance=member, request_key=access.pk)
    if not form.is_valid() or form.cleaned_data['request_key'] != access.pk:
        raise ValidationError('Review the information and submit the current form.')
    proposed = {name: scalar(form.cleaned_data.get(name)) for name in AssociationPDFForm.base_fields}
    existing = MemberUpdateRequest.objects.filter(access=access).first()
    if existing:
        if existing.proposed_values != proposed:
            raise ValidationError('This update was already submitted. Contact the Help Desk for a further correction.')
        return existing
    if not can_request(member) or member.version != access.member_version or access.submitted_at:
        raise ValidationError(EXPIRED)
    if pending_request(member):
        raise ValidationError('An update is already awaiting staff review. Contact the Help Desk to follow up.')
    previous = initial_values(member)
    changed = [name for name in previous if previous[name] != proposed[name] and name != 'pwd_number']
    if not changed:
        raise ValidationError('No information has changed. Edit at least one field before submitting.')
    with update_write():
        record = MemberUpdateRequest.objects.create(access=access, member=member, member_version=member.version,
            previous_values=previous, proposed_values=proposed, changed_fields=changed)
        action(record, name='submitted', reason='Requested changes to: ' + ', '.join(str(form.fields[name].label) for name in changed) + '.')
        access.submitted_at = timezone.now()
        access.save(update_fields=['submitted_at'])
    return record


def review_actor(user, *, decision=False):
    actor = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    if actor is None:
        raise PermissionDenied
    permissions = ['members.view_member', 'members.change_member']
    if decision:
        permissions.append('members.change_member_status')
    require_workspace_permissions(actor, *permissions)
    return actor


def locked_review(pk, *, version, member_version):
    identity = MemberUpdateRequest.objects.get(pk=pk)
    member = Member.objects.select_for_update().select_related('application').get(pk=identity.member_id)
    record = MemberUpdateRequest.objects.select_for_update().get(pk=pk)
    record.member = member
    if record.version != version or member.version != member_version:
        raise ValidationError('The record changed. Reload and compare the current information before continuing.')
    if not can_request(member) or record.state == 'approved':
        raise ValidationError('This update is no longer awaiting approval, or the member is inactive or archived.')
    return record


@terms_lock()
def invite_member(pk, *, user, version, member_version):
    actor = review_actor(user)
    record = locked_review(pk, version=version, member_version=member_version)
    existing = getattr(record, 'invitation', None)
    if existing:
        return existing
    with update_write():
        job = update_mail.queue_email(request=record, recipient=record.access.recipient,
            subject='Please visit the barangay office to verify your updated information',
            body='Please visit the Barangay Santolan PWD Association office for an interview or screening '
                 'to confirm the member information you requested to update. Bring documents supporting your '
                 'changes and your Association membership reference, if available.\n\nYour changes will be applied only after staff verification '
                 'and approval. Contact the Association Help Desk for office hours or assistance.')
        before = record.state
        if record.state != 'needs_verification':
            record.state = 'invited'
        record.version += 1
        record.save(update_fields=['state', 'version'])
        action(record, actor=actor, name='invited', before=before,
            reason='Requested an office interview or screening by email to verify the member’s updated information.',
            details={'email': str(job.pk)})
    return job


@terms_lock()
def retry_invitation(pk, *, user, version, member_version):
    actor = review_actor(user)
    record = locked_review(pk, version=version, member_version=member_version)
    job = record.invitation
    with update_write():
        job = type(job).objects.select_for_update().get(pk=job.pk)
        if job.state not in ('queued', 'failed') or job.accepted_at:
            raise ValidationError('This invitation was accepted or its delivery is unconfirmed. Check the sending account before retrying.')
        from assistance.referral_models import ReferralSettings
        configuration = ReferralSettings.objects.filter(pk=1).first()
        if configuration:
            job.sender = configuration.sender_email
        job.state = 'queued'
        job.save(update_fields=['state', 'sender'])
        record.version += 1
        record.save(update_fields=['version'])
        action(record, actor=actor, name='email_retry', before=record.state,
            reason='Retried the office-verification invitation email.', details={'email': str(job.pk)})
        transaction.on_commit(partial(update_mail.deliver, job.pk), robust=True)
    return job


@terms_lock()
def decide_update(pk, *, user, version, member_version, decision, reason, interview_confirmed=False):
    actor = review_actor(user, decision=True)
    record = locked_review(pk, version=version, member_version=member_version)
    if not reason.strip() or len(reason) > 2000:
        raise ValidationError('Record a reason for this decision (up to 2,000 characters).')
    if decision not in ('approved', 'needs_verification'):
        raise ValidationError('Choose an available review decision.')
    before = record.state
    if decision == 'approved':
        if not update_mail.accepted(getattr(record, 'invitation', None)):
            raise ValidationError('Send the office-verification invitation successfully before approving this update.')
        if interview_confirmed is not True:
            raise ValidationError('Confirm the member attended the office interview or screening and their information was verified.')
        current = initial_values(record.member)
        merged = current | {name: record.proposed_values[name] for name in record.changed_fields}
        merged['pwd_number'] = record.member.control_number
        if merged != current:
            from .services import update_member
            update_member(record.member_id, user=actor, version=member_version,
                data=merged | {'member_profile_format': 'association_pdf_v1', 'version': member_version,
                              'acknowledgement': 'on', 'notes': reason.strip()}, notes=reason.strip())
        record.approved_at = timezone.now()
        record.approved_by = actor
    with update_write():
        record.state = decision
        record.version += 1
        fields = ['state', 'version'] + (['approved_at', 'approved_by'] if decision == 'approved' else [])
        record.save(update_fields=fields)
        action(record, actor=actor, name=decision, reason=reason.strip(), before=before,
            details={'office_interview_confirmed': decision == 'approved', 'reviewed_member_version': member_version})
    return record


def comparison(record):
    current = initial_values(record.member)
    fields = MemberRegistrationForm(instance=record.member).fields
    def display(name, value):
        return dict(getattr(fields[name], 'choices', ())).get(value, value)
    return [{'name': name, 'label': fields[name].label, 'before': display(name, current.get(name, '')),
             'proposed': display(name, record.proposed_values[name]),
             'submitted_before': display(name, record.previous_values.get(name, ''))}
            for name in record.changed_fields]
