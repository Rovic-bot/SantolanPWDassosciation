"""Reasoned pending notices: an audited message, never a membership decision."""
from functools import partial

from django import forms
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
from .forms import StyledForm
from .pending_email_models import MembershipPendingEmail as Email, MembershipPendingEmailAttempt as Attempt
from .registration_models import RegistrationIntake, registration_write
from . import registration_services as registration


class PendingEmailForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.CharField(label='Reason for leaving this application pending', max_length=2000,
        widget=forms.Textarea(attrs={'rows': 5, 'placeholder': 'Explain what is missing and what the applicant needs to do next.'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


def pending(intake):
    return not intake.membership_application_id or intake.membership_application.status == 'pending'


def deliver_pending_email(identifier):
    return deliver_membership_email(identifier, Email, Attempt, message_prefix='membership-pending', pending_only=True)


def send_pending_email(reference, *, user, version, request_key, reason):
    return _send_review_email(reference, user=user, version=version, request_key=request_key, reason=reason)


@transaction.atomic
def _send_review_email(reference, *, user, version, request_key, reason, office_invitation=False,
                       prpwd_lookup_number='', prpwd_verified=False):
    from .office_verification import INVITATION_ACTION, current_invitation, required
    actor = registration.require_staff(user, 'membership.decide_membershipapplication')
    # Service callers receive the same validation as the HTTP form.
    form = PendingEmailForm({'version': version, 'request_key': request_key, 'reason': reason})
    if not form.is_valid():
        raise ValidationError('Enter a reason of at most 2,000 characters and reload any expired form.')
    version, request_key, reason = (form.cleaned_data[key] for key in ('version', 'request_key', 'reason'))
    intake = RegistrationIntake.objects.select_for_update().filter(
        reference=registration.normalize_reference(reference), category='association').first()
    if not intake:
        raise Http404
    if not pending(intake):
        raise ValidationError('This application already has a final decision. Reload the review.')
    if office_invitation and not required(intake):
        raise ValidationError('Office invitations are for pending online Association applications.')
    previous = Email.objects.filter(pk=request_key).first()
    if previous:
        was_invitation = intake.actions.filter(action=INVITATION_ACTION, payload__email_id=str(previous.pk)).exists()
        if (previous.intake_id != intake.pk or previous.expected_version != version or previous.reason != reason
                or was_invitation != office_invitation):
            raise ValidationError('This send request was already used. Reload before sending another message.')
        return previous
    if version != intake.version:
        raise ValidationError('Another administrator changed this application. Reload before sending.')
    revision = intake.revisions.get(number=intake.current_revision)
    prpwd_review = None
    if office_invitation:
        existing = current_invitation(intake, revision)
        if existing:
            # Fresh page / concurrent click: reuse the same saved invitation.
            # Failures retry explicitly; uncertain sends never silently resend.
            return existing
        from .office_verification import validate_prpwd_review
        prpwd_review = validate_prpwd_review(revision, user=actor,
            number=prpwd_lookup_number, confirmed=prpwd_verified)
    recipient = (revision.data.get('email') or '').strip()
    try:
        validate_email(recipient)
    except ValidationError:
        raise ValidationError('This application has no valid saved email address. Correct it before sending.')
    configuration = ReferralSettings.objects.filter(pk=1).first()
    with registration_write(), approval_email_write():
        job = Email.objects.create(id=request_key, intake=intake, revision=revision, expected_version=version,
            reason=reason, recipient=recipient, sender=configuration.sender_email if configuration else '',
            subject=('Please visit the barangay office for membership verification' if office_invitation
                     else 'Your Association membership application is pending'),
            body=render_to_string('membership/registration/office_invitation_email.txt' if office_invitation
                                 else 'membership/registration/pending_email.txt', {
                'applicant_name': revision.data['full_name'], 'reference': intake.short_reference, 'reason': reason}),
            requested_by=actor, requested_by_label=actor.get_username())
        intake.version += 1
        intake.save(update_fields=['version'])
        registration.record_action(intake, INVITATION_ACTION if office_invitation else 'pending_email_requested', revision, actor=actor, before=version,
            reason=reason, payload={'email_id': str(job.pk), 'status': 'pending',
                **({'prpwd_review': prpwd_review} if prpwd_review else {})})
        registration.require_staff(actor, 'membership.decide_membershipapplication')
        if office_invitation:
            registration.require_staff(actor, 'membership.verify_membershipapplication')
        transaction.on_commit(partial(deliver_pending_email, job.pk), robust=True)
    return job


@transaction.atomic
def retry_pending_email(reference, *, user, identifier):
    actor = registration.require_staff(user, 'membership.decide_membershipapplication')
    intake = RegistrationIntake.objects.select_for_update().get(reference=reference)
    with registration_write(), approval_email_write():
        job = Email.objects.select_for_update().get(pk=identifier, intake=intake)
        if not pending(intake) or intake.current_revision != job.revision.number:
            raise ValidationError('This application changed. Review its current information before sending another notice.')
        if job.state not in ('queued', 'failed') or job.accepted_at or job.attempts.filter(outcome='accepted').exists():
            raise ValidationError('This message was already accepted or its delivery is unconfirmed. Check Gmail before sending again.')
        if not job.sender:
            configuration = ReferralSettings.objects.filter(pk=1).first()
            if not configuration:
                raise ValidationError('Connect the Association Gmail account before retrying.')
            job.sender = configuration.sender_email
            job.save(update_fields=['sender'])
        job.state = 'queued'
        job.save(update_fields=['state'])
        registration.record_action(intake, 'pending_email_retry', job.revision, actor=actor,
            reason='Administrator retried the saved pending-review email.', payload={'email_id': str(job.pk)})
        transaction.on_commit(partial(deliver_pending_email, job.pk), robust=True)
    return job


def notification_context(intake, user):
    from .office_verification import invitation_ids
    office_ids = {str(identifier) for identifier in invitation_ids(intake)}
    jobs = list(Email.objects.filter(intake=intake)[:10])
    for job in jobs:
        job.delivery_help = delivery_help(job)
        job.is_office_invitation = str(job.pk) in office_ids
        job.delivery_label = ('Saved to test outbox — not sent to an inbox'
            if job.state == 'sent' and local_delivery(job) else job.get_state_display())
        job.can_retry = (pending(intake) and user.has_perm('membership.decide_membershipapplication')
            and intake.current_revision == job.revision.number and job.state in ('queued', 'failed'))
    return {'pending_emails': jobs}
