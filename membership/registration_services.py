"""Pending intake operations, deliberately independent of membership/EWAF writers."""
from datetime import timedelta
import hashlib
import logging
from pathlib import Path
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.datastructures import MultiValueDict

from accounts.backends import reserve_windows
from .models import SubmissionWindow
from .registration_forms import RegistrationForm, OnlineRegistrationForm, OnsiteRegistrationForm, OnsiteForm
from .registration_models import (RegistrationSubmissionContext, RegistrationIntake, RegistrationRevision,
                                  RegistrationAttachment, RegistrationAction, registration_write)
from .registration_policy import policy_for, digest, RegistrationUnavailable

logger = logging.getLogger(__name__)
VIEW = 'membership.view_registrationintake'


def require_staff(user, capability=VIEW):
    # A new instance avoids stale permission caches from an earlier page/request.
    actor = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    if not (actor and actor.is_active and actor.is_staff and actor.has_perms([
            'accounts.access_dashboard', 'membership.view_membershipapplication', VIEW, capability])):
        raise PermissionDenied
    policy_for('staff')
    return actor


def binding_for(session_key):
    if not session_key:
        raise PermissionDenied
    return salted_hmac('association.registration.session', session_key).hexdigest()


def reserve_attempt(binding, address, policy):
    keys = {
        salted_hmac('association.registration.address', address or 'unavailable').hexdigest(): policy['address_attempt_limit'],
        salted_hmac('association.registration.attempt', binding).hexdigest(): policy['session_attempt_limit'],
    }
    return reserve_windows(keys, window_seconds=policy['attempt_window_seconds'], window_model=SubmissionWindow)


def issue_context(binding, *, channel='online', user=None):
    if channel not in ('online', 'printed', 'walk_in'):
        raise PermissionDenied
    policy = policy_for('public' if channel == 'online' else 'staff')
    with transaction.atomic(), registration_write():
        actor = require_staff(user, 'membership.encode_registrationintake') if channel != 'online' else None
        return RegistrationSubmissionContext.objects.create(binding_digest=binding, policy_digest=digest(policy),
            channel=channel, actor=actor, expires_at=timezone.now() + timedelta(seconds=policy['context_seconds']))


def _context(context_id, binding, *, user=None, channel='online'):
    try:
        key = UUID(str(context_id))
    except (ValueError, TypeError, AttributeError):
        raise PermissionDenied from None
    context = RegistrationSubmissionContext.objects.select_for_update().filter(pk=key).first()
    policy = policy_for('public' if channel == 'online' else 'staff')
    if (not context or context.channel != channel or context.revoked_at or context.expires_at <= timezone.now()
            or not constant_time_compare(context.binding_digest, binding)
            or not constant_time_compare(context.policy_digest, digest(policy))
            or context.actor_id != (getattr(user, 'pk', None) if channel != 'online' else None)):
        raise PermissionDenied
    if channel != 'online':
        require_staff(user, 'membership.encode_registrationintake')
    return context, policy


def _file_digest(upload):
    value = hashlib.sha256()
    for chunk in upload.chunks():
        value.update(chunk)
    upload.seek(0)
    return value.hexdigest()


def _validated(data, files, policy, *, onsite=False, online=False):
    form_class = OnsiteRegistrationForm if onsite else OnlineRegistrationForm if online else RegistrationForm
    form = form_class(data, files or MultiValueDict(), policy=policy)
    if not form.is_valid():
        raise ValidationError('The submitted form or documents are invalid.')
    payload = form.submitted_data()
    uploads = {slot: form.cleaned_data[slot] for slot in policy['upload_slots'] if form.cleaned_data.get(slot)}
    fingerprints = {slot: {'digest': _file_digest(upload), 'alternative':
        form.cleaned_data.get('civil_alternative', '') if slot == 'civil_document' else ''}
        for slot, upload in uploads.items()}
    return payload, uploads, fingerprints


def record_action(intake, action, revision, *, actor=None, context=None, reason='', before=None, payload=None):
    if actor:
        capabilities = {'received': 'membership.encode_registrationintake',
            'begin_review': 'membership.review_registrationintake',
            'request_information': 'membership.review_registrationintake',
            'ready_for_onsite': 'membership.onsite_registrationintake',
            'presented_printout': 'membership.onsite_registrationintake',
            'correction_recorded': 'membership.correct_registrationintake',
            'onsite_observations': 'membership.onsite_registrationintake',
            'membership_handoff': 'membership.encode_membershipapplication',
            'membership_verification': 'membership.verify_membershipapplication',
            'membership_approved': 'membership.decide_membershipapplication',
            'membership_rejected': 'membership.decide_membershipapplication',
            'registration_approved': 'membership.decide_membershipapplication',
            'registration_rejected': 'membership.decide_membershipapplication',
            'approval_email_retry': 'membership.decide_membershipapplication',
            'pending_email_requested': 'membership.decide_membershipapplication',
            'office_verification_email_requested': 'membership.decide_membershipapplication',
            'office_information_verified': 'membership.decide_membershipapplication',
            'pending_email_retry': 'membership.decide_membershipapplication',
            'staff_form_viewed': VIEW, 'staff_completed_form_viewed': VIEW,
            'private_document_downloaded': 'membership.view_registration_documents'}
        if action not in capabilities:
            raise PermissionDenied
        # Recheck after lock waits/file operations, not just when the form opened.
        # A failure rolls back the operation and prevents protected delivery.
        actor = require_staff(actor, capabilities[action])
        if action == 'membership_handoff':
            from .registration_handoff import require_handoff_actor
            actor = require_handoff_actor(actor)
        elif action.startswith('membership_'):
            actor = require_staff(actor, 'membership.review_registrationintake')
    return RegistrationAction.objects.create(intake=intake, action=action, revision=revision,
        actor=actor, actor_label=actor.get_username() if actor else '', context=context,
        version_before=intake.version if before is None else before, version_after=intake.version,
        reason=reason, payload=payload or {})


def _save_files(revision, uploads, fingerprints, saved, previous=None):
    previous = previous or {}
    for slot, upload in uploads.items():
        attachment = RegistrationAttachment(revision=revision, slot=slot,
            alternative=fingerprints[slot]['alternative'], original_name=Path(upload.name).name[:255],
            content_type=upload.content_type, size=upload.size, digest=fingerprints[slot]['digest'],
            predecessor=previous.get(slot))
        attachment.file.save(upload.name, upload, save=False)
        saved.append((attachment.file.storage, attachment.file.name))
        attachment.save()


def _cleanup(saved):
    for storage, name in saved:
        try:
            storage.delete(name)
        except Exception:
            # Random storage key only. Restricted operators can retry orphan cleanup;
            # never log applicant content, original filenames, or submitted fields.
            logger.error('Uncommitted private registration object needs cleanup: %s', name)


def submit_registration(context_id, binding, data, files=None, *, user=None, channel='online'):
    if channel not in ('online', 'printed', 'walk_in'):
        raise PermissionDenied
    policy = policy_for('public' if channel == 'online' else 'staff')
    payload, uploads, fingerprints = _validated(data, files, policy, onsite=channel != 'online', online=channel == 'online')
    payload_digest = digest({'data': payload, 'files': fingerprints, 'policy': digest(policy)})
    saved = []
    try:
        with transaction.atomic(), registration_write():
            context, policy = _context(context_id, binding, user=user, channel=channel)
            actor = require_staff(user, 'membership.encode_registrationintake') if channel != 'online' else None
            existing = RegistrationIntake.objects.filter(context=context).first()
            if existing:
                if not constant_time_compare(existing.payload_digest, payload_digest):
                    raise ValidationError('This request was already accepted with different information. Contact authorized staff.')
                return existing
            intake = None
            for _ in range(policy['reference_attempt_limit']):
                reference = f'AMR-{uuid4()}'
                try:
                    with transaction.atomic():
                        intake = RegistrationIntake.objects.create(reference=reference, context=context,
                            request_key=context.request_key, payload_digest=payload_digest, channel=channel,
                            policy_snapshot=policy)
                    break
                except IntegrityError:
                    if not RegistrationIntake.objects.filter(reference=reference).exists():
                        raise
            if intake is None:
                raise ValidationError('The request could not be accepted. Please try again later.')
            revision = RegistrationRevision.objects.create(intake=intake, number=1, data=payload, policy_snapshot=policy,
                actor=actor, actor_label=actor.get_username() if actor else '', context=context)
            _save_files(revision, uploads, fingerprints, saved)
            record_action(intake, 'received', revision, actor=actor, context=context)
            return intake
    except Exception:
        _cleanup(saved)
        raise


def normalize_reference(value):
    from core.reference_services import original_reference
    value = original_reference('association', value)
    value = str(value).strip()
    if len(value) != 40 or value[:4].upper() != 'AMR-':
        raise ValidationError('Enter the complete AMR registration reference.')
    try:
        key = UUID(value[4:])
    except ValueError:
        raise ValidationError('Enter the complete AMR registration reference.') from None
    if value[4:].lower() != str(key) or key.version != 4:
        raise ValidationError('Enter the complete AMR registration reference.')
    return f'AMR-{key}'


def _locked(reference, version):
    try:
        reference = normalize_reference(reference)
    except ValidationError:
        raise Http404 from None
    intake = RegistrationIntake.objects.select_for_update().filter(reference=reference, category='association').first()
    if not intake:
        raise Http404
    if type(version) is not int or intake.version != version:
        raise ValidationError('Another review changed this record. Reload before continuing.')
    return intake


def _reason(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 2000:
        raise ValidationError('Record a reason of at most 2000 characters.')
    return value.strip()


def review_registration(reference, *, user, version, action, reason):
    reason = _reason(reason)
    with transaction.atomic(), registration_write():
        actor = require_staff(user, 'membership.review_registrationintake')
        intake = _locked(reference, version)
        transitions = {'begin_review': ({'received'}, 'under_review'),
                      'request_information': ({'under_review', 'ready_for_onsite', 'onsite_review'}, 'needs_information'),
                      'ready_for_onsite': ({'under_review'}, 'ready_for_onsite'),
                      'presented_printout': (set(('received', 'under_review', 'needs_information', 'ready_for_onsite', 'onsite_review')), intake.state)}
        if action not in transitions or intake.state not in transitions[action][0]:
            raise ValidationError('That action is unavailable for the current processing state.')
        if action in ('ready_for_onsite', 'presented_printout'):
            policy_for('onsite')
            actor = require_staff(user, 'membership.onsite_registrationintake')
        if action == 'presented_printout' and intake.channel != 'online':
            raise ValidationError('Only an existing online submission can be matched to its printout.')
        before = intake.version
        intake.state = transitions[action][1]
        intake.version += 1
        intake.save(update_fields=['state', 'version'])
        record_action(intake, action, intake.revisions.get(number=intake.current_revision), actor=actor,
            reason=reason, before=before)
        return intake


def active_attachments(revision):
    return RegistrationAttachment.objects.filter(revision__intake=revision.intake).filter(
        Q(revision=revision) | Q(pk__in=revision.retained_attachment_ids))


def correct_registration(reference, *, user, version, reason, data, files=None):
    policy = policy_for('correction')
    reason = _reason(reason)
    payload, uploads, fingerprints = _validated(data, files, policy)
    saved = []
    try:
        with transaction.atomic(), registration_write():
            actor = require_staff(user, 'membership.correct_registrationintake')
            intake = _locked(reference, version)
            if intake.membership_application_id:
                raise ValidationError('Linked records require a separately authorized correction service.')
            previous = intake.revisions.get(number=intake.current_revision)
            previous_kind = previous.data.get('profile_kind', 'minimal_v1')
            if previous_kind != policy.get('applicant_profile', 'minimal_v1'):
                raise ValidationError('The applicant field contract changed. Retain this submission for authorized reconciliation; no fields were replaced.')
            attachments = {item.slot: item for item in active_attachments(previous)}
            revision = RegistrationRevision.objects.create(intake=intake, number=previous.number + 1,
                predecessor=previous, data=payload, policy_snapshot=policy, actor=actor, actor_label=actor.get_username(), reason=reason,
                retained_attachment_ids=[str(item.pk) for slot, item in attachments.items() if slot not in uploads])
            _save_files(revision, uploads, fingerprints, saved, attachments)
            before = intake.version
            intake.current_revision = revision.number
            intake.version += 1
            intake.state = 'under_review'
            intake.save(update_fields=['current_revision', 'version', 'state'])
            record_action(intake, 'correction_recorded', revision, actor=actor, reason=reason, before=before)
            return intake
    except Exception:
        _cleanup(saved)
        raise


def record_onsite(reference, *, user, data):
    policy = policy_for('onsite')
    form = OnsiteForm(data, policy=policy)
    if not form.is_valid():
        raise ValidationError('Record the permitted onsite observations and reason.')
    with transaction.atomic(), registration_write():
        actor = require_staff(user, 'membership.onsite_registrationintake')
        intake = _locked(reference, form.cleaned_data['version'])
        if intake.state not in ('under_review', 'ready_for_onsite', 'onsite_review'):
            raise ValidationError('Begin review before recording onsite findings.')
        before = intake.version
        intake.state = 'onsite_review'
        intake.version += 1
        intake.save(update_fields=['state', 'version'])
        record_action(intake, 'onsite_observations', intake.revisions.get(number=intake.current_revision),
            actor=actor, reason=form.cleaned_data['reason'], before=before,
            payload={'procedure': policy['onsite_procedure_reference'], 'findings': form.findings()})
        return intake


def receipt_for(context_id, binding):
    with transaction.atomic(), registration_write():
        context, _ = _context(context_id, binding)
        intake = RegistrationIntake.objects.filter(context=context).first()
        if not intake:
            raise PermissionDenied
        original = intake.revisions.get(number=1)
        record_action(intake, 'submitted_form_viewed', original, context=context)
        return intake, original


def revoke_context(context_id, binding):
    # Revocation reduces access only. Expiry, changed policy and collection gates
    # must not prevent the owning session from closing an existing online context.
    # Retain ownership checks even on retries; never accept a public reference.
    try:
        key = UUID(str(context_id))
    except (ValueError, TypeError, AttributeError):
        raise PermissionDenied from None
    if not isinstance(binding, str) or not binding:
        raise PermissionDenied
    with transaction.atomic(), registration_write():
        context = RegistrationSubmissionContext.objects.select_for_update().filter(pk=key).first()
        if (not context or context.channel != 'online' or context.actor_id is not None
                or not constant_time_compare(context.binding_digest, binding)):
            raise PermissionDenied
        intake = RegistrationIntake.objects.filter(context=context).first()
        # Return only the owning session's issued reference for its confirmation
        # screen, including an idempotent retry. This grants no form access.
        reference = intake.reference if intake else None
        if context.revoked_at is not None:
            return reference
        context.revoked_at = timezone.now()
        context.save(update_fields=['revoked_at'])
        if intake:
            record_action(intake, 'submission_context_closed', intake.revisions.get(number=1), context=context)
        return reference


def audit_access(intake, *, user, action, revision=None, attachment=None):
    capability = 'membership.view_registration_documents' if attachment else VIEW
    with transaction.atomic(), registration_write():
        actor = require_staff(user, capability)
        intake = RegistrationIntake.objects.select_for_update().get(pk=intake.pk, category='association')
        if revision is None:
            revision = intake.revisions.get(number=intake.current_revision)
        if revision.intake_id != intake.pk or (attachment and attachment.revision.intake_id != intake.pk):
            raise PermissionDenied
        record_action(intake, action, revision, actor=actor,
            payload={'attachment_id': str(attachment.pk)} if attachment else {})


def handoff_registration(reference=None, *, user=None, form=None, address=None, **writer_options):
    # Enter the established writer at top level. It owns transaction/authority
    # locks and atomically records the link; never wrap it in an intake atomic.
    from .services import submit_application
    from .registration_handoff import handoff_policy
    handoff_policy()
    return submit_application(form, user=user, address=address,
                              registration_reference=reference, **writer_options)
