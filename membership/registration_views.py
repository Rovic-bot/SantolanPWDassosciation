"""Default-unavailable Association intake and category-scoped staff access."""
from functools import wraps
from pathlib import Path
from uuid import UUID, uuid4

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_safe, require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin

from accounts.decorators import dashboard_required
from .guidance import membership_guidance, ASSOCIATION_REQUIREMENTS, LEGACY_ASSOCIATION_REQUIREMENTS
from .registration_forms import RegistrationForm, OnlineRegistrationForm, OnsiteRegistrationForm, ReviewForm, OnsiteForm
from .registration_models import RegistrationIntake, RegistrationAttachment, RegistrationSubmissionContext
from .registration_policy import available, policy_for, RegistrationUnavailable
from .registration_receipt import reference_confirmation
from . import registration_services as services
from .forms import VerificationForm, DecisionForm
from .registration_handoff import (HandoffForm, handoff_available, handoff_policy, require_handoff_actor)

CONTEXT_KEY = 'association_registration_context'
CONFIRMATION_KEY = 'association_registration_confirmation_reference'


def gated(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except RegistrationUnavailable:
            return render(request, 'membership/registration/unavailable.html', status=503)
    return wrapped


class RegistrationUploadHandler(FileUploadHandler):
    def __init__(self, request, policy):
        super().__init__(request)
        self.limit = policy['total_max_bytes']
        self.total = 0

    def receive_data_chunk(self, raw_data, start):
        self.total += len(raw_data)
        if self.total > self.limit:
            self.request.upload_limit_exceeded = True
            raise StopUpload(connection_reset=False)
        return raw_data

    def file_complete(self, file_size):
        return None


def _session_binding(request):
    if not request.session.session_key:
        request.session.create()
    return services.binding_for(request.session.session_key)


def _public_attempt(request, policy):
    binding = _session_binding(request)
    if not services.reserve_attempt(binding, request.META.get('REMOTE_ADDR', ''), policy):
        raise PermissionDenied
    return binding


@never_cache
@csrf_exempt
@gated
@require_http_methods(['GET', 'HEAD', 'POST'])
def apply(request):
    # Gate/size check precedes parsing; CSRF is enforced by the inner view after
    # installing the bounded handler. A disabled route does not touch new tables.
    policy = policy_for('public')
    try:
        length = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        raise PermissionDenied from None
    if length < 0 or length > policy['body_max_bytes']:
        return render(request, 'membership/registration/unavailable.html', status=413)
    binding = _public_attempt(request, policy)
    request.upload_handlers.insert(0, RegistrationUploadHandler(request, policy))
    return _apply(request, policy, binding)


@csrf_protect
@sensitive_post_parameters()
def _apply(request, policy, binding):
    if request.method in ('GET', 'HEAD'):
        context = None
        try:
            context_id = UUID(str(request.session.get(CONTEXT_KEY, '')))
            context = RegistrationSubmissionContext.objects.filter(pk=context_id, binding_digest=binding,
                revoked_at__isnull=True, expires_at__gt=timezone.now(), channel='online',
                policy_digest=services.digest(policy)).first()
        except ValueError:
            pass
        if context and RegistrationIntake.objects.filter(context=context).exists():
            return redirect('membership:registration_receipt')
        if context is None:
            context = services.issue_context(binding)
            request.session[CONTEXT_KEY] = str(context.pk)
            # A new applicant on a shared browser must not inherit the previous
            # applicant's confirmation reference.
            request.session.pop(CONFIRMATION_KEY, None)
        form = OnlineRegistrationForm(policy=policy)
        context_id = str(context.pk)
    else:
        context_id = request.POST.get('context_id', '')
        if context_id != request.session.get(CONTEXT_KEY):
            raise PermissionDenied
        form = OnlineRegistrationForm(request.POST, request.FILES, policy=policy)
        if getattr(request, 'upload_limit_exceeded', False):
            form.is_valid()
            form.add_error(None, 'The uploads exceed the approved total limit.')
        elif form.is_valid():
            try:
                services.submit_registration(context_id, binding, request.POST, request.FILES)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                return redirect('membership:registration_receipt')
    return render(request, 'membership/registration/apply.html', {**membership_guidance(),
        'form': form, 'policy': policy, 'context_id': context_id,
        'expires_at': context.expires_at if request.method in ('GET', 'HEAD') else None}, status=400 if form.errors else 200)


@never_cache
@gated
@require_safe
def receipt(request):
    policy = policy_for('public')
    try:
        binding = _public_attempt(request, policy)
        intake, revision = services.receipt_for(request.session.get(CONTEXT_KEY, ''), binding)
    except PermissionDenied:
        # Closed, expired or unavailable receipt access returns to the public
        # membership page. Both responses are uncached; no private data or
        # receipt credentials are passed to the destination.
        return redirect('core:membership')
    # Explicit submitted-form projection: no staff state, reasons, history or files.
    return render(request, 'membership/registration/receipt.html', {
        **reference_confirmation(intake.reference), 'received_at': intake.received_at, 'submitted': revision.data,
        'receipt_requirements': (ASSOCIATION_REQUIREMENTS
            if revision.data.get('profile_kind') == 'association_pdf_v1' else LEGACY_ASSOCIATION_REQUIREMENTS),
        'form_version': revision.policy_snapshot['form_version'],
        'onsite_instructions': revision.policy_snapshot['onsite_instructions']})


@never_cache
@require_POST
@csrf_protect
def finish(request):
    # Only reduce the current session's access. Do not create/rotate a session,
    # issue a context, or consume/reset the ordinary submission/read budgets.
    # Repeated Finish after successful closure is a no-op, even while disabled.
    context_id = request.session.get(CONTEXT_KEY)
    if context_id is not None:
        binding = services.binding_for(request.session.session_key)
        reference = services.revoke_context(context_id, binding)
        request.session.pop(CONTEXT_KEY, None)
        if reference:
            request.session[CONFIRMATION_KEY] = reference
        else:
            request.session.pop(CONFIRMATION_KEY, None)
    # Only a server-confirmed reference is retained, never applicant details or
    # submitted identifiers. Repeating Finish cannot reopen the private form.
    return render(request, 'membership/registration/finished.html',
                  reference_confirmation(request.session.get(CONFIRMATION_KEY, '')))


@never_cache
@dashboard_required
@gated
@require_safe
def inbox(request):
    services.require_staff(request.user)
    from .registration_inbox import inbox_context
    context = inbox_context(request.GET)
    context['can_encode'] = request.user.has_perm('membership.encode_registrationintake')
    return render(request, 'membership/registration/inbox.html', context)


def _find(reference):
    try:
        reference = services.normalize_reference(reference)
    except ValidationError:
        raise Http404 from None
    return get_object_or_404(RegistrationIntake, reference=reference, category='association')


@never_cache
@dashboard_required
@gated
@require_safe
def lookup(request):
    actor = services.require_staff(request.user)
    value = request.GET.get('reference', '').strip()
    error = ''
    if 'reference' in request.GET:
        try:
            intake = _find(value)
        except Http404:
            error = 'No accessible pending application matches that reference. Check the complete AMR reference on the receipt.'
        else:
            application = intake.membership_application
            if application and application.status == 'approved' and actor.has_perm('members.view_member'):
                return redirect('members:detail', pk=application.member.pk)
            return redirect('membership:registration_detail', reference=intake.reference)
    return render(request, 'membership/registration/lookup.html',
                  {'reference_query': value[:40], 'reference_error': error}, status=404 if error else 200)


@never_cache
@dashboard_required
@gated
@require_http_methods(['GET', 'HEAD', 'POST'])
@sensitive_post_parameters()
def detail(request, reference):
    actor = services.require_staff(request.user)
    intake = _find(reference)
    application = intake.membership_application
    from .registration_decisions import ACTIONS, can_edit, decide_registration
    from .registration_editor import RegistrationEditorForm
    revision = intake.revisions.get(number=intake.current_revision)
    can_decide = actor.has_perm('membership.decide_membershipapplication')
    pending = application is None or application.status == 'pending'
    from . import pending_email, office_verification
    office_action = request.method == 'POST' and request.POST.get('action') == 'send_office_invitation'
    office_form = office_verification.OfficeInvitationForm(request.POST if office_action else None,
        initial={'version': intake.version, 'request_key': uuid4()}, auto_id='office_%s')
    pending_action = request.method == 'POST' and request.POST.get('action') == 'send_pending_email'
    pending_form = pending_email.PendingEmailForm(request.POST if pending_action else None,
        initial={'version': intake.version, 'request_key': uuid4()}, auto_id='pending_%s')
    simple_action = request.method == 'POST' and request.POST.get('action') in ACTIONS
    editor_form = RegistrationEditorForm(request.POST if simple_action else None,
        files=request.FILES if simple_action else None, revision=revision, version=intake.version,
        editable=pending and can_decide and can_edit(actor),
        member_number=application.control_number if application else '')
    from .prpwd import registry_url
    prpwd_lookup_url = registry_url()
    saved_prpwd_review = office_verification.recorded_prpwd_review(intake, revision) if office_verification.required(intake) else None
    if saved_prpwd_review and not simple_action:
        editor_form.initial['prpwd_lookup_number'] = saved_prpwd_review['number']
    if office_action:
        editor_form.initial['prpwd_lookup_number'] = request.POST.get('prpwd_lookup_number', '')
    if editor_form.requires_office_verification:
        editor_form.fields['office_verification_confirmed'].widget.attrs['form'] = 'association-review-form'
    lookup = request.session.get('onsite_prpwd_lookup', {})
    if (not simple_action and pending and lookup.get('reference') == intake.reference
            and lookup.get('url') == prpwd_lookup_url
            and lookup.get('number') == revision.data.get('pwd_number')):
        editor_form.initial['prpwd_lookup_number'] = lookup['number']
    if editor_form.uses_pwd_number:
        can_decide = can_decide and actor.has_perm('membership.verify_membershipapplication')
    membership_action = request.POST.get('action') in ('verify_membership', 'decide_membership')
    form = ReviewForm(request.POST if request.method == 'POST' and not membership_action and not pending_action and not office_action else None, initial={'version': intake.version})
    verification_form = VerificationForm(initial={'version': application.version if application else 0}, auto_id='verify_%s')
    decision_form = DecisionForm(initial={'version': application.version if application else 0}, auto_id='decision_%s')
    error_status = 200
    if office_action:
        services.require_staff(request.user, 'membership.decide_membershipapplication')
        if office_form.is_valid():
            try:
                job = office_verification.send_invitation(reference, user=request.user, **office_form.cleaned_data)
            except ValidationError as error:
                office_form.add_error(None, error)
            else:
                job.refresh_from_db()
                messages.success(request, f'Office-verification invitation recorded. Application remains pending. {office_verification.delivery_label(job)}.')
                return redirect('membership:registration_detail', reference=intake.reference)
        error_status = 400
    elif pending_action:
        services.require_staff(request.user, 'membership.decide_membershipapplication')
        if pending_form.is_valid():
            try:
                job = pending_email.send_pending_email(reference, user=request.user, **pending_form.cleaned_data)
            except ValidationError as error:
                pending_form.add_error(None, error)
            else:
                job.refresh_from_db()
                messages.success(request, f'Application remains pending. {job.get_state_display()}.')
                return redirect('membership:registration_detail', reference=intake.reference)
        error_status = 400
    elif simple_action:
        services.require_staff(request.user, 'membership.decide_membershipapplication')
        if editor_form.is_valid():
            try:
                result = decide_registration(reference, user=request.user, data=request.POST,
                    action=request.POST['action'], address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                editor_form.add_error(None, error)
            else:
                approved = result.membership_application.status == 'approved'
                if lookup.get('reference') == intake.reference:
                    request.session.pop('onsite_prpwd_lookup', None)
                messages.success(request, 'Registration approved. The applicant is now a member.' if approved
                    else 'Registration declined. No member record was created.')
                if approved and actor.has_perm('members.view_member'):
                    return redirect('members:detail', pk=result.membership_application.member.pk)
                return redirect('membership:registration_detail', reference=result.reference)
        error_status = 400
    elif request.method == 'POST' and membership_action:
        services.require_staff(request.user, 'membership.review_registrationintake')
        if not application:
            raise PermissionDenied
        from .services import record_verification, decide_application
        verifying = request.POST['action'] == 'verify_membership'
        action_form = VerificationForm(request.POST, auto_id='verify_%s') if verifying else DecisionForm(request.POST, auto_id='decision_%s')
        if verifying:
            verification_form = action_form
        else:
            decision_form = action_form
        if action_form.is_valid():
            try:
                (record_verification if verifying else decide_application)(application.reference,
                    user=request.user, address=request.META.get('REMOTE_ADDR'), **action_form.cleaned_data)
            except ValidationError as error:
                action_form.add_error(None, error)
            else:
                messages.success(request, 'Manual verification saved.' if verifying else 'Membership decision saved.')
                return redirect('membership:registration_detail', reference=intake.reference)
        error_status = 400
    elif request.method == 'POST':
        services.require_staff(request.user, 'membership.review_registrationintake')
        if form.is_valid():
            try:
                services.review_registration(reference, user=request.user, **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Review saved. Membership has not been approved.')
                return redirect('membership:registration_detail', reference=intake.reference)
    revision = intake.revisions.get(number=intake.current_revision)
    from .registration_profile import readonly_submission
    submitted_form = readonly_submission(revision.data, revision.policy_snapshot)
    services.audit_access(intake, user=request.user, action='staff_form_viewed', revision=revision)
    # Suggestions are confined to pending intakes visible to this staff capability.
    # They are not identity matches, merge authority or a public person lookup.
    candidates = RegistrationIntake.objects.filter(category='association', revisions__number=1,
        revisions__data__full_name=revision.data['full_name'], revisions__data__birthdate=revision.data['birthdate']).exclude(pk=intake.pk)
    revisions = list(intake.revisions.all())
    if actor.has_perm('membership.view_registration_documents'):
        for previous in revisions:
            previous.visible_attachments = services.active_attachments(previous)
    from .approval_email import notification_context
    return render(request, 'membership/registration/detail.html', {**membership_guidance(),
        **notification_context(intake, actor),
        **pending_email.notification_context(intake, actor),
        **office_verification.notification_context(intake, revision),
        'office_invitation_form': office_form,
        'saved_prpwd_review': saved_prpwd_review,
        'can_send_office_invitation': pending and actor.has_perms([
            'membership.decide_membershipapplication', 'membership.verify_membershipapplication']),
        'pending_email_form': pending_form, 'pending_email_recipient': revision.data.get('email', ''),
        'intake': intake, 'revision': revision, 'form': form, 'submitted_form': submitted_form, 'candidates': candidates,
        'attachments': services.active_attachments(revision) if actor.has_perm('membership.view_registration_documents') else (),
        'history': intake.actions.select_related('revision'), 'revisions': revisions,
        'can_review': not application and actor.has_perm('membership.review_registrationintake'),
        'can_correct': not application and available('correction') and actor.has_perm('membership.correct_registrationintake'),
        'can_onsite': not application and available('onsite') and actor.has_perm('membership.onsite_registrationintake'),
        'handoff_ready': handoff_available(), 'application': application,
        'handoff_record': intake.actions.filter(action='membership_handoff', revision=revision).first() if application else None,
        'can_prepare': not application and actor.has_perms(['membership.encode_membershipapplication',
            'membership.onsite_registrationintake', 'membership.view_registration_documents',
            'documents.view_membershipapplicationdocument']),
        'can_membership_review': actor.has_perm('membership.review_registrationintake'),
        'editor_form': editor_form, 'registration_pending': pending, 'can_decide': can_decide,
        'approved_with_pwd_number': bool(application and intake.actions.filter(action='registration_approved',
            payload__member_number_source='pwd_number').exists()),
        'verification_form': verification_form, 'decision_form': decision_form,
        'prpwd_lookup_url': prpwd_lookup_url},
        status=400 if not simple_action and form.errors else error_status)


@never_cache
@dashboard_required
@gated
@require_http_methods(['GET', 'HEAD', 'POST'])
@sensitive_post_parameters()
def prepare_membership(request, reference):
    require_handoff_actor(request.user)
    policy = handoff_policy()
    intake = _find(reference)
    if intake.membership_application_id and request.method != 'POST':
        return redirect('membership:registration_detail', reference=intake.reference)
    form = HandoffForm(request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None, intake=intake, policy=policy)
    if request.method == 'POST' and form.is_valid():
        try:
            if getattr(request, 'upload_limit_exceeded', False):
                raise ValidationError('The combined uploads exceed the existing permitted limit.')
            services.handoff_registration(reference, user=request.user, form=form,
                address=request.META.get('REMOTE_ADDR'))
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Onsite acceptance retained. Complete manual verification and the authorized membership decision below.')
            return redirect('membership:registration_detail', reference=intake.reference)
    return render(request, 'membership/registration/handoff.html', {'form': form, 'intake': intake,
        'handoff_policy': policy}, status=400 if form.errors else 200)


@never_cache
@dashboard_required
@gated
@require_http_methods(['GET', 'HEAD', 'POST'])
@sensitive_post_parameters()
def encode(request, channel):
    services.require_staff(request.user, 'membership.encode_registrationintake')
    if channel != 'walk_in':
        raise Http404
    policy = policy_for('staff')
    binding = _session_binding(request)
    if request.method == 'POST':
        context_id = request.POST.get('context_id', '')
        form = OnsiteRegistrationForm(request.POST, request.FILES, policy=policy)
        if getattr(request, 'upload_limit_exceeded', False):
            form.is_valid()
            form.add_error(None, 'The uploads exceed the permitted total limit.')
        elif form.is_valid():
            try:
                intake = services.submit_registration(context_id, binding, request.POST, request.FILES,
                    user=request.user, channel=channel)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                from .prpwd import registry_url
                number = form.cleaned_data.get('pwd_number')
                if number and form.cleaned_data.get('prpwd_lookup_number') == number:
                    request.session['onsite_prpwd_lookup'] = {
                        'reference': intake.reference, 'number': number, 'url': registry_url()}
                return redirect('membership:registration_detail', reference=intake.reference)
    else:
        context_id = str(services.issue_context(binding, user=request.user, channel=channel).pk)
        form = OnsiteRegistrationForm(policy=policy)
    from .prpwd import registry_url
    return render(request, 'membership/onsite/intake.html', {**membership_guidance(), 'form': form,
        'context_id': context_id, 'policy': policy,
        'prpwd_lookup_url': registry_url(),
        'title': 'Onsite Member Registration'},
        status=400 if form.errors else 200)


@never_cache
@dashboard_required
@gated
@require_http_methods(['GET', 'HEAD', 'POST'])
@sensitive_post_parameters()
def correct(request, reference):
    services.require_staff(request.user, 'membership.correct_registrationintake')
    intake = _find(reference)
    policy = policy_for('correction')
    revision = intake.revisions.get(number=intake.current_revision)
    if revision.data.get('profile_kind', 'minimal_v1') != policy.get('applicant_profile', 'minimal_v1'):
        raise RegistrationUnavailable('The applicant field contract changed; authorized reconciliation is required.')
    form = RegistrationForm(request.POST if request.method == 'POST' else None,
        request.FILES if request.method == 'POST' else None, initial=revision.data, policy=policy)
    if request.method == 'POST' and form.is_valid():
        try:
            version = int(request.POST.get('version', '-1'))
            if getattr(request, 'upload_limit_exceeded', False):
                raise ValidationError('The uploads exceed the permitted total limit.')
            services.correct_registration(reference, user=request.user, version=version,
                reason=request.POST.get('reason', ''), data=request.POST, files=request.FILES)
        except (ValidationError, ValueError) as error:
            form.add_error(None, error if isinstance(error, ValidationError) else 'Reload the current form.')
        else:
            messages.success(request, 'Correction retained. Earlier findings require review; no membership decision was made.')
            return redirect('membership:registration_detail', reference=intake.reference)
    return render(request, 'membership/registration/staff_form.html', {**membership_guidance(), 'form': form,
        'policy': policy, 'intake': intake, 'version': request.POST.get('version', intake.version),
        'reason': request.POST.get('reason', ''), 'title': 'Record an onsite / assisted correction'},
        status=400 if form.errors else 200)


@never_cache
@dashboard_required
@gated
@require_http_methods(['GET', 'HEAD', 'POST'])
@sensitive_post_parameters()
def onsite(request, reference):
    services.require_staff(request.user, 'membership.onsite_registrationintake')
    policy = policy_for('onsite')
    intake = _find(reference)
    form = OnsiteForm(request.POST if request.method == 'POST' else None, initial={'version': intake.version}, policy=policy)
    if request.method == 'POST' and form.is_valid():
        try:
            services.record_onsite(reference, user=request.user, data=request.POST)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Onsite observations retained. Registry review, assessment and membership decision remain separate.')
            return redirect('membership:registration_detail', reference=intake.reference)
    return render(request, 'membership/registration/onsite.html', {'form': form, 'intake': intake,
        'procedure': policy['onsite_procedure_reference']}, status=400 if form.errors else 200)


@never_cache
@dashboard_required
@gated
@require_safe
def document(request, document_id):
    services.require_staff(request.user, 'membership.view_registration_documents')
    attachment = get_object_or_404(RegistrationAttachment.objects.select_related('revision__intake'),
        pk=document_id, revision__intake__category='association')
    try:
        handle = attachment.file.open('rb')
    except FileNotFoundError:
        raise Http404 from None
    try:
        services.audit_access(attachment.revision.intake, user=request.user, action='private_document_downloaded',
            revision=attachment.revision, attachment=attachment)
    except Exception:
        handle.close()
        raise
    preview = (request.GET.get('preview') == '1'
               and attachment.content_type in ('application/pdf', 'image/jpeg', 'image/png'))
    response = FileResponse(handle, as_attachment=not preview, content_type=attachment.content_type,
        filename=f'registration-document-{attachment.pk}{Path(attachment.file.name).suffix}')
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@never_cache
@dashboard_required
@gated
@require_safe
@xframe_options_sameorigin
def completed_form(request, reference, revision_number):
    services.require_staff(request.user)
    intake = _find(reference)
    revision = get_object_or_404(intake.revisions, number=revision_number)
    services.audit_access(intake, user=request.user, action='staff_completed_form_viewed', revision=revision)
    application = intake.membership_application
    approved = (application is not None and application.status == 'approved'
                and revision.number == intake.current_revision)
    return render(request, 'membership/registration/completed_form.html', {'intake': intake,
        'form_base': 'membership/registration/preview_base.html' if request.GET.get('preview') == '1' else 'base.html',
        'submitted': revision.data, 'revision_number': revision.number,
        'member_number': application.control_number if approved else '',
        'approved_at': application.decided_at if approved else None,
        'form_version': revision.policy_snapshot['form_version'],
        'onsite_instructions': revision.policy_snapshot['onsite_instructions']})
