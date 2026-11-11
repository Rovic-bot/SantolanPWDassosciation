import logging

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from documents.models import MembershipApplicationDocument
from members.models import Member
from ewaf.membership_invalidation import membership_writer, remember_membership_upload
from .forms import PROFILE_FIELDS, STORED_PROFILE_FIELDS
from .models import MembershipApplication, MembershipEvent, MembershipSettings

logger = logging.getLogger(__name__)
QUICK_VERIFICATION_NOTE = 'Administrator confirmed successful manual PRPWD verification.'
QUICK_APPROVAL_NOTE = 'Administrator approved membership after confirming PRPWD.'


@membership_writer('approve_checked')
def approve_checked_application(reference, *, user, version, verified, address=None):
    """Save the admin's manual PRPWD attestation and approval in one transaction."""
    from django.contrib.auth import get_user_model
    actor = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    require_capability(actor, 'membership.verify_membershipapplication')
    require_capability(actor, 'membership.decide_membershipapplication')
    if verified is not True:
        raise ValidationError('Check the PRPWD confirmation before approving.')
    # The outer writer owns one atomic operation, retaining both native audits.
    application = _record_verification(reference, user=actor, version=version,
        verified=True, notes=QUICK_VERIFICATION_NOTE, address=address)
    application = _decide_application(reference, user=actor, version=application.version,
        decision='approved', notes=QUICK_APPROVAL_NOTE, address=address)
    current = get_user_model().objects.get(pk=actor.pk)
    require_capability(current, 'membership.verify_membershipapplication')
    require_capability(current, 'membership.decide_membershipapplication')
    return application


def require_capability(user, capability):
    if not (user and user.is_authenticated and user.is_active and user.is_staff
            and user.has_perms(['accounts.access_dashboard', 'membership.view_membershipapplication', capability])):
        raise PermissionDenied


def record_event(application, action, description, user=None, address=None):
    return MembershipEvent.objects.create(application=application, action=action, description=description,
        actor=user, actor_label=user.get_username() if user else '', address=address or None)


@membership_writer('submit')
def submit_application(form, *, user=None, address=None, registration_reference=None):
    """Commit profile, requirement snapshot, and uploads together; clean up failed file writes."""
    require_capability(user, 'membership.encode_membershipapplication')
    saved_files = []
    try:
        with transaction.atomic():
            policy = MembershipSettings.objects.select_for_update().filter(pk=1).first()
            if not policy or not policy.prpwd_url:
                raise ValidationError('Configure the official PRPWD verification link before onsite registration.')
            from .registration_handoff import lock_handoff, link_handoff, linked_intake
            from .registration_models import RegistrationIntake
            if not registration_reference and RegistrationIntake.objects.filter(
                    request_key=form.cleaned_data['submission_token']).exists():
                raise ValidationError('Use the linked registration review to process this submission.')
            intake = lock_handoff(form, user, registration_reference) if registration_reference else None
            # Serializing against the settings row also makes retry keys idempotent.
            existing = MembershipApplication.objects.filter(submission_key=form.cleaned_data['submission_token']).first()
            if existing:
                linked = linked_intake(existing.pk)
                if linked and (not intake or linked.pk != intake.pk):
                    raise PermissionDenied
                if intake and intake.membership_application_id != existing.pk:
                    raise ValidationError('This submission key is already in use. Review the retained record.')
                return existing
            if intake and intake.membership_application_id:
                raise ValidationError('Open the already linked membership review.')
            application = MembershipApplication.objects.create(
                **{name: form.cleaned_data[name] for name in PROFILE_FIELDS},
                **getattr(form, 'registration_values', {}),
                submission_key=form.cleaned_data['submission_token'], requirements_snapshot=form.snapshot)
            application.disability_types.set(form.cleaned_data['disability_types'])
            for item in form.snapshot:
                upload = form.cleaned_data.get(f'document_{item["id"]}')
                if upload:
                    document = MembershipApplicationDocument(application=application, requirement_id=item['id'],
                        label=item['label'], content_type=upload.content_type, size=upload.size)
                    document.file.save(upload.name, upload, save=False)
                    saved_files.append((document.file.storage, document.file.name))
                    remember_membership_upload(saved_files[-1])
                    document.save()
            record_event(application, 'onsite_encoded', 'Onsite membership registration encoded for review.', user, address)
            if intake:
                link_handoff(intake, application, form, user)
            return application
    except Exception:
        for storage, name in saved_files:
            try:
                storage.delete(name)
            except OSError:
                logger.exception('Failed to remove an uncommitted membership upload.')
        raise


def locked_pending(reference, version):
    application = MembershipApplication.objects.select_for_update().get(reference=reference)
    if application.status != MembershipApplication.Status.PENDING:
        raise ValidationError('This application already has a final decision.')
    if application.version != version:
        raise ValidationError('Another review changed this application. Reload the page before continuing.')
    return application


@membership_writer('verify')
def record_verification(reference, *, user, version, verified, notes, address=None):
    return _record_verification(reference, user=user, version=version, verified=verified, notes=notes, address=address)


@transaction.atomic
def _record_verification(reference, *, user, version, verified, notes, address=None):
    require_capability(user, 'membership.verify_membershipapplication')
    application = locked_pending(reference, version)
    from .registration_handoff import guard_linked_review, record_linked_review
    intake = guard_linked_review(application, user, 'membership.verify_membershipapplication')
    policy = MembershipSettings.objects.filter(pk=1).first()
    if not policy or not policy.prpwd_url:
        raise ValidationError('Configure the official PRPWD verification link first.')
    if not isinstance(verified, bool) or not notes.strip():
        raise ValidationError('Record a verification result and notes.')
    application.prpwd_verified = verified
    application.prpwd_verified_by = user
    application.prpwd_verified_at = timezone.now()
    application.verification_notes = notes
    application.verification_url = policy.prpwd_url
    application.version += 1
    application.save()
    record_event(application, 'prpwd_verified' if verified else 'prpwd_not_verified',
                 'Manual PRPWD verification recorded.', user, address)
    record_linked_review(intake, application, user, 'membership_verification', notes)
    return application


@membership_writer('decide')
def decide_application(reference, *, user, version, decision, notes, address=None):
    return _decide_application(reference, user=user, version=version, decision=decision, notes=notes, address=address)


def _decide_application(reference, *, user, version, decision, notes, address=None):
    require_capability(user, 'membership.decide_membershipapplication')
    if decision not in ('approved', 'rejected') or not notes.strip():
        raise ValidationError('Select approval or rejection and provide decision notes.')
    try:
        with transaction.atomic():
            application = locked_pending(reference, version)
            from .registration_handoff import guard_linked_review, record_linked_review
            intake = guard_linked_review(application, user, 'membership.decide_membershipapplication')
            if decision == 'approved':
                from .office_verification import required
                if intake and required(intake):
                    raise ValidationError('Use the Association membership review to check PRPWD and confirm the in-person visit before approval.')
                if application.prpwd_verified is not True or not application.prpwd_verified_at:
                    raise ValidationError('Approval requires a recorded successful manual PRPWD verification.')
                uploaded = {doc.requirement_id: doc for doc in application.documents.all()}
                for item in application.requirements_snapshot:
                    if item['required'] and (item['id'] not in uploaded or not uploaded[item['id']].file.storage.exists(uploaded[item['id']].file.name)):
                        raise ValidationError('A required document is missing. Approval is blocked.')
                member = Member.objects.create(application=application,
                    **{name: getattr(application, name) for name in STORED_PROFILE_FIELDS})
                member.disability_types.set(application.disability_ids)
            application.status = decision
            application.decided_by = user
            application.decided_at = timezone.now()
            application.decision_notes = notes
            application.version += 1
            application.save()
            record_event(application, decision, f'Membership application {decision}.', user, address)
            record_linked_review(intake, application, user, 'membership_' + decision, notes)
            return application
    except IntegrityError as error:
        if error.args[0] != 1062:
            raise
        raise ValidationError('A member with this control number or application already exists. Review the duplicate before deciding.')
