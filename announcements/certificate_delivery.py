"""Commit a private outbox with publication, then deliver outside that transaction."""
from datetime import timedelta
import hashlib
import logging
from threading import Lock, Thread
import time

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import close_old_connections, transaction
from django.utils import timezone

from programs.decision_email import recipient_for
from programs.terms import terms_lock
from .certificate_models import SelectionCertificateEmail as Email, SelectionCertificateAttempt, certificate_write
from .certificates import certificate_document
from .certificate_pdf import certificate_pdfs
from .models import Announcement
from .certificate_mail import DeliveryFailure, selected_provider, sender_for, send_certificate, setup_problem

logger = logging.getLogger(__name__)
_worker_lock = Lock()
REASONS = {
    'mail_provider': 'Configure Gmail or Resend for certificate delivery.',
    'gmail_setup': 'The Association Gmail account needs to be connected before certificates can be sent.',
    'gmail_connection': 'Could not connect to Gmail. Check the connection and retry.',
    'gmail_rejected': 'Gmail rejected the message. Check the recipient, sender and sending limit before retrying.',
    'gmail_uncertain': 'Check the Gmail Sent folder before any manual resend; delivery was not confirmed and automatic retry is disabled to avoid duplicates.',
    'setup': 'Resend needs an API key and a verified sending domain.',
    'sender': 'Configure a valid Resend sender address.',
    'domain': 'Verify the sending domain in Resend before sending certificates.',
    'missing': 'Add an email address to the member or application record, then retry.',
    'invalid': 'Correct the email address on the application or member record, then retry.',
    'changed': 'Review and publish the current selections before retrying.',
    'api_key': 'Check the Resend API key and its sending permission.',
    'rate_limit': 'Resend limited this request. Retry the pending certificates later.',
    'rejected': 'Resend rejected this email. Check the recipient and sender configuration.',
    'provider': 'Resend could not confirm this request.',
    'connection': 'The email service could not confirm receipt of this request.',
    'response': 'The email service returned no delivery confirmation.',
    'expired': 'Check this email in Resend before any manual resend; automatic retry is disabled to avoid duplicates.',
    'sender_changed': 'Restore the original sender before retrying this saved email.',
}


def queue_certificates(item, *, user):
    """Run inside the publication transaction, with program/member locks held."""
    if not item.program.ewaf_applicable:
        return
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError('Certificate jobs must commit with their publication.')
    payload = item.result_revision.public_payload
    references = {row['reference'] for row in payload['rows']}
    applications = list(item.program.applications.filter(public_reference__in=references)
        .select_related('member').order_by('pk'))
    if len(applications) != len(references):
        raise ValidationError('A selected application could not be matched to its certificate.')
    issued_on = timezone.localdate(item.published_at)
    existing = {job.application_id: job for job in Email.objects.select_for_update()
        .filter(application__in=applications).defer('document', 'body')
        .select_related('application__member').prefetch_related('attempts')}
    pending = [application for application in applications if application.pk not in existing]
    documents = certificate_pdfs([certificate_document(member_name=application.member.full_name,
        program_name=payload['program_name'], issued_on=issued_on) for application in pending])
    with certificate_write():
        # Republishing may resume a safely failed/blocked notification, but never
        # creates a new certificate or replaces a previously submitted payload.
        for job in existing.values():
            queue_retry(job)
        for application, document in zip(pending, documents, strict=True):
            recipient, source, reason = recipient_for(application)
            reason = reason or setup_problem()
            Email.objects.create(application=application, revision=item.result_revision,
                member_name=application.member.full_name, program_name=payload['program_name'],
                issued_on=issued_on, document=document,
                document_sha256=hashlib.sha256(document).hexdigest(),
                recipient=recipient, recipient_source=source, provider=selected_provider(),
                subject=' '.join(f'Certificate of Assistance - {payload["program_name"]}'.split())[:250],
                body=(f'Dear {application.member.full_name},\n\n'
                      f'You have been selected to receive assistance under {payload["program_name"]}. '
                      'Your personalized Certificate of Assistance is attached as a PDF.\n\n'
                      'Please contact the Santolan PWD Association for the assistance schedule and next steps.\n\n'
                      'Santolan PWD Association'),
                requested_by=user, requested_by_label=user.get_username(),
                state='blocked' if reason else 'queued', reason=reason)
    transaction.on_commit(kick_delivery, robust=True)


def delivery_accepted(job):
    """Any retained success is authoritative, even if a queue state is stale."""
    return (job.state == 'sent' or job.accepted_at is not None
            or any(attempt.outcome == 'sent' for attempt in job.attempts.all()))


def retryable(job):
    if delivery_accepted(job):
        return False
    if job.provider == 'gmail' and job.acceptance_unknown:
        return False
    if job.state == 'sending' and job.last_attempt_at > timezone.now() - timedelta(minutes=5):
        return False
    if job.acceptance_unknown and job.first_attempt_at <= timezone.now() - timedelta(hours=23):
        return False
    return True


def queue_retry(job):
    """Caller holds the job/program locks and certificate write context."""
    if not retryable(job) or setup_problem(job.provider):
        return False
    if job.state == 'queued':
        return True
    fields = ['state', 'reason']
    if not job.attempt_count:
        job.recipient, job.recipient_source, reason = recipient_for(job.application)
        fields.extend(['recipient', 'recipient_source'])
        if reason:
            job.state, job.reason = 'blocked', reason
            job.save(update_fields=fields)
            return False
    job.state, job.reason = 'queued', ''
    job.save(update_fields=fields)
    return True


def selected_in_published_results(job):
    from .results import results_current
    item = Announcement.objects.select_related('program', 'result_revision').filter(
        program_id=job.application.program_id, status='published').first()
    return bool(item and item.result_revision and results_current(item)
        and any(row['reference'] == job.application.public_reference
                for row in item.result_revision.public_payload.get('rows', [])))


@terms_lock()
@transaction.atomic
def retry_certificates(program_id, *, user):
    from .generation import publisher
    from .results import lock_program
    from .services import record_event
    user = publisher(user)
    program = lock_program(program_id)
    if not program.ewaf_applicable:
        raise ValidationError('Certificate emails are not sent for non-EWAF programs.')
    item = Announcement.objects.select_for_update().filter(program=program, status='published').first()
    if not item:
        raise ValidationError('Publish the recorded selections before retrying certificates.')
    queued = 0
    with certificate_write():
        for job in Email.objects.select_for_update().filter(application__program=program).select_related(
                'application__member').prefetch_related('attempts'):
            if not retryable(job) or setup_problem(job.provider) or not selected_in_published_results(job):
                continue
            queued += queue_retry(job)
    if queued:
        record_event(item, user, 'certificates_retried',
            f'Administrator queued {queued} pending selection certificate emails for another attempt.', None)
        transaction.on_commit(kick_delivery, robust=True)
    return queued


def deliver_certificate(identifier):
    from .results import lock_program
    program_id = Email.objects.values_list('application__program_id', flat=True).get(pk=identifier)
    with terms_lock(), transaction.atomic(), certificate_write():
        program = lock_program(program_id)
        if not program.ewaf_applicable:
            return False
        job = Email.objects.select_for_update().select_related('application').get(pk=identifier)
        if job.state != 'queued' or delivery_accepted(job):
            return False
        reason = setup_problem(job.provider)
        if not reason and not selected_in_published_results(job):
            reason = 'changed'
        if job.acceptance_unknown and not retryable(job):
            reason = 'gmail_uncertain' if job.provider == 'gmail' else 'expired'
        if job.sender and job.sender.casefold() != sender_for(job.provider).casefold():
            reason = reason or 'sender_changed'
        if reason:
            job.state, job.reason = 'blocked', reason
            job.save(update_fields=['state', 'reason'])
            return False
        if not job.recipient:
            job.state, job.reason = 'blocked', 'missing'
            job.save(update_fields=['state', 'reason'])
            return False
        if not job.sender:
            from assistance.referral_models import ReferralSettings
            configuration = ReferralSettings.objects.filter(pk=1).first()
            job.sender = sender_for(job.provider)
            job.reply_to = configuration.sender_email if configuration else ''
        previous_unknown = job.acceptance_unknown
        job.state, job.reason, job.acceptance_unknown = 'sending', '', True
        job.attempt_count += 1
        job.last_attempt_at = timezone.now()
        job.first_attempt_at = job.first_attempt_at or job.last_attempt_at
        job.save(update_fields=['sender', 'reply_to', 'state', 'reason', 'acceptance_unknown',
                                'attempt_count', 'last_attempt_at', 'first_attempt_at'])
        number = job.attempt_count
    failure, provider_id = None, ''
    try:
        provider_id = send_certificate(job)
    except DeliveryFailure as error:
        failure = error
    except Exception:
        # A transport interruption can occur after provider acceptance. Never
        # infer failure or expose diagnostics containing private message data.
        failure = DeliveryFailure('gmail_uncertain' if job.provider == 'gmail' else 'connection', uncertain=True)
    with transaction.atomic(), certificate_write():
        current = Email.objects.select_for_update().get(pk=identifier)
        if current.state != 'sending' or current.attempt_count != number:
            return False
        current.acceptance_unknown = bool(failure and (failure.uncertain or previous_unknown))
        current.state = ('uncertain' if current.acceptance_unknown else 'failed') if failure else 'sent'
        current.reason = failure.code if failure else ''
        current.accepted_at = None if failure else timezone.now()
        current.provider_id = provider_id
        current.save(update_fields=['state', 'reason', 'accepted_at', 'provider_id', 'acceptance_unknown'])
        SelectionCertificateAttempt.objects.create(email=current, number=number,
            outcome=current.state, error_code=current.reason)
    return not failure


def deliver_pending(*, limit=None):
    """Also callable by a scheduled management command after a server restart."""
    identifiers = Email.objects.filter(state='queued', application__program__ewaf_applicable=True).order_by('created_at').values_list('pk', flat=True)
    if limit is not None:
        identifiers = identifiers[:limit]
    count = 0
    for identifier in list(identifiers):
        deliver_certificate(identifier)
        count += 1
        # Attachments require individual /emails requests. Respect the usual
        # Resend two-request/second limit; 429 responses remain retryable.
        time.sleep(.6)
    return count


def kick_delivery():
    if setup_problem() or not settings.CERTIFICATE_EMAIL_BACKGROUND:
        return

    def work():
        with _worker_lock:
            close_old_connections()
            try:
                deliver_pending()
            except Exception:
                logger.error('Certificate worker stopped; saved jobs remain available for retry.')
            finally:
                close_old_connections()

    Thread(target=work, name='selection-certificates', daemon=True).start()


def certificate_context(program, user):
    from .generation import PERMISSIONS
    if not program or not user.has_perms(PERMISSIONS):
        return {}
    jobs = list(Email.objects.filter(application__program=program).defer('document', 'body')
                .select_related('application').prefetch_related('attempts'))
    for job in jobs:
        job.delivery_label = f'Accepted by {job.get_provider_display()}' if delivery_accepted(job) else job.get_state_display()
        expired = 'gmail_uncertain' if job.provider == 'gmail' else 'expired'
        job.explanation = REASONS.get(expired if job.acceptance_unknown and not retryable(job)
                                     and job.state != 'sending' else job.reason, '')
    return {'certificate_jobs': jobs, 'certificate_total': len(jobs),
            'certificate_emails_enabled': program.ewaf_applicable,
            'certificate_accepted': sum(delivery_accepted(job) for job in jobs),
            'certificate_provider': dict(Email._meta.get_field('provider').choices).get(selected_provider(), 'email service'),
            'certificate_setup': REASONS.get(setup_problem(), '') if program.ewaf_applicable else '',
            'certificate_can_retry': program.ewaf_applicable and any(retryable(job) and not setup_problem(job.provider) for job in jobs)}
