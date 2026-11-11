"""Independent PDAO intake, private receipts, printing and manual forwarding."""
from datetime import datetime, timedelta, timezone as datetime_timezone
from uuid import UUID, uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import F, JSONField, OuterRef, Subquery, TextField
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Coalesce
from django.http import Http404
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from accounts.backends import reserve_windows
from .models import SubmissionWindow
from .pdao_forms import (PDAOOnlineForm, PDAOOnsiteForm, PDAOForwardForm, PDAOReviewForm,
                         PRIVACY_VERSION, ONSITE_PRIVACY_VERSION)
from .pdao_models import PDAORegistration, PDAORegistrationEvent, PDAORegistrationRevision
from .registration_models import registration_write
from .registration_policy import RegistrationUnavailable, digest

VIEW = 'membership.view_pdaoregistration'
PRINT = 'membership.print_pdaoregistration'
FORWARD = 'membership.forward_pdaoregistration'
CORRECT = 'membership.correct_pdaoregistration'
ADD = 'membership.add_pdaoregistration'
CONTEXT_KEY = 'pdao_registration_context'
RECEIPT_KEY = 'pdao_registration_receipt'
LIFETIME = 3600
SALT = 'membership.pdao.submit.v1'


def require_enabled():
    if not getattr(settings, 'PDAO_REGISTRATION_ENABLED', False):
        raise RegistrationUnavailable


def binding_for(request):
    if not request.session.session_key:
        request.session.create()
    return salted_hmac('pdao.registration.session', request.session.session_key, algorithm='sha256').hexdigest()


def reserve_attempt(request):
    binding = binding_for(request)
    limits = {
        salted_hmac('pdao.address', request.META.get('REMOTE_ADDR', ''), algorithm='sha256').hexdigest(): 120,
        salted_hmac('pdao.attempt', binding, algorithm='sha256').hexdigest(): 40,
    }
    if not reserve_windows(limits, window_seconds=900, window_model=SubmissionWindow):
        raise PermissionDenied('Too many attempts. Please try again later.')


def issue_token(request, *, onsite=False):
    actor = require_staff(request.user, ADD) if onsite else None
    key = str(uuid4())
    request.session[CONTEXT_KEY + ('.onsite' if onsite else '')] = key
    if not onsite:
        request.session.pop(RECEIPT_KEY, None)
    context = {'key': key, 'binding': binding_for(request),
        'privacy': ONSITE_PRIVACY_VERSION if onsite else PRIVACY_VERSION,
        'expires': int((timezone.now() + timedelta(seconds=LIFETIME)).timestamp())}
    if onsite:
        context['actor'] = actor.pk
    return signing.dumps(context, salt=SALT + ('.onsite' if onsite else ''))


def token_context(request, token, *, onsite=False):
    try:
        context = signing.loads(token, salt=SALT + ('.onsite' if onsite else ''), max_age=LIFETIME)
        key = UUID(context['key'])
        expires = datetime.fromtimestamp(context['expires'], datetime_timezone.utc)
        if (str(key) != request.session.get(CONTEXT_KEY + ('.onsite' if onsite else '')) or expires <= timezone.now()
                or context['privacy'] != (ONSITE_PRIVACY_VERSION if onsite else PRIVACY_VERSION)
                or (onsite and context.get('actor') != request.user.pk)
                or not constant_time_compare(context['binding'], binding_for(request))):
            raise ValueError
    except (signing.BadSignature, KeyError, TypeError, ValueError, OverflowError):
        raise PermissionDenied('This form session has expired. Open a new form.') from None
    return key, expires


def record_event(registration, action, actor=None, *, details=None):
    return PDAORegistrationEvent.objects.create(registration=registration, action=action,
        actor=actor, actor_label=actor.get_username() if actor else '', version=registration.version,
        details=details or {})


def submit(request, *, onsite=False):
    actor = require_staff(request.user, ADD) if onsite else None
    if not onsite:
        require_enabled()
    form = (PDAOOnsiteForm if onsite else PDAOOnlineForm)(request.POST, request.FILES)
    if not form.is_valid():
        raise ValidationError('Correct the form before submitting.')
    key, expires = token_context(request, form.cleaned_data['submission_token'], onsite=onsite)
    data = form.submitted_data()
    payload_digest = digest(data)
    binding = binding_for(request)

    def existing_submission():
        existing = PDAORegistration.objects.filter(submission_key=key).first()
        if existing is not None and (existing.payload_digest != payload_digest or existing.binding_digest != binding
                                     or (not onsite and (existing.receipt_revoked_at or existing.receipt_expires_at <= timezone.now()))):
            raise ValidationError('This form was already submitted. Use your receipt or contact the Help Desk.')
        return existing

    existing = existing_submission()
    if existing:
        return existing
    try:
        with transaction.atomic(), registration_write():
            registration = PDAORegistration.objects.create(submission_key=key, data=data,
                payload_digest=payload_digest, privacy_version=ONSITE_PRIVACY_VERSION if onsite else PRIVACY_VERSION,
                binding_digest=binding, receipt_expires_at=expires,
                receipt_revoked_at=timezone.now() if onsite else None)
            record_event(registration, 'onsite_submitted' if onsite else 'submitted', actor)
            if onsite:
                require_staff(actor, ADD)
            return registration
    except IntegrityError:
        # Concurrent retries of the same nonce must never create two records.
        existing = existing_submission()
        if existing:
            return existing
        raise


def receipt_for(request):
    require_enabled()
    try:
        key = UUID(str(request.session.get(RECEIPT_KEY, '')))
    except ValueError:
        raise Http404 from None
    registration = PDAORegistration.objects.filter(pk=key, binding_digest=binding_for(request),
        receipt_revoked_at__isnull=True, receipt_expires_at__gt=timezone.now()).first()
    if registration is None:
        raise Http404
    return registration


def finish(request):
    key = request.session.get(RECEIPT_KEY)
    if key:
        with transaction.atomic(), registration_write():
            registration = PDAORegistration.objects.select_for_update().filter(pk=key,
                binding_digest=binding_for(request), receipt_revoked_at__isnull=True).first()
            if registration:
                registration.receipt_revoked_at = timezone.now()
                registration.save(update_fields=['receipt_revoked_at'])
    request.session.pop(RECEIPT_KEY, None)
    request.session.pop(CONTEXT_KEY, None)


def require_staff(user, capability=VIEW):
    # Closing public intake must not hide already retained submissions from staff.
    actor = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    if not (actor and actor.is_active and actor.is_staff
            and actor.has_perms(['accounts.access_dashboard', VIEW, capability])):
        raise PermissionDenied
    return actor


def review_records():
    latest = PDAORegistrationRevision.objects.filter(registration_id=OuterRef('pk')).order_by('-version')
    return PDAORegistration.objects.annotate(
        _review_data=Coalesce(Subquery(latest.values('data')[:1]), F('data'), output_field=JSONField()),
        # Extract JSON text from each column before coalescing: MySQL's ->>
        # operator accepts columns, not a COALESCE expression as its left side.
        _review_name=Coalesce(Subquery(latest.annotate(name=KeyTextTransform('full_name', 'data')).values('name')[:1]),
            KeyTextTransform('full_name', 'data'), output_field=TextField()))


def correct(key, user, data, files=None):
    with transaction.atomic(), registration_write():
        actor = require_staff(user, CORRECT)
        registration = PDAORegistration.objects.select_for_update().filter(pk=key).first()
        if registration is None:
            raise Http404
        current = registration.current_data
        form = PDAOReviewForm(data, files, initial=current)
        if not form.is_valid():
            raise ValidationError('Correct the highlighted application details before saving.')
        if registration.version != form.cleaned_data['version']:
            raise ValidationError('Another administrator updated this record. Reload before saving.')
        if registration.status == 'forwarded':
            raise ValidationError('This form has already been forwarded to PDAO and cannot be edited.')
        reviewed = form.submitted_data()
        reviewed['acknowledgement'] = registration.data.get('acknowledgement', False)
        reviewed['intake_channel'] = registration.data.get('intake_channel', 'online')
        if reviewed == current:
            return registration
        registration.version += 1
        # A corrected ready form must be reviewed again before forwarding.
        registration.status = PDAORegistration.Status.RECEIVED
        registration.save(update_fields=['status', 'version'])
        PDAORegistrationRevision.objects.create(registration=registration, version=registration.version,
            data=reviewed, actor=actor, actor_label=actor.get_username())
        record_event(registration, 'corrected', actor)
        require_staff(actor, CORRECT)
        return registration


def staff_record(key, user, *, printing=False):
    capability = PRINT if printing else VIEW
    with transaction.atomic(), registration_write():
        actor = require_staff(user, capability)
        registration = PDAORegistration.objects.select_for_update().filter(pk=key).first()
        if registration is None:
            raise Http404
        record_event(registration, 'print_viewed' if printing else 'details_viewed', actor)
        require_staff(actor, capability)
        return registration


def transition(key, user, data):
    form = PDAOForwardForm(data)
    if not form.is_valid():
        raise ValidationError('Confirm the forwarding details before continuing.')
    with transaction.atomic(), registration_write():
        actor = require_staff(user, FORWARD)
        registration = PDAORegistration.objects.select_for_update().filter(pk=key).first()
        if registration is None:
            raise Http404
        if registration.version != form.cleaned_data['version']:
            raise ValidationError('Another administrator updated this record. Reload before continuing.')
        status = form.cleaned_data['action']
        online = registration.data.get('intake_channel', 'online') == 'online'
        allowed = [('received', 'ready'), ('ready', 'forwarded')]
        if online:
            allowed += [('received', 'needs_info'), ('ready', 'needs_info'), ('needs_info', 'ready')]
        if (registration.status, status) not in allowed:
            raise ValidationError('This action is not available for the current processing status.')
        details = {}
        if online and status in ('ready', 'needs_info'):
            from .prpwd import registry_url
            from .pdao_email import queue_review_email, validate_recipient
            current = registration.current_data
            validate_recipient(current)
            number = (current.get('pwd_number') or '').strip()
            if number:
                url = registry_url()
                if not url:
                    raise ValidationError('Configure the official PRPWD verification link before recording a result.')
                if form.cleaned_data.get('prpwd_lookup_number') != number:
                    raise ValidationError('Open PRPWD and check the saved PWD number before recording a result.')
                details = {'pwd_number': number, 'registry_url': url,
                    'manual_result': 'verified' if status == 'ready' else 'needs_information'}
            else:
                details = {'manual_result': 'no_existing_number_provided'}
            if status == 'needs_info':
                details['reason'] = form.cleaned_data['reason']
        registration.status = status
        registration.version += 1
        registration.save(update_fields=['status', 'version'])
        record_event(registration, status, actor, details=details)
        if online and status in ('ready', 'needs_info'):
            queue_review_email(registration, user=actor, reason=form.cleaned_data.get('reason', '') if status == 'needs_info' else '')
        require_staff(actor, FORWARD)
        return registration
