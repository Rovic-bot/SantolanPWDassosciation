"""Owner-authorized reference lookup of limited application progress only.

This is not identity verification and grants no profile, document or assessment
access. Issued references and the existing status-only projection are retained.
"""
import json
import math
from uuid import UUID

from django.conf import settings
from django.db import OperationalError
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from accounts.backends import reserve_windows
from .models import ProgramApplication, VerificationWindow


SESSION_KEY = 'program_tracking'
VERIFICATION_FAILED = ('We could not find an application with that reference. '
    'Check your application reference number or contact the Association Help Desk.')

# Fetch only reference binding and permitted progress data.
# Documents, assessments, internal notes and snapshots are never loaded here.
RECORD_FIELDS = (
    'reference', 'public_reference', 'status', 'submitted_at', 'program__name',
    'program__status', 'member__archived_at',
)
# Owner-authorized status disclosure only: never include staff notes, scores,
# ranks, evidence or unpublished applicant lists in this projection.
STATUS_MESSAGES = {
    'PENDING_PHOTO_VERIFICATION': (
        'Received', 'Your application has been received and is waiting for initial verification.',
        'Check back for updates while staff verify your application.'),
    'PHOTO_VERIFIED': (
        'Photo verified', 'Your photo has been verified. Your application still needs an eligibility review.',
        'Wait for staff to review your program requirements.'),
    'ELIGIBILITY_REVIEW': (
        'Under review', 'Staff are reviewing your application and program requirements.',
        'Check back for your eligibility decision. Submission does not guarantee selection.'),
    'NEEDS_INFORMATION': (
        'Clarification needed', 'Staff need more information before your application can proceed.',
        'Contact the Association Help Desk to find out what information or clarification is needed.'),
    'VERIFICATION_FAILED': (
        'Verification unsuccessful', 'Your application did not pass verification.',
        'Contact the Association Help Desk for clarification and guidance.'),
    'ELIGIBLE': (
        'You are now eligible', 'You meet the eligibility requirements for this program. Beneficiary selection is still pending.',
        'Wait for the selection update. Being eligible does not guarantee a beneficiary slot.'),
    'INELIGIBLE': (
        'You are not eligible', 'Your application was marked ineligible for this program.',
        'Contact the Association Help Desk for clarification about the eligibility decision.'),
    'EWAF_READY': (
        'You are now eligible', 'Your eligible application is ready for EWAF assessment. Beneficiary selection is still pending.',
        'Wait for assessment and selection updates. Eligibility does not guarantee selection.'),
    'EWAF_PROCESSED': (
        'You are now eligible', 'Your EWAF assessment has been processed. Beneficiary selection is still pending.',
        'Wait for the selection update. Assessment alone does not confirm a beneficiary slot.'),
    'RANKED': (
        'You are now eligible', 'Your application has been ranked. The final beneficiary selection is still pending.',
        'Wait for the selection update. A ranking does not guarantee selection.'),
    'SELECTED': (
        'You have been selected', 'You have been selected for assistance under this program.',
        'Check your email or contact the Association Help Desk for claiming instructions. Selection does not mean assistance has already been released.'),
    'WAITLISTED': (
        'You are on the waitlist', 'Your application is waitlisted. You have not been selected for a beneficiary slot at this time.',
        'Check back for updates. A place on the waitlist does not guarantee selection.'),
    'NOT_SELECTED': (
        'You were not selected', 'Your application was not selected for assistance under this program.',
        'Contact the Association Help Desk if you need clarification. Not being selected is different from being ineligible.'),
    'COMPLETED': (
        'Assistance released', 'Staff have recorded the release of assistance for your application.',
        'Keep your reference for your records. Contact the Association Help Desk if the recorded release needs clarification.'),
    'CLOSED': (
        'Application closed', 'Your application is closed and is no longer being processed.',
        'Contact the Association Help Desk if you need clarification about the closure.'),
}


def reserve_tracking_attempt(reference, address):
    from core.reference_services import original_reference
    reference = original_reference('program', reference) or reference
    limits = {
        salted_hmac('programs.tracking.reference', reference.strip().upper()[:40],
            algorithm='sha256').hexdigest(): settings.PROGRAM_VERIFICATION_MEMBER_LIMIT,
        salted_hmac('programs.tracking.address', address,
            algorithm='sha256').hexdigest(): settings.PROGRAM_VERIFICATION_ADDRESS_LIMIT,
    }
    try:
        return reserve_windows(limits, settings.PROGRAM_VERIFICATION_WINDOW_SECONDS, VerificationWindow)
    except (OperationalError, VerificationWindow.DoesNotExist):
        return False


def identity_fingerprint(record):
    identity = {key: record[key] for key in ('reference', 'public_reference', 'member__archived_at')}
    return salted_hmac('programs.tracking.reference_lookup.v2',
        json.dumps(identity, sort_keys=True, default=str), algorithm='sha256').hexdigest()


def verify_application(data):
    from core.reference_services import original_reference
    reference = original_reference('program', data['reference'])
    record = ProgramApplication.objects.filter(
        public_reference=reference).values(*RECORD_FIELDS).first()
    if not record or record['member__archived_at']:
        return None
    if record['public_reference'].strip().casefold() != reference.casefold():
        return None
    # Inactive applicants can check a prior submission. This grants no
    # eligibility, new application, membership activation or document access.
    return {'application': str(record['reference']), 'identity': identity_fingerprint(record),
        'expires': timezone.now().timestamp() + settings.PROGRAM_TRACKING_GRANT_SECONDS}


def progress_from_grant(grant):
    if not isinstance(grant, dict):
        return None
    try:
        reference = UUID(grant['application'])
        expires = float(grant['expires'])
        if not math.isfinite(expires) or expires <= timezone.now().timestamp():
            return None
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    record = ProgramApplication.objects.filter(pk=reference).values(*RECORD_FIELDS).first()
    if (not record or record['member__archived_at']
            or not isinstance(grant.get('identity'), str)
            or not constant_time_compare(grant['identity'], identity_fingerprint(record))):
        return None
    return progress_summary(record)


def progress_summary(record):
    label, explanation, next_steps = STATUS_MESSAGES.get(record['status'], (
        'Contact the Help Desk',
        'Please contact the Association Help Desk for a processing update.',
        'Keep your application reference ready when requesting an update.'))
    return {'reference': record['public_reference'], 'program_name': record['program__name'],
        'submitted_at': record['submitted_at'], 'status_label': label, 'explanation': explanation,
        'next_steps': next_steps,
        'program_cancelled': record['program__status'] == 'cancelled'}

