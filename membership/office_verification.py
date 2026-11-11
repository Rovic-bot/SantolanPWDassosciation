"""Optional office invitations and required in-person verification for online intakes.

The existing immutable pending-message store retains delivery evidence. A typed,
append-only registration action identifies an office invitation; an ordinary
pending notice (including one with identical wording) is not an office invitation.
The owner's latest workflow permits approval after manual PRPWD and in-person
verification without requiring a successful invitation email first.
"""
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .forms import StyledForm
from .pending_email_models import MembershipPendingEmail

INVITATION_ACTION = 'office_verification_email_requested'
INVITATION_REASON = 'Please visit the barangay office to verify your information with Association staff. Bring your PWD ID and application reference.'


class OfficeInvitationForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    prpwd_lookup_number = forms.CharField(max_length=100, widget=forms.HiddenInput)
    prpwd_verified = forms.BooleanField(
        label='I confirmed this applicant’s PWD number in PRPWD.',
        widget=forms.CheckboxInput(attrs={'form': 'office-invitation-form', 'class': 'form-check-input'}))


def required(intake):
    return intake.category == 'association' and intake.channel == 'online'


def invitation_ids(intake, revision=None):
    actions = intake.actions.filter(action=INVITATION_ACTION)
    if revision is not None:
        actions = actions.filter(revision=revision)
    return list(actions.values_list('payload__email_id', flat=True))


def current_invitation(intake, revision):
    return MembershipPendingEmail.objects.filter(intake=intake, revision=revision,
        pk__in=invitation_ids(intake, revision)).first()


def accepted(job):
    return bool(job and job.state == 'sent' and job.accepted_at
                and job.attempts.filter(outcome='accepted').exists())


def require_office_confirmation(intake, revision, *, recipient, confirmed):
    if not required(intake):
        return None
    if confirmed is not True:
        raise ValidationError('Confirm that the applicant visited the barangay office and their information was verified before approving.')
    try:
        validate_email(recipient or '')
    except ValidationError:
        raise ValidationError('Save a valid email address before approving membership and sending confirmation.')
    job = current_invitation(intake, revision)
    # Link existing delivery evidence only when it belongs to this recipient.
    # An absent, failed or unrelated invitation does not imply a verified visit.
    return job if accepted(job) and job.recipient.casefold() == (recipient or '').strip().casefold() else None


def validate_prpwd_review(revision, *, user, number, confirmed):
    from .registration_services import require_staff
    from .prpwd import registry_url
    require_staff(user, 'membership.verify_membershipapplication')
    url = registry_url()
    saved_number = revision.data.get('pwd_number')
    if not url or not saved_number or number != saved_number or confirmed is not True:
        raise ValidationError('Check the saved PWD number in PRPWD and confirm a matching record before sending the office-verification email. Save any PWD number correction first.')
    return {'number': saved_number, 'url': url, 'verified': True}


def recorded_prpwd_review(intake, revision):
    """An invitation attestation applies only to the same saved revision and URL."""
    from .prpwd import registry_url
    expected = {'number': revision.data.get('pwd_number'), 'url': registry_url(), 'verified': True}
    if not expected['number'] or not expected['url']:
        return None
    for action in intake.actions.filter(action=INVITATION_ACTION, revision=revision):
        if action.payload.get('prpwd_review') == expected:
            return expected
    return None


def send_invitation(reference, *, user, version, request_key, prpwd_lookup_number='', prpwd_verified=False):
    from .pending_email import _send_review_email
    return _send_review_email(reference, user=user, version=version, request_key=request_key,
        reason=INVITATION_REASON, office_invitation=True,
        prpwd_lookup_number=prpwd_lookup_number, prpwd_verified=prpwd_verified)


def delivery_label(job):
    from assistance.referral_mail import local_delivery
    return ('Saved to test outbox — not sent to an inbox'
        if job and job.state == 'sent' and local_delivery(job) else job.get_state_display() if job else '')


def notification_context(intake, revision):
    from core.email_delivery import delivery_help
    if not required(intake):
        return {}
    job = current_invitation(intake, revision)
    return {'office_verification_required': True, 'office_invitation': job,
        'office_invitation_accepted': accepted(job),
        'office_invitation_help': delivery_help(job),
        'office_invitation_label': delivery_label(job)}
