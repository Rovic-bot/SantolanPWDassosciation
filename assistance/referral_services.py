"""Ticket-scoped verification, atomic intake, staff review and retained email jobs."""
from datetime import timedelta
from functools import partial
import hashlib
import json
import logging
from uuid import UUID, uuid4

from django.conf import settings
from django.core import signing
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import OperationalError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.debug import sensitive_variables
from accounts.backends import reserve_windows
from core.permissions import require_workspace_permissions
from events.services import normalize_name, VERIFICATION_FAILED
from members.models import Member
from .referral_forms import NewConcernForm, TicketForm, ReviewForm, QuickActionForm, SettingsForm
from .referral_models import (ReferralGrant, ReferralTicket, ReferralAttachment, ReferralAction,
    ReferralEmail, ReferralSettings, ReferralSettingsEvent, ReferralWindow, referral_write)

logger = logging.getLogger(__name__)
NOTICE = 'Submitting this request does not guarantee financial assistance, referral approval, or beneficiary selection. This service is separate from membership registration and program applications.'
STATUSES = {
    'received': {'received', 'in_review', 'needs_information', 'closed'},
    'in_review': {'in_review', 'needs_information', 'referred', 'closed'},
    'needs_information': {'needs_information', 'in_review', 'closed'},
    'referred': {'referred', 'in_review', 'needs_information', 'closed'},
    'closed': set(),
}


def enabled():
    return getattr(settings, 'REFERRAL_ENABLED', False)


def digest(value):
    return hashlib.sha256(json.dumps(value, default=str, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def binding_for(session_key):
    if not session_key:
        raise PermissionDenied
    return salted_hmac('referral.session.v1', session_key, algorithm='sha256').hexdigest()


def current_actor(user, *permissions):
    actor = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    if actor is None:
        raise PermissionDenied
    require_workspace_permissions(actor, 'assistance.view_referralticket', *permissions)
    return actor


def new_concern_count():
    """Count submitted concerns that have not entered staff review."""
    return ReferralTicket.objects.filter(status=ReferralTicket.Status.RECEIVED).count()


def source_snapshot(member):
    application = member.application
    return {'member': member.pk, 'version': member.version, 'active': member.is_active,
        'archived_at': member.archived_at, 'full_name': member.full_name, 'birthdate': member.birthdate,
        'contact_number': member.contact_number, 'control_number': member.control_number,
        'membership': application.pk, 'membership_version': application.version,
        'approved': application.status == 'approved', 'verified': application.prpwd_verified,
        'verified_at': application.prpwd_verified_at, 'decided_at': application.decided_at,
        'association_approval': association_approval(member)}


def association_approval(member):
    """Recognize the audited onsite decision without manufacturing PRPWD proof."""
    from membership.registration_decisions import WORKFLOW
    from membership.registration_models import RegistrationAction

    application = member.application
    if not application.decided_by_id:
        return None
    return RegistrationAction.objects.filter(
        intake__membership_application_id=application.pk, intake__category='association',
        action='registration_approved', actor_id=application.decided_by_id,
        payload__workflow=WORKFLOW, payload__status='approved',
        payload__application_reference=str(application.reference),
    ).values_list('pk', flat=True).first()


def valid_member(member):
    application = member.application
    return bool(member.is_active and not member.archived_at and application.status == 'approved'
        and application.decided_at and (
            (application.prpwd_verified is True and application.prpwd_verified_at)
            or association_approval(member)))


def reserve_attempt(control_number, address, binding):
    limits = {
        salted_hmac('referral.verify.member', control_number.strip().upper(), algorithm='sha256').hexdigest(): settings.REFERRAL_MEMBER_LIMIT,
        salted_hmac('referral.verify.address', address or 'unavailable', algorithm='sha256').hexdigest(): settings.REFERRAL_ADDRESS_LIMIT,
        salted_hmac('referral.verify.session', binding, algorithm='sha256').hexdigest(): settings.REFERRAL_MEMBER_LIMIT,
    }
    try:
        return reserve_windows(limits, settings.REFERRAL_WINDOW_SECONDS, ReferralWindow)
    except (OperationalError, ReferralWindow.DoesNotExist):
        return False


def verify_member(*, binding, control_number, full_name, identifier=None):
    if not enabled():
        raise PermissionDenied
    code = control_number.strip().upper()
    with transaction.atomic(), referral_write():
        member = Member.objects.select_for_update().select_related('application').filter(control_number=code).first()
        if not (member and member.control_number.strip().upper() == code and valid_member(member)
                and normalize_name(member.full_name) == normalize_name(full_name)):
            raise ValidationError(VERIFICATION_FAILED)
        if not ReferralSettings.objects.filter(pk=1).exists():
            raise ValidationError('This service is not available yet. Please contact the Association Help Desk.')
        if identifier and ReferralGrant.objects.filter(pk=identifier).exists():
            grant = get_grant(identifier, binding, lock=True)
            if grant.member_id != member.pk:
                raise ValidationError('This form was already used for another request. Open New concern to start again.')
            return grant
        return ReferralGrant.objects.create(id=identifier or uuid4(), member=member, binding_digest=binding,
            source_digest=digest(source_snapshot(member)),
            expires_at=timezone.now() + timedelta(seconds=settings.REFERRAL_GRANT_SECONDS))


def new_request_key(binding):
    return signing.dumps({'grant': str(uuid4()), 'binding': binding}, salt='referral.new-concern.v1')


@sensitive_variables()
@transaction.atomic
def start_concern(*, binding, data, files=None):
    """Verify the intake and create its conversation atomically."""
    form = NewConcernForm(data, files)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    values = form.cleaned_data
    try:
        token = signing.loads(values['request_key'], salt='referral.new-concern.v1',
            max_age=settings.REFERRAL_GRANT_SECONDS)
        identifier = UUID(token['grant'])
        if not constant_time_compare(token['binding'], binding):
            raise ValueError
    except (signing.BadSignature, ValueError, TypeError, KeyError, AttributeError):
        raise ValidationError('This form has expired. Reload New concern and submit again.') from None
    grant = verify_member(binding=binding, control_number=values['control_number'],
        full_name=values['full_name'], identifier=identifier)
    # The visible Submit notice replaces the separate acknowledgment checkbox.
    return submit_ticket(grant.pk, binding, data={
        'email': values['email'], 'subject': values['subject'],
        'assistance_type': values['assistance_type'], 'concern': values['concern'],
        'acknowledgement': True,
    })


def get_grant(identifier, binding, *, lock=False, recheck=True):
    try:
        identifier = UUID(str(identifier))
    except (ValueError, TypeError, AttributeError):
        raise PermissionDenied from None
    query = ReferralGrant.objects.select_for_update() if lock else ReferralGrant.objects
    grant = query.select_related('member__application').filter(pk=identifier).first()
    if not (grant and constant_time_compare(grant.binding_digest, binding)
            and not grant.revoked_at and grant.expires_at > timezone.now()):
        raise PermissionDenied
    if recheck and (not valid_member(grant.member) or grant.source_digest != digest(source_snapshot(grant.member))):
        raise ValidationError('Membership information changed. Verify your membership again or visit the Help Desk.')
    return grant


def record_action(ticket, *, action, actor=None, before='', channel='internal', notes, message=''):
    return ReferralAction.objects.create(ticket=ticket, action=action, actor=actor,
        actor_label=actor.get_username() if actor else '', status_before=before, status_after=ticket.status,
        version=ticket.version, channel=channel, notes=notes, member_message=message)


def queue_email(ticket, action, *, acknowledgment=False):
    from django.template.loader import render_to_string
    configuration = ReferralSettings.objects.select_for_update().get(pk=1)
    body = render_to_string('assistance/referrals/email.txt', {'ticket': ticket, 'action': action,
        'acknowledgment': acknowledgment, 'notice': NOTICE, 'sender': configuration.sender_email})
    job = ReferralEmail.objects.create(ticket=ticket, action=action, recipient=ticket.email,
        sender=configuration.sender_email, subject=(
            'Request received — ' if acknowledgment else 'Request update — ') + ticket.short_reference, body=body)
    from .referral_mail import deliver_email
    transaction.on_commit(partial(deliver_email, job.pk), robust=True)
    return job


def submit_ticket(identifier, binding, *, data, files=None):
    if not enabled():
        raise PermissionDenied
    saved_files = []
    try:
        with transaction.atomic(), referral_write():
            grant = get_grant(identifier, binding, lock=True)
            form = TicketForm(data, files, member=grant.member)
            if not form.is_valid():
                raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
            values = {name: form.cleaned_data[name] for name in (
                'email', 'subject', 'assistance_type', 'concern', 'acknowledgement')}
            values.update(full_name=grant.member.full_name, address=grant.member.address,
                contact_number=grant.member.contact_number)
            attachments = []
            for key in ('evidence_1',):
                upload = form.cleaned_data[key]
                if upload:
                    sha = hashlib.sha256()
                    for chunk in upload.chunks():
                        sha.update(chunk)
                    upload.seek(0)
                    attachments.append((key, upload, sha.hexdigest()))
            fingerprint = digest({'form': 'referral-v2', 'values': values,
                'evidence': [(key, upload.name, upload.size, sha) for key, upload, sha in attachments]})
            existing = ReferralTicket.objects.filter(grant=grant).first()
            if existing:
                if existing.submission_digest != fingerprint:
                    raise ValidationError('This request was already submitted. Keep its reference and contact the Association for corrections.')
                return existing
            ticket = ReferralTicket(grant=grant, member=grant.member, submission_digest=fingerprint,
                member_snapshot=json.loads(json.dumps(source_snapshot(grant.member), default=str)), **values)
            ticket.reference = 'ASR-' + str(ticket.pk)
            ticket.full_clean()
            ticket.save()
            for key, upload, sha in attachments:
                item = ReferralAttachment(ticket=ticket, label=upload.name[:200], content_type=upload.content_type,
                    size=upload.size, sha256=sha)
                item.file.save(upload.name, upload, save=False)
                saved_files.append((item.file.storage, item.file.name))
                item.save()
            action = record_action(ticket, action='submitted', channel='online', notes='Request submitted after membership verification.')
            queue_email(ticket, action, acknowledgment=True)
            return ticket
    except Exception:
        for storage, name in saved_files:
            try:
                storage.delete(name)
            except OSError:
                logger.error('Uncommitted referral file cleanup failed.')
        raise


@transaction.atomic
def finish(identifier, binding):
    with referral_write():
        grant = get_grant(identifier, binding, lock=True, recheck=False)
        grant.revoked_at = timezone.now()
        grant.save(update_fields=['revoked_at'])


@transaction.atomic
def review_ticket(identifier, *, user, data):
    actor = current_actor(user, 'assistance.review_referralticket')
    form = ReviewForm(data)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    values = form.cleaned_data
    if values['channel'] == 'email':
        current_actor(actor, 'assistance.send_referral_email')
    with referral_write():
        ticket = ReferralTicket.objects.select_for_update().get(pk=identifier)
        if ticket.version != values['version']:
            previous = ticket.actions.filter(action='reviewed', actor=actor,
                channel=values['channel'], version=values['version'] + 1).first()
            if previous and previous.member_message == values['member_message']:
                return ticket
            raise ValidationError('This conversation has new activity. Read the latest messages, then send your reply again.')
        if ticket.status == ReferralTicket.Status.CLOSED:
            raise ValidationError('This conversation is closed. Its history is retained for staff.')
        if values['channel'] == 'email':
            from .referral_connection import require_connection
            configuration = ReferralSettings.objects.select_for_update().filter(pk=1).first()
            if not configuration or configuration.version != values['sender_version']:
                raise ValidationError('The Association email settings changed. Reload this ticket before sending.')
            require_connection(configuration)
        before = ticket.status
        if ticket.status == ReferralTicket.Status.RECEIVED:
            ticket.status = ReferralTicket.Status.REVIEW
        ticket.version += 1
        ticket.save(update_fields=['status', 'version'])
        action = record_action(ticket, action='reviewed',
            actor=actor, before=before, channel=values['channel'],
            notes='Email reply recorded.' if values['channel'] == 'email' else 'Reply sent in the online conversation only.',
            message=values['member_message'])
        if values['channel'] == 'email':
            queue_email(ticket, action)
        return ticket


@transaction.atomic
def quick_update_ticket(identifier, *, user, data):
    """Owner-authorized direct staff actions; no email is sent by this path."""
    actor = current_actor(user, 'assistance.review_referralticket')
    form = QuickActionForm(data)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    values = form.cleaned_data
    recording_reply = values['action'] == 'record_reply'
    opening_review = values['action'] == 'begin_review'
    if recording_reply:
        current_actor(actor, 'assistance.send_referral_email')
    action_name = ('review_started' if opening_review else
        'quick_gmail_reply_recorded' if recording_reply else 'quick_status_updated')
    with referral_write():
        ticket = ReferralTicket.objects.select_for_update().get(pk=identifier)
        # Opening an already handled ticket never resets its state or adds an
        # extra review event, including simultaneous opens by different staff.
        if opening_review and ticket.status != ReferralTicket.Status.RECEIVED:
            return ticket
        target = (ReferralTicket.Status.REVIEW if opening_review else
            ticket.status if recording_reply else ReferralTicket.Status.CLOSED)
        # A repeated click with the same version and actor is the same action.
        # Other stale actions still fail, including a changed target status.
        if ticket.version == values['version'] + 1 and ticket.actions.filter(
                version=ticket.version, actor=actor, action=action_name, status_after=target).exists():
            return ticket
        if ticket.version != values['version']:
            raise ValidationError('Another staff member updated this ticket. Reload before choosing an action.')
        if ticket.status == ReferralTicket.Status.CLOSED:
            raise ValidationError('This ticket is closed and retains its final history.')
        if not recording_reply and target == ticket.status:
            raise ValidationError('The ticket already has this status.')
        before = ticket.status
        ticket.status = target
        ticket.version += 1
        ticket.save(update_fields=['status', 'version'])
        notes = ('Ticket opened for review.' if opening_review else
                 'Admin recorded a reply sent through Gmail.' if recording_reply
                 else f'Status changed to {ticket.get_status_display()}.')
        record_action(ticket, action=action_name, actor=actor, before=before,
            channel='email' if recording_reply else 'internal', notes=notes)
        return ticket


@transaction.atomic
@sensitive_variables()
def set_sender(*, user, data):
    actor = current_actor(user, 'assistance.configure_referrals')
    form = SettingsForm(data)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    with referral_write():
        row, _ = ReferralSettings.objects.get_or_create(pk=1, defaults={'sender_email': form.cleaned_data['sender_email']})
        row = ReferralSettings.objects.select_for_update().get(pk=1)
        if row.version != form.cleaned_data['version']:
            raise ValidationError('The Association email address changed. Reload before saving.')
        before = row.sender_email if row.version else ''
        sender = form.cleaned_data['sender_email']
        password = form.cleaned_data['gmail_app_password']
        if before == sender and not password:
            raise ValidationError('Enter a different email address.')
        if password:
            from .referral_connection import check_gmail_login, encrypt_password
            check_gmail_login(sender, password)
            row.gmail_password_encrypted = encrypt_password(sender, password)
        elif before.casefold() != sender.casefold():
            # Credentials for one account must never be used for another.
            row.gmail_password_encrypted = ''
        current_actor(actor, 'assistance.configure_referrals')
        row.sender_email = sender
        row.version += 1
        row.full_clean()
        row.save(update_fields=['sender_email', 'version', 'gmail_password_encrypted'])
        ReferralSettingsEvent.objects.create(actor=actor, before=before, after=row.sender_email,
            version=row.version, reason=form.cleaned_data['reason'])
        return row
