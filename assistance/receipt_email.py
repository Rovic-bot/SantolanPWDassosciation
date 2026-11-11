"""Representative receipt mail, with append-only delivery events in private history.

The receipt row serializes queue/claim/retry transitions. Queueing occurs in the
outer receipt transaction after the release writer validates its single audit.
SMTP runs only after commit; neither retries nor delivery events edit the receipt.
"""
from datetime import timedelta
from functools import partial

from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from core.email_delivery import send_message, EmailDeliveryUnconfirmed
from core.permissions import require_workspace_permissions
from programs.decision_email import recipient_for
from .models import AssistanceLog, AssistanceRelease
from .referral_connection import EmailConnectionRequired, transport_for, TEST_BACKEND
from .referral_models import ReferralSettings

ACTION = 'representative_receipt_email'
CONTRACT = 'representative-receipt-email-v1'


def latest(release):
    return AssistanceLog.objects.filter(application_id=release.application_id,
        action=ACTION, snapshot__release=str(release.pk)).order_by('-pk').first()


def event(release, payload, *, user=None):
    return AssistanceLog.objects.create(application_id=release.application_id,
        actor=user, actor_label=user.get_username() if user else 'Receipt email service',
        action=ACTION, notes='Representative receipt email: ' + payload['state'],
        snapshot={**payload, 'contract': CONTRACT, 'release': str(release.pk)})


def queue_receipt_email(release, *, user):
    claimant = release.approval_snapshot.get('claimant', {})
    if claimant.get('claimant_type') != 'representative':
        return
    # Caller already holds the receipt transaction and its source locks.
    if latest(release):
        return
    recipient, source, skipped = recipient_for(release.application)
    configuration = ReferralSettings.objects.filter(pk=1).first()
    payload = {'state': 'skipped' if skipped else 'queued', 'skip_reason': skipped,
        'recipient': recipient, 'recipient_source': source,
        'sender': configuration.sender_email if configuration else '',
        'subject': ' '.join(('Assistance collected by your representative — ' +
                            release.approval_snapshot['program_name']).split())[:250],
        'body': render_to_string('assistance/receipt_email.txt', {'release': release, 'claimant': claimant}),
        'attempt': 0, 'error_type': '', 'backend': ''}
    event(release, payload, user=user)
    if not skipped:
        transaction.on_commit(partial(deliver_receipt_email, release.pk), robust=True)


@sensitive_variables()
def deliver_receipt_email(identifier):
    with transaction.atomic():
        release = AssistanceRelease.objects.select_for_update().get(pk=identifier)
        saved = latest(release)
        if not saved or saved.snapshot['state'] != 'queued':
            return False
        payload = dict(saved.snapshot)
        if release.voided_at:
            event(release, {**payload, 'state': 'skipped', 'skip_reason': 'voided'})
            return False
        payload.update(state='sending', attempt=payload['attempt'] + 1, error_type='')
        claimed = event(release, payload)
    error_type, backend = '', ''
    try:
        configuration = ReferralSettings.objects.filter(pk=1).first()
        if not configuration or not payload['sender'] or configuration.sender_email.casefold() != payload['sender'].casefold():
            raise EmailConnectionRequired()
        backend, options = transport_for(configuration)
        message = EmailMessage(subject=payload['subject'], body=payload['body'],
            from_email=f'Santolan PWD Association <{payload["sender"]}>',
            to=[payload['recipient']], reply_to=[payload['sender']],
            connection=get_connection(backend=backend, **options),
            headers={'Message-ID': f'<receipt-{release.pk}@{payload["sender"].rsplit("@", 1)[-1]}>'})
        send_message(message)
    except Exception as error:
        error_type = type(error).__name__[:100]
    with transaction.atomic():
        release = AssistanceRelease.objects.select_for_update().get(pk=identifier)
        if latest(release).pk != claimed.pk:
            return False
        state = ('uncertain' if error_type == EmailDeliveryUnconfirmed.__name__ else
                 'failed' if error_type else 'sent')
        event(release, {**payload, 'state': state, 'error_type': error_type, 'backend': backend})
    return not error_type


def retryable(saved):
    return saved and (saved.snapshot['state'] in ('queued', 'failed', 'uncertain')
        or saved.snapshot['state'] == 'skipped' and saved.snapshot.get('skip_reason') in ('missing', 'invalid')
        or saved.snapshot['state'] == 'sending' and saved.occurred_at < timezone.now() - timedelta(minutes=5))


@transaction.atomic
def retry_receipt_email(identifier, *, application_id, user, confirmed):
    from .services import VIEW_PERMISSIONS
    require_workspace_permissions(user, *VIEW_PERMISSIONS,
        'assistance.view_assistancerelease', 'assistance.record_release')
    if confirmed is not True:
        raise ValidationError('Confirm the email retry.')
    release = AssistanceRelease.objects.select_for_update().select_related(
        'application__member', 'application__program').get(pk=identifier, application_id=application_id)
    saved = latest(release)
    if release.voided_at or not retryable(saved):
        raise ValidationError('This receipt email cannot be retried now.')
    payload = dict(saved.snapshot)
    if payload['state'] == 'skipped':
        recipient, source, skipped = recipient_for(release.application)
        if skipped:
            raise ValidationError('Save a valid beneficiary email address before retrying.')
        payload.update(recipient=recipient, recipient_source=source)
    configuration = ReferralSettings.objects.filter(pk=1).first()
    if not configuration:
        raise ValidationError('Connect the Association email account before retrying.')
    payload.update(sender=configuration.sender_email, state='queued', skip_reason='', error_type='')
    event(release, payload, user=user)
    transaction.on_commit(partial(deliver_receipt_email, release.pk), robust=True)


def notification_context(release, user):
    if not release:
        return None
    saved = latest(release)
    if not saved:
        return None
    payload = saved.snapshot
    state = payload['state']
    labels = {'sent': 'Email sent to the beneficiary.', 'queued': 'Beneficiary email queued.',
        'sending': 'Email delivery is unconfirmed.', 'uncertain': 'Email delivery is unconfirmed.',
        'failed': 'Email not sent. Check the Association email connection.',
        'skipped': 'Email not sent: no valid beneficiary email address.'}
    label = labels[state]
    if state == 'sent' and payload.get('backend') == TEST_BACKEND:
        label = 'Test email saved — not sent to an inbox.'
    if payload.get('skip_reason') == 'voided':
        label = 'Email not sent: this receipt was voided.'
    return {'label': label, 'recipient': payload['recipient'],
        'uncertain': state in ('sending', 'uncertain'),
        'can_retry': bool(not release.voided_at and retryable(saved) and user.has_perm('assistance.record_release'))}
