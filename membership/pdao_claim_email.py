"""Explicit, private collection notices for already-forwarded PDAO records."""
from functools import partial
import logging
from threading import Lock, Thread
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import close_old_connections, transaction
from django.db.models import Prefetch
from django.template.loader import render_to_string

from assistance.referral_mail import local_delivery
from assistance.referral_models import ReferralSettings
from .approval_email_models import approval_email_write
from .pdao_email import deliver_review_email
from .pdao_email_models import PDAOReviewEmail as Email
from .pdao_forms import MAX_CLAIM_BATCH
from .pdao_models import PDAORegistration
from .registration_models import registration_write
from . import pdao_services as services

logger = logging.getLogger(__name__)
_worker_lock = Lock()


def claim_recipient(data):
    value = data.get('email')
    recipient = value.strip() if isinstance(value, str) else ''
    try:
        validate_email(recipient)
    except ValidationError:
        return ''
    return recipient


def delivery_label(job):
    return ('Saved to test outbox — not sent to an inbox'
        if job.state == 'sent' and local_delivery(job) else job.get_state_display())


def claim_context(registration, user, jobs):
    notice = next((job for job in jobs if job.outcome == 'claim_ready'), None)
    recipient = claim_recipient(registration.current_data)
    return {'claim_notice': notice, 'claim_recipient': recipient,
        'claim_delivery_label': delivery_label(notice) if notice else '',
        'can_send_claim_notice': registration.status == 'forwarded' and not notice and bool(recipient)
            and user.has_perm(services.FORWARD)}


def claim_records(records, user):
    records = records.prefetch_related(Prefetch('review_emails',
        queryset=Email.objects.filter(outcome='claim_ready').defer('body'), to_attr='claim_notices'))
    # The caller paginates first; do not evaluate the complete inbox here.
    for registration in records:
        registration.claim = claim_context(registration, user, registration.claim_notices)
    return records


def dispatch_claim_emails(identifiers):
    """A committed batch returns promptly; each recipient has a separate message."""
    identifiers = tuple(identifiers)
    if not identifiers:
        return

    def deliver():
        for identifier in identifiers:
            try:
                deliver_review_email(identifier)
            except Exception:
                # Keep the durable job for staff inspection; never blindly retry
                # a message that may already have reached the transport.
                logger.error('PDAO claim delivery stopped for a saved notice; inspect its delivery status.')

    if not getattr(settings, 'PDAO_CLAIM_EMAIL_BACKGROUND', True):
        deliver()
        return

    def work():
        with _worker_lock:
            close_old_connections()
            try:
                deliver()
            finally:
                close_old_connections()

    Thread(target=work, name='pdao-claim-notices', daemon=True).start()


@transaction.atomic
def queue_claim_notices(*, user, selections, confirmed):
    actor = services.require_staff(user, services.FORWARD)
    if confirmed is not True:
        raise ValidationError('Confirm that the selected PWD IDs are ready for collection at the barangay office.')
    if (not isinstance(selections, dict) or not 1 <= len(selections) <= MAX_CLAIM_BATCH
            or any(not isinstance(key, UUID) or type(version) is not int or not 0 <= version <= 2147483647
                   for key, version in selections.items())):
        raise ValidationError(f'Select between 1 and {MAX_CLAIM_BATCH} applications from the forwarded list.')
    # Lock in a stable order. Overlapping batches and duplicate clicks cannot
    # create another claim notice for the same application.
    records = list(PDAORegistration.objects.select_for_update().filter(pk__in=selections).order_by('pk'))
    if len(records) != len(selections):
        raise ValidationError('A selected application is no longer available. Refresh the list before sending.')
    for registration in records:
        if registration.status != 'forwarded' or registration.version != selections[registration.pk]:
            raise ValidationError('A selected application changed or has not been forwarded to PDAO. Refresh the list before sending.')
    existing = set(Email.objects.filter(registration_id__in=selections, outcome='claim_ready')
                   .values_list('registration_id', flat=True))
    pending = [(record, claim_recipient(record.current_data)) for record in records if record.pk not in existing]
    if any(not recipient for _, recipient in pending):
        raise ValidationError('A selected application has no valid saved email address. Refresh the list and review its contact details.')
    configuration = ReferralSettings.objects.filter(pk=1).first()
    identifiers = []
    with approval_email_write(), registration_write():
        for registration, recipient in pending:
            data = registration.current_data
            job = Email.objects.create(registration=registration, expected_version=registration.version,
                outcome='claim_ready', recipient=recipient, sender=configuration.sender_email if configuration else '',
                subject='Your PWD ID is ready for collection at the barangay office',
                body=render_to_string('membership/pdao/claim_email.txt', {
                    'applicant_name': data['full_name'], 'reference': registration.short_reference}),
                requested_by=actor, requested_by_label=actor.get_username())
            services.record_event(registration, 'claim_notice_queued', actor,
                details={'email_id': str(job.pk), 'availability_confirmed': True})
            identifiers.append(job.pk)
        services.require_staff(actor, services.FORWARD)
        if identifiers:
            transaction.on_commit(partial(dispatch_claim_emails, tuple(identifiers)), robust=True)
    return {'queued': len(identifiers), 'already_requested': len(existing)}
