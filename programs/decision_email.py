"""Send saved eligibility decisions after commit using the Association Gmail connection."""
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
from assistance.referral_models import ReferralSettings
from core.permissions import require_workspace_permissions
from core.email_delivery import delivery_help, delivery_unconfirmed, send_message
from .decision_email_models import ApplicationDecisionEmail, ApplicationDecisionEmailAttempt, decision_email_write
from .information_confirmation import declaration


def recipient_for(application):
    report = declaration(application) or {}
    provided = report.get('applicant_email', '') if isinstance(report, dict) else ''
    provided = provided.strip() if isinstance(provided, str) else ''
    address = provided or (application.member.email or '').strip()
    source = 'application' if provided else 'registration' if address else ''
    if not address:
        return '', source, 'missing'
    try:
        validate_email(address)
    except ValidationError:
        # A bad application address must not silently select a different person.
        return '', source, 'invalid'
    return address, source, ''


def queue_decision_email(application, *, outcome, remarks, user):
    """Called inside the locked eligibility transaction; one job per saved version."""
    recipient, source, skipped = recipient_for(application)
    configuration = ReferralSettings.objects.filter(pk=1).first()
    label = dict(ApplicationDecisionEmail._meta.get_field('outcome').choices)[outcome]
    subject = ' '.join(f'{label} — {application.program.name}'.split())[:250]
    body = render_to_string('programs/decision_email.txt', {
        'application': application, 'outcome': outcome, 'label': label, 'remarks': remarks,
    })
    with decision_email_write():
        job = ApplicationDecisionEmail.objects.create(application=application,
            application_version=application.version, outcome=outcome, remarks=remarks,
            recipient=recipient, recipient_source=source, skip_reason=skipped,
            sender=configuration.sender_email if configuration else '', subject=subject, body=body,
            requested_by=user, requested_by_label=user.get_username(),
            state='skipped' if skipped else 'queued')
    if not skipped:
        transaction.on_commit(partial(deliver_decision_email, job.pk), robust=True)
    return job


@sensitive_variables()
def deliver_decision_email(identifier):
    # Commit the claim before SMTP: duplicate callbacks cannot send the same job.
    from .models import ProgramApplication
    application_id = ApplicationDecisionEmail.objects.values_list('application_id', flat=True).get(pk=identifier)
    with transaction.atomic(), decision_email_write():
        application = ProgramApplication.objects.select_for_update().get(pk=application_id)
        job = ApplicationDecisionEmail.objects.select_for_update().get(pk=identifier)
        if job.state != 'queued':
            return False
        if job.application_version != application.version:
            job.state, job.skip_reason = 'skipped', 'superseded'
            job.save(update_fields=['state', 'skip_reason'])
            return False
        job.state = 'sending'
        job.attempt_count += 1
        job.last_attempt_at = timezone.now()
        job.save(update_fields=['state', 'attempt_count', 'last_attempt_at'])
        number = job.attempt_count
    error_type = ''
    try:
        configuration = ReferralSettings.objects.filter(pk=1).first()
        if not configuration or not job.sender or configuration.sender_email.casefold() != job.sender.casefold():
            raise EmailConnectionRequired('Connect the saved Association sender before sending.')
        backend, options = transport_for(configuration)
        with transaction.atomic(), decision_email_write():
            claimed = ApplicationDecisionEmail.objects.select_for_update().get(pk=identifier)
            claimed.backend = backend
            claimed.save(update_fields=['backend'])
        connection = get_connection(backend=backend, **options)
        message = EmailMessage(subject=job.subject, body=job.body,
            from_email=f'Santolan PWD Association <{job.sender}>', to=[job.recipient],
            reply_to=[job.sender], connection=connection,
            headers={'Message-ID': f'<eligibility-{job.pk}@{job.sender.rsplit("@", 1)[-1]}>'})
        send_message(message)
    except Exception as error:
        error_type = type(error).__name__[:100]
    with transaction.atomic(), decision_email_write():
        current = ApplicationDecisionEmail.objects.select_for_update().get(pk=identifier)
        if current.state != 'sending' or current.attempt_count != number:
            return False
        # This retained schema has no "uncertain" state. The immutable attempt's
        # EmailDeliveryUnconfirmed marker supplies the warning in every mail UI;
        # a callback cannot retry either kind of failed attempt automatically.
        current.state = 'failed' if error_type else 'sent'
        current.accepted_at = None if error_type else timezone.now()
        current.save(update_fields=['state', 'accepted_at'])
        ApplicationDecisionEmailAttempt.objects.create(email=current, number=number,
            outcome='failed' if error_type else 'accepted', error_type=error_type)
    return not error_type


def retry_available(job, application):
    stale = job.state == 'sending' and job.last_attempt_at and job.last_attempt_at < timezone.now() - timedelta(minutes=5)
    return (job.application_version == application.version
            and (job.state in ('failed', 'queued') or bool(stale)))


@transaction.atomic
def retry_decision_email(identifier, *, application_id, user, confirmed):
    from .models import ProgramApplication, ProgramLog
    from .review_services import DIRECT_REVIEW_PERMISSIONS
    require_workspace_permissions(user, *DIRECT_REVIEW_PERMISSIONS)
    if confirmed is not True:
        raise ValidationError('Confirm that you want to retry this email.')
    application = ProgramApplication.objects.select_for_update().get(pk=application_id)
    with decision_email_write():
        job = ApplicationDecisionEmail.objects.select_for_update().get(pk=identifier, application=application)
        if not retry_available(job, application):
            raise ValidationError('This email was already accepted, is still sending, or belongs to an earlier application decision.')
        # A decision saved before any sender was configured may use its first
        # connected sender on retry. Existing sender/recipient snapshots stay fixed.
        if not job.sender:
            configuration = ReferralSettings.objects.filter(pk=1).first()
            if not configuration:
                raise ValidationError('Connect the Association email account before retrying.')
            job.sender = configuration.sender_email
            job.save(update_fields=['sender'])
        job.state = 'queued'
        job.save(update_fields=['state'])
        ProgramLog.objects.create(program_id=application.program_id, application=application,
            actor=user, actor_label=user.get_username(), action='decision_email_retry',
            notes='Administrator requested another delivery attempt for the saved eligibility email.',
            changes={'email_id': str(job.pk), 'outcome': job.outcome})
        transaction.on_commit(partial(deliver_decision_email, job.pk), robust=True)


def notification_context(application, user):
    from .review_services import DIRECT_REVIEW_PERMISSIONS
    if not user.has_perms(DIRECT_REVIEW_PERMISSIONS):
        return {}
    recipient, source, skipped = recipient_for(application)
    job = application.decision_emails.first()
    from assistance.referral_mail import delivery_label, local_delivery
    label = delivery_label(job) if job else ''
    return {'decision_email_recipient': recipient, 'decision_email_source': source,
            'decision_email_skip_reason': skipped, 'decision_email': job,
            'decision_email_label': label,
            'decision_email_is_local': bool(job and local_delivery(job)),
            'decision_email_help': delivery_help(job),
            'decision_email_unconfirmed': delivery_unconfirmed(job),
            'can_retry_decision_email': bool(job and retry_available(job, application))}
