"""Commit-only, version-bound notices through the existing Association sender."""
from functools import partial

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import Http404
from django.template.loader import render_to_string

from assistance.referral_mail import local_delivery
from assistance.referral_models import ReferralSettings
from core.email_delivery import delivery_help
from .approval_email import deliver_membership_email
from .approval_email_models import approval_email_write
from .pdao_email_models import PDAOReviewEmail as Email, PDAOReviewEmailAttempt as Attempt
from .pdao_models import PDAORegistration
from .registration_models import registration_write
from . import pdao_services as services


def validate_recipient(data):
    recipient = (data.get('email') or '').strip()
    try:
        validate_email(recipient)
    except ValidationError:
        raise ValidationError('Save a valid applicant email in Application details before sending a review notice.') from None
    return recipient


def current_notice(job, registration):
    if job.outcome == 'claim_ready':
        return registration.status == 'forwarded' and registration.version == job.expected_version
    return (registration.data.get('intake_channel', 'online') == 'online'
            and registration.status == job.outcome and registration.version == job.expected_version)


def lock_source(identifier):
    # Always lock source before email, matching transition and retry lock order.
    key = Email.objects.values_list('registration_id', flat=True).get(pk=identifier)
    registration = PDAORegistration.objects.select_for_update().get(pk=key)
    return lambda job: current_notice(job, registration)


def deliver_review_email(identifier):
    return deliver_membership_email(identifier, Email, Attempt, message_prefix='pdao-review', source_guard=lock_source)


def queue_review_email(registration, *, user, reason=''):
    """Caller holds the registration lock within the transition transaction."""
    if registration.data.get('intake_channel', 'online') != 'online':
        return None
    if registration.status not in ('ready', 'needs_info'):
        raise ValidationError('This status does not send a PDAO review notice.')
    data = registration.current_data
    recipient = validate_recipient(data)
    configuration = ReferralSettings.objects.filter(pk=1).first()
    with approval_email_write():
        job = Email.objects.create(registration=registration, expected_version=registration.version,
            outcome=registration.status, recipient=recipient,
            sender=configuration.sender_email if configuration else '',
            subject=('Your PDAO application — please visit the office for verification' if registration.status == 'ready'
                     else 'Your PDAO application — information needs checking'),
            body=render_to_string('membership/pdao/review_email.txt', {'applicant_name': data['full_name'],
                'reference': registration.short_reference, 'ready': registration.status == 'ready', 'reason': reason}),
            requested_by=user, requested_by_label=user.get_username())
        transaction.on_commit(partial(deliver_review_email, job.pk), robust=True)
    return job


@transaction.atomic
def retry_review_email(key, *, user, identifier):
    actor = services.require_staff(user, services.FORWARD)
    registration = PDAORegistration.objects.select_for_update().filter(pk=key).first()
    if not registration:
        raise Http404
    with registration_write(), approval_email_write():
        job = Email.objects.select_for_update().filter(pk=identifier, registration=registration).first()
        if not job:
            raise Http404
        if not current_notice(job, registration):
            raise ValidationError('This application changed. Review its current details before sending another notice.')
        if job.state not in ('queued', 'failed') or job.accepted_at or job.attempts.filter(outcome='accepted').exists():
            raise ValidationError('This message was accepted, is still sending, or its delivery is unconfirmed. Check the sender mailbox before taking further action.')
        if not job.sender:
            configuration = ReferralSettings.objects.filter(pk=1).first()
            if not configuration:
                raise ValidationError('Connect the Association Gmail account before retrying.')
            job.sender = configuration.sender_email
        job.state = 'queued'
        job.save(update_fields=['sender', 'state'])
        services.record_event(registration, 'email_retry', actor, details={'email_id': str(job.pk)})
        services.require_staff(actor, services.FORWARD)
        transaction.on_commit(partial(deliver_review_email, job.pk), robust=True)
    return job


def notification_context(registration, user):
    from .pdao_claim_email import claim_context
    jobs = list(registration.review_emails.all()[:10])
    for job in jobs:
        job.delivery_help = delivery_help(job)
        job.delivery_label = ('Saved to test outbox — not sent to an inbox'
            if job.state == 'sent' and local_delivery(job) else job.get_state_display())
        job.can_retry = (user.has_perm(services.FORWARD) and current_notice(job, registration)
                         and job.state in ('queued', 'failed'))
    return {'pdao_emails': jobs, **claim_context(registration, user, jobs)}
