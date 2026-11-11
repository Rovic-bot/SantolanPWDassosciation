"""Durable, single-claim email attempts. SMTP acceptance is not inbox delivery."""
from datetime import timedelta
from functools import partial

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables
from core.email_delivery import delivery_unconfirmed, send_message
from .referral_models import ReferralEmail, ReferralEmailAttempt, ReferralSettings, referral_write
from .referral_connection import EmailConnectionRequired, transport_for


def local_delivery(job):
    return job.backend in ('django.core.mail.backends.filebased.EmailBackend',
        'django.core.mail.backends.locmem.EmailBackend', 'django.core.mail.backends.console.EmailBackend')


def development_delivery():
    return settings.EMAIL_BACKEND in ('django.core.mail.backends.filebased.EmailBackend',
        'django.core.mail.backends.locmem.EmailBackend', 'django.core.mail.backends.console.EmailBackend')


@sensitive_variables()
def deliver_email(identifier):
    # Claim and commit before talking to SMTP. Concurrent callbacks/workers cannot
    # claim the same job; an unconfirmed in-flight attempt is never auto-retried.
    with transaction.atomic(), referral_write():
        job = ReferralEmail.objects.select_for_update().get(pk=identifier)
        if job.state != 'queued':
            return False
        job.state = 'sending'
        job.attempt_count += 1
        job.last_attempt_at = timezone.now()
        job.backend = settings.EMAIL_BACKEND
        job.save(update_fields=['state', 'attempt_count', 'last_attempt_at', 'backend'])
        number = job.attempt_count
    error_type = ''
    try:
        configuration = ReferralSettings.objects.filter(pk=1).first()
        if not configuration or configuration.sender_email.casefold() != job.sender.casefold():
            raise EmailConnectionRequired('The saved sender is no longer the connected account.')
        backend, options = transport_for(configuration)
        with transaction.atomic(), referral_write():
            claimed = ReferralEmail.objects.select_for_update().get(pk=identifier)
            claimed.backend = backend
            claimed.save(update_fields=['backend'])
        connection = get_connection(backend=backend, **options)
        message = EmailMessage(subject=job.subject, body=job.body,
            from_email=f'Santolan PWD Association <{job.sender}>', to=[job.recipient],
            reply_to=[job.sender], connection=connection,
            headers={'Message-ID': f'<referral-{job.pk}@{job.sender.rsplit("@", 1)[-1]}>'})
        send_message(message)
    except Exception as error:
        error_type = type(error).__name__[:100]
    with transaction.atomic(), referral_write():
        current = ReferralEmail.objects.select_for_update().get(pk=identifier)
        if current.state != 'sending' or current.attempt_count != number:
            return False
        # Retain the existing schema; EmailDeliveryUnconfirmed in the attempt
        # distinguishes an interrupted submission from a definite rejection.
        current.state = 'failed' if error_type else 'sent'
        current.accepted_at = None if error_type else timezone.now()
        current.save(update_fields=['state', 'accepted_at'])
        ReferralEmailAttempt.objects.create(email=current, number=number,
            outcome='failed' if error_type else 'accepted', error_type=error_type)
    return not error_type


@transaction.atomic
def retry_email(identifier, *, user, reason, confirmed):
    from .referral_services import current_actor, record_action
    actor = current_actor(user, 'assistance.send_referral_email')
    if confirmed is not True or not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValidationError('Confirm the retry and record its reason.')
    with referral_write():
        job = ReferralEmail.objects.select_for_update().select_related('ticket').get(pk=identifier)
        stale = job.state == 'sending' and job.last_attempt_at < timezone.now() - timedelta(minutes=5)
        if job.state not in ('failed', 'queued') and not stale:
            raise ValidationError('This email is already accepted or an attempt is still in progress.')
        job.state = 'queued'
        job.save(update_fields=['state'])
        record_action(job.ticket, action='email_retry', actor=actor, channel='internal',
            before=job.ticket.status, notes=reason.strip())
        transaction.on_commit(partial(deliver_email, job.pk), robust=True)


def delivery_label(job):
    if delivery_unconfirmed(job):
        return 'Email delivery is unconfirmed'
    if job.state == 'sent' and local_delivery(job):
        return 'Saved to development outbox — not sent to an inbox'
    return job.get_state_display()
