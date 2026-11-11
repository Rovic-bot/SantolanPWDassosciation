"""Owner-authorized onsite edit and decision, with automatic private history.

The current PWD-number form records the administrator's manual PRPWD result
with the membership decision. It never treats opening a link as verification.
"""
from contextlib import contextmanager
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.db.models import Value
from django.db.models.functions import Replace
from django.http import Http404
from django.utils import timezone

from members.models import DisabilityType, Member
from programs.terms import terms_lock
from . import registration_services as registration
from . import services as membership
from .forms import STORED_PROFILE_FIELDS
from .models import MembershipApplication, MembershipEvent
from .pdf_registration_forms import ASSOCIATION_PDF_KIND
from .registration_editor import RegistrationEditorForm
from .registration_models import RegistrationIntake, RegistrationRevision, registration_write
from .registration_policy import available, digest, policy_for
from .registration_profile import PROFILE_KIND

WORKFLOW = 'onsite-prpwd-decision-v2'
ACTIONS = {'approve_registration': 'approved', 'decline_registration': 'rejected'}


def can_edit(user):
    return available('correction') and user.has_perm('membership.correct_registrationintake')


@contextmanager
def decision_scope(user, expected):
    """Keep new-member decisions inside the existing source/authority boundary."""
    from accounts.authority_services import enlisted
    if not enlisted():
        if expected is not None:
            raise PermissionDenied('Source tokens require a registered disposable session.')
        with terms_lock():
            yield user, None
        return
    from ewaf.shared_invalidation import source_fence, finish, audit_history, audit_delta
    with source_fence(user, expected, lambda: []) as (actor, authority, states):
        before = audit_history(MembershipEvent)

        def finalize(application, event, verification_event=None):
            logs = audit_delta(MembershipEvent, before)
            expected_logs = [event] + ([verification_event] if verification_event else [])
            if {log.pk for log in logs} != {log.pk for log in expected_logs}:
                raise ValidationError('MEMBERSHIP_NATIVE_AUDIT_SCOPE')
            log = event
            if (log.application_id != application.pk or log.actor_id != actor.pk
                    or log.actor_label != actor.get_username() or log.action != application.status
                    or log.description != f'Membership application {application.status}.'):
                raise ValidationError('MEMBERSHIP_NATIVE_AUDIT_INVALID')
            if verification_event and (verification_event.application_id != application.pk
                    or verification_event.actor_id != actor.pk
                    or verification_event.actor_label != actor.get_username()
                    or verification_event.action != ('prpwd_verified' if application.prpwd_verified else 'prpwd_not_verified')
                    or verification_event.description != 'Manual PRPWD verification recorded.'):
                raise ValidationError('MEMBERSHIP_NATIVE_VERIFICATION_AUDIT_INVALID')
            finish(states, authority, expected, actor=actor, kind='membership', source_id=application.pk, audits=logs)

        yield actor, finalize


def member_values(source, number):
    """Project equivalent fields while retaining the complete source declaration."""
    blank = MembershipApplication()
    values = {name: getattr(blank, name) for name in STORED_PROFILE_FIELDS}
    values.update(control_number=number, registration_profile=source,
                  birthdate=date.fromisoformat(source['birthdate']))
    for name in ('full_name', 'address', 'contact_number'):
        values[name] = source.get(name, '')
    kind = source.get('profile_kind')
    if kind == ASSOCIATION_PDF_KIND:
        for name in ('first_name', 'middle_name', 'last_name', 'email', 'barangay',
                     'employment_status', 'household_monthly_income', 'household_members'):
            values[name] = source.get(name, getattr(blank, name))
        values.update(municipality=source.get('city', ''), no_middle_name=not source.get('middle_name'),
            disability_information=source.get('disability_type', ''),
            employment_information=source.get('employment_status', '').replace('_', ' '))
        from members.disability_catalog import association_types
        classifications = association_types(source.get('disability_type', ''))
    elif kind == PROFILE_KIND:
        for name in values:
            if name in source and name not in ('birthdate', 'control_number', 'registration_profile'):
                values[name] = source[name]
        classifications = DisabilityType.objects.filter(pk__in=source.get('disability_types', []))
    else:
        classifications = DisabilityType.objects.none()
    return values, list(classifications)


def decide_registration(reference, *, user, data, action, address=None, source_expected=None):
    if action not in ACTIONS:
        raise ValidationError('Choose Approve or Decline.')
    decision = ACTIONS[action]
    try:
        with decision_scope(user, source_expected) as (actor, finalize), registration_write():
            actor = registration.require_staff(actor, 'membership.decide_membershipapplication')
            reference = registration.normalize_reference(reference)
            intake = RegistrationIntake.objects.select_for_update().filter(reference=reference, category='association').first()
            if intake is None:
                raise Http404
            application = (MembershipApplication.objects.select_for_update().get(pk=intake.membership_application_id)
                           if intake.membership_application_id else None)
            previous = intake.revisions.get(number=intake.current_revision)
            form = RegistrationEditorForm(data, revision=previous, version=intake.version,
                editable=can_edit(actor), member_number=application.control_number if application else '')
            if not form.is_valid():
                raise ValidationError('Correct the highlighted registration fields before deciding.')
            version = form.cleaned_data['version']
            number = form.cleaned_data[form.member_number_field]
            number_label = 'PWD No.' if form.uses_pwd_number else 'assigned member number'
            if decision == 'approved' and not number:
                raise ValidationError(f'Enter the {number_label} to approve this registration.')
            payload = form.changed_payload(previous.data)
            request_payload = {'data': payload, 'number': number, 'decision': decision, 'version': version}
            if form.cleaned_data.get('office_verification_confirmed'):
                request_payload['office_verification_confirmed'] = True
            request_digest = digest(request_payload)
            if application and application.status != 'pending':
                proof = intake.actions.filter(action='registration_' + decision).last()
                if proof and application.status == decision and proof.payload.get('request_digest') == request_digest:
                    return intake
                raise ValidationError('This registration already has a final decision. Reload the page.')
            if version != intake.version:
                raise ValidationError('Another administrator changed this registration. Reload before continuing.')
            if application and Member.objects.filter(application=application).exists():
                raise ValidationError('This registration already belongs to an official Member.')
            invitation = None
            if decision == 'approved':
                from .office_verification import require_office_confirmation
                invitation = require_office_confirmation(intake, previous, recipient=payload.get('email'),
                    confirmed=form.cleaned_data.get('office_verification_confirmed', False))
            record_prpwd = form.uses_pwd_number and bool(number)
            verification_url = ''
            if record_prpwd:
                from .prpwd import registry_url
                actor = registration.require_staff(actor, 'membership.verify_membershipapplication')
                verification_url = registry_url()
                if not verification_url:
                    raise ValidationError('Configure the official PRPWD verification link before recording a result.')
            changed = payload != previous.data
            if changed:
                policy_for('correction')
                actor = registration.require_staff(actor, 'membership.correct_registrationintake')
            if decision == 'approved':
                collision = MembershipApplication.objects.filter(status='pending')
                members = Member.objects.all()
                if form.uses_pwd_number:
                    # Formatting does not make a second identity. Keep the ID's
                    # original formatting in storage, including leading zeros.
                    canonical = number.replace('-', '')
                    collision = collision.annotate(number_digits=Replace('control_number', Value('-'), Value(''))).filter(number_digits=canonical)
                    members = members.annotate(number_digits=Replace('control_number', Value('-'), Value(''))).filter(number_digits=canonical)
                else:
                    collision = collision.filter(control_number=number)
                    members = members.filter(control_number=number)
                if application:
                    collision = collision.exclude(pk=application.pk)
                if members.exists() or collision.exists():
                    raise ValidationError(f'That {number_label} is already in use. Check the number before approving.')
            revision = previous
            if changed:
                revision = RegistrationRevision.objects.create(intake=intake, number=previous.number + 1,
                    predecessor=previous, data=payload, policy_snapshot=previous.policy_snapshot,
                    actor=actor, actor_label=actor.get_username(),
                    reason='Administrator corrected the registration before the membership decision.',
                    retained_attachment_ids=[str(item.pk) for item in registration.active_attachments(previous)])
            values, classifications = member_values(payload, number or (application.control_number if application else ''))
            prior_verification = None
            if application is None:
                application = MembershipApplication(submission_key=intake.request_key, requirements_snapshot=[])
            elif changed:
                # Preserve any earlier result as history, without attaching it to
                # corrected identity information or inventing a new verification.
                prior_verification = {'verified': application.prpwd_verified,
                    'by': application.prpwd_verified_by_id,
                    'at': application.prpwd_verified_at.isoformat() if application.prpwd_verified_at else None,
                    'notes': application.verification_notes, 'url': application.verification_url}
                application.prpwd_verified = None
                application.prpwd_verified_by = None
                application.prpwd_verified_at = None
                application.verification_notes = ''
                application.verification_url = ''
            for name, value in values.items():
                setattr(application, name, value)
            if record_prpwd:
                application.prpwd_verified = decision == 'approved'
                application.prpwd_verified_by = actor
                application.prpwd_verified_at = timezone.now()
                application.verification_url = verification_url
                application.verification_notes = (
                    'Administrator confirmed a matching PRPWD record before approving onsite membership.'
                    if decision == 'approved' else
                    'Administrator recorded that PRPWD verification was not confirmed and declined onsite membership.')
            application.status = decision
            application.decided_by = actor
            application.decided_at = timezone.now()
            application.decision_notes = 'Administrator ' + ('approved' if decision == 'approved' else 'declined') + ' the onsite registration.'
            application.version += 1
            application.save()
            application.disability_types.set(classifications)
            if decision == 'approved':
                member = Member.objects.create(application=application,
                    **{name: getattr(application, name) for name in STORED_PROFILE_FIELDS})
                member.disability_types.set(classifications)
            before = intake.version
            intake.membership_application = application
            intake.state = 'membership_review'
            intake.current_revision = revision.number
            intake.version += 1
            intake.save(update_fields=['membership_application', 'state', 'current_revision', 'version'])
            if changed:
                registration.record_action(intake, 'correction_recorded', revision, actor=actor,
                    reason=revision.reason, before=before)
            if decision == 'approved' and form.requires_office_verification:
                registration.record_action(intake, 'office_information_verified', revision, actor=actor,
                    reason='Administrator confirmed the applicant visited the barangay office and verified their information in person.',
                    before=before, payload={'email_id': str(invitation.pk) if invitation else None,
                        'invited_revision': invitation.revision.number if invitation else None,
                        'invitation_sent': bool(invitation)})
            verification_event = (membership.record_event(application,
                'prpwd_verified' if application.prpwd_verified else 'prpwd_not_verified',
                'Manual PRPWD verification recorded.', actor, address) if record_prpwd else None)
            event = membership.record_event(application, decision,
                f'Membership application {decision}.', actor, address)
            registration.record_action(intake, 'registration_' + decision, revision, actor=actor,
                reason=application.decision_notes, before=before,
                payload={'workflow': WORKFLOW, 'request_digest': request_digest,
                    'application_reference': str(application.reference), 'status': decision,
                    'assigned_member_number': application.control_number,
                    'member_number_source': 'pwd_number' if form.uses_pwd_number else 'assigned_member_number',
                    'prior_verification': prior_verification,
                    'prpwd_review': {'verified': application.prpwd_verified,
                        'number': number, 'url': verification_url} if record_prpwd else None})
            # Recheck both capabilities after all writes; failures roll back the
            # correction, native decision, member and audit history together.
            if changed:
                registration.require_staff(actor, 'membership.correct_registrationintake')
            registration.require_staff(actor, 'membership.decide_membershipapplication')
            if record_prpwd:
                registration.require_staff(actor, 'membership.verify_membershipapplication')
            if finalize:
                finalize(application, event, verification_event)
            if decision == 'approved' and intake.channel == 'online':
                from .approval_email import queue_approval_email
                queue_approval_email(intake, revision, user=actor)
            return intake
    except IntegrityError as error:
        if error.args[0] != 1062:
            raise
        raise ValidationError('This registration or member number is already in use. Reload before continuing.') from error
