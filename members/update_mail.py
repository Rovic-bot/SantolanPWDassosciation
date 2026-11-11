"""Retained, single-claim delivery using the existing Association email account."""
from functools import partial

from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from assistance.referral_connection import EmailConnectionRequired, transport_for
from assistance.referral_mail import delivery_label
from assistance.referral_models import ReferralSettings
from core.email_delivery import EmailDeliveryUnconfirmed, send_message
from .update_models import MemberUpdateEmail, MemberUpdateEmailAttempt, update_write


def queue_email(*, recipient, subject, body, access=None, request=None):
    configuration = ReferralSettings.objects.filter(pk=1).first()
    with update_write():
        job = MemberUpdateEmail.objects.create(access=access, request=request, recipient=recipient,
            sender=configuration.sender_email if configuration else '', subject=subject, body=body)
    transaction.on_commit(partial(deliver, job.pk), robust=True)
    return job


@sensitive_variables()
def deliver(identifier):
    with transaction.atomic(), update_write():
        job = MemberUpdateEmail.objects.select_for_update().get(pk=identifier)
        if job.state != 'queued':
            return False
        if job.access_id and (job.access.expires_at <= timezone.now() or job.access.verified_at):
            job.state = 'cancelled'
            job.save(update_fields=['state'])
            return False
        job.state = 'sending'
        job.attempt_count += 1
        job.last_attempt_at = timezone.now()
        job.save(update_fields=['state', 'attempt_count', 'last_attempt_at'])
        number = job.attempt_count
    outcome, error_type = 'accepted', ''
    try:
        configuration = ReferralSettings.objects.filter(pk=1).first()
        if not configuration or configuration.sender_email.casefold() != job.sender.casefold():
            raise EmailConnectionRequired('Connect the Association email account before sending.')
        backend, options = transport_for(configuration)
        with transaction.atomic(), update_write():
            claimed = MemberUpdateEmail.objects.select_for_update().get(pk=identifier)
            claimed.backend = backend
            claimed.save(update_fields=['backend'])
        connection = get_connection(backend=backend, **options)
        message = EmailMessage(subject=job.subject, body=job.body,
            from_email=f'Santolan PWD Association <{job.sender}>', to=[job.recipient],
            reply_to=[job.sender], connection=connection,
            headers={'Message-ID': f'<member-update-{job.pk}@{job.sender.rsplit("@", 1)[-1]}>'})
        send_message(message)
    except Exception as error:
        outcome = 'uncertain' if isinstance(error, EmailDeliveryUnconfirmed) else 'failed'
        error_type = type(error).__name__[:100]
    with transaction.atomic(), update_write():
        current = MemberUpdateEmail.objects.select_for_update().get(pk=identifier)
        if current.state != 'sending' or current.attempt_count != number:
            return False
        current.state = 'sent' if outcome == 'accepted' else outcome
        current.accepted_at = timezone.now() if outcome == 'accepted' else None
        current.save(update_fields=['state', 'accepted_at'])
        MemberUpdateEmailAttempt.objects.create(email=current, number=number,
            outcome=outcome, error_type=error_type)
    return outcome == 'accepted'


def accepted(job):
    return bool(job and job.state == 'sent' and job.accepted_at
                and job.attempts.filter(outcome='accepted').exists())


def describe(job):
    return delivery_label(job) if job else 'No invitation sent yet'
