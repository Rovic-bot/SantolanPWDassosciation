"""Queue approval notices atomically, then send through the Association Gmail."""
from datetime import timedelta
from functools import partial

from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage, get_connection
from django.core.validators import validate_email
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from assistance.referral_connection import EmailConnectionRequired, transport_for
from assistance.referral_mail import local_delivery
from assistance.referral_models import ReferralSettings
from core.email_delivery import EmailDeliveryUnconfirmed, delivery_help, send_message
from .approval_email_models import MembershipApprovalEmail, MembershipApprovalEmailAttempt, approval_email_write
from .registration_models import RegistrationIntake, registration_write
from . import registration_services as registration


def queue_approval_email(intake, revision, *, user):
    """The caller holds the intake lock inside the approval transaction."""
    if intake.channel != 'online' or intake.membership_application.status != 'approved':
        return None
    recipient = (revision.data.get('email') or '').strip()
    try:
        validate_email(recipient)
    except ValidationError:
        recipient = ''
    configuration = ReferralSettings.objects.filter(pk=1).first()
    with approval_email_write():
        job = MembershipApprovalEmail.objects.create(intake=intake, revision=revision,
            recipient=recipient, sender=configuration.sender_email if configuration else '',
            subject='You are now a member of the Santolan PWD Association',
            body=render_to_string('membership/registration/approval_email.txt', {
                'applicant_name': revision.data['full_name'], 'reference': intake.short_reference}),
            requested_by=user, requested_by_label=user.get_username(),
            state='queued' if recipient else 'skipped')
    if recipient:
        transaction.on_commit(partial(deliver_approval_email, job.pk), robust=True)
    return job


@sensitive_variables()
def deliver_approval_email(identifier):
    return deliver_membership_email(identifier, MembershipApprovalEmail, MembershipApprovalEmailAttempt,
                                    message_prefix='membership-approval')


@sensitive_variables()
def deliver_membership_email(identifier, email_model, attempt_model, *, message_prefix, pending_only=False, source_guard=None):
    # A committed claim prevents repeated callbacks from submitting the same mail.
    with transaction.atomic(), approval_email_write():
        source_is_current = source_guard(identifier) if source_guard else None
        if pending_only:
            intake_id = email_model.objects.values_list('intake_id', flat=True).get(pk=identifier)
            intake = RegistrationIntake.objects.select_for_update().get(pk=intake_id)
        job = email_model.objects.select_for_update().get(pk=identifier)
        if job.state != 'queued' or job.accepted_at or job.attempts.filter(outcome='accepted').exists():
            return False
        if source_is_current and not source_is_current(job):
            job.state = 'cancelled'
            job.save(update_fields=['state'])
            return False
        if pending_only and ((intake.membership_application_id and intake.membership_application.status != 'pending')
                             or intake.current_revision != job.revision.number):
            job.state = 'cancelled'
            job.save(update_fields=['state'])
            return False
        job.state = 'sending'
        job.attempt_count += 1
        job.last_attempt_at = timezone.now()
        job.save(update_fields=['state', 'attempt_count', 'last_attempt_at'])
        number = job.attempt_count
    error_type, uncertain = '', False
    try:
        configuration = ReferralSettings.objects.filter(pk=1).first()
        if not configuration or not job.sender or configuration.sender_email.casefold() != job.sender.casefold():
            raise EmailConnectionRequired('Connect the saved Association sender before retrying.')
        backend, options = transport_for(configuration)
        with transaction.atomic(), approval_email_write():
            claimed = email_model.objects.select_for_update().get(pk=identifier)
            claimed.backend = backend
            claimed.save(update_fields=['backend'])
        connection = get_connection(backend=backend, **options)
        message = EmailMessage(subject=job.subject, body=job.body,
            from_email=f'Santolan PWD Association <{job.sender}>', to=[job.recipient],
            reply_to=[job.sender], connection=connection,
            headers={'Message-ID': f'<{message_prefix}-{job.pk}@{job.sender.rsplit("@", 1)[-1]}>'})
        send_message(message)
    except Exception as error:
        error_type = type(error).__name__[:100]
        uncertain = isinstance(error, EmailDeliveryUnconfirmed)
    with transaction.atomic(), approval_email_write():
        current = email_model.objects.select_for_update().get(pk=identifier)
        if current.state != 'sending' or current.attempt_count != number:
            return False
        current.state = 'uncertain' if uncertain else 'failed' if error_type else 'sent'
        current.accepted_at = None if error_type else timezone.now()
        current.save(update_fields=['state', 'accepted_at'])
        attempt_model.objects.create(email=current, number=number,
            outcome=current.state if error_type else 'accepted', error_type=error_type)
    return not error_type


def retry_available(job):
    stale = job.state == 'sending' and job.last_attempt_at and job.last_attempt_at < timezone.now() - timedelta(minutes=5)
    return job.state in ('queued', 'failed', 'uncertain') or bool(stale)


@transaction.atomic
def retry_approval_email(identifier, *, reference, user, confirmed):
    actor = registration.require_staff(user, 'membership.decide_membershipapplication')
    if confirmed is not True:
        raise ValidationError('Confirm that you want to retry this email.')
    intake = RegistrationIntake.objects.select_for_update().get(reference=reference)
    with approval_email_write(), registration_write():
        job = MembershipApprovalEmail.objects.select_for_update().get(pk=identifier, intake=intake)
        if not retry_available(job):
            raise ValidationError('This email was already accepted, is still sending, or has no valid recipient.')
        if not job.sender:
            configuration = ReferralSettings.objects.filter(pk=1).first()
            if not configuration:
                raise ValidationError('Connect the Association Gmail account before retrying.')
            job.sender = configuration.sender_email
            job.save(update_fields=['sender'])
        job.state = 'queued'
        job.save(update_fields=['state'])
        registration.record_action(intake, 'approval_email_retry', job.revision, actor=actor,
            reason='Administrator requested another attempt for the saved membership approval email.',
            payload={'email_id': str(job.pk)})
        transaction.on_commit(partial(deliver_approval_email, job.pk), robust=True)


def notification_context(intake, user):
    if not intake or not user.has_perms(['membership.view_membershipapplication', registration.VIEW]):
        return {}
    job = MembershipApprovalEmail.objects.filter(intake=intake).first()
    if not job:
        return {}
    return {'membership_approval_email': job,
        'membership_approval_email_help': delivery_help(job),
        'membership_approval_email_label': ('Saved to test outbox — not sent to an inbox'
            if job.state == 'sent' and local_delivery(job) else job.get_state_display()),
        'can_retry_membership_email': user.has_perm('membership.decide_membershipapplication') and retry_available(job)}
