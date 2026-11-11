"""Public session-bound updates and the existing staff permission boundary."""
import secrets

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from core.email_delivery import delivery_help
from programs.tracking_views import private_response
from .update_forms import UpdateIdentityForm, UpdateCodeForm, PublicMemberUpdateForm, UpdateReviewForm
from .update_models import MemberUpdateRequest
from . import update_services as service, update_mail


def current_access(request, *, allow_submitted=False):
    grant = request.session.get(service.SESSION_KEY, {})
    return service.verified_access(grant.get('id'), grant.get('nonce', ''), allow_submitted=allow_submitted)


@never_cache
@sensitive_post_parameters()
@require_http_methods(['GET', 'HEAD', 'POST'])
def start(request):
    form = UpdateIdentityForm(request.POST if request.method == 'POST' else None)
    status = 200
    if request.method == 'POST':
        request.session.pop(service.SESSION_KEY, None)
        if not service.reserve_access(request.POST.get('control_number', '')[:100], request.META.get('REMOTE_ADDR', '')):
            form.add_error(None, 'Too many requests. Please try again later or contact the Association Help Desk.')
            status = 429
        elif form.is_valid():
            nonce = secrets.token_urlsafe(32)
            access = service.start_access(nonce=nonce, **form.cleaned_data)
            request.session.cycle_key()
            request.session[service.SESSION_KEY] = {'id': str(access.pk), 'nonce': nonce}
            return private_response(redirect('members:update_code'))
    response = private_response(render(request, 'members/update/verify.html', {'form': form}, status=status))
    if status == 429:
        response['Retry-After'] = '3600'
    return response


@never_cache
@sensitive_post_parameters('code')
@require_http_methods(['GET', 'HEAD', 'POST'])
def code(request):
    grant = request.session.get(service.SESSION_KEY, {})
    if not service.access_record(grant.get('id'), grant.get('nonce', '')):
        return private_response(redirect('members:update_start'))
    form = UpdateCodeForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        if service.verify_code(grant['id'], nonce=grant['nonce'], code=form.cleaned_data['code']):
            request.session.cycle_key()
            return private_response(redirect('members:update_information'))
        form.add_error(None, 'The code is incorrect, expired or no longer available. Request a new code or contact the Help Desk.')
    return private_response(render(request, 'members/update/code.html', {'form': form}))


@never_cache
@sensitive_post_parameters()
@require_http_methods(['GET', 'HEAD', 'POST'])
def information(request):
    try:
        access = current_access(request, allow_submitted=True)
    except ValidationError:
        request.session.pop(service.SESSION_KEY, None)
        messages.info(request, service.EXPIRED)
        return private_response(redirect('members:update_start'))
    pending = service.pending_request(access.member)
    previous = getattr(access, 'update_request', None)
    if pending or previous:
        return private_response(render(request, 'members/update/submitted.html', {'update': pending or previous}))
    form = PublicMemberUpdateForm(request.POST if request.method == 'POST' else None,
        instance=access.member, request_key=access.pk)
    if request.method == 'POST':
        if request.FILES:
            form.add_error(None, 'Bring supporting documents to the office interview; this form accepts information only.')
        elif form.is_valid():
            grant = request.session[service.SESSION_KEY]
            try:
                service.submit_update(grant['id'], nonce=grant['nonce'], data=request.POST)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                return private_response(redirect('members:update_information'))
    return private_response(render(request, 'members/update/information.html', {'form': form}))


@never_cache
@require_POST
def finish(request):
    request.session.pop(service.SESSION_KEY, None)
    return private_response(redirect('core:home'))


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def review(request, pk):
    require_workspace_permissions(request.user, 'members.view_member')
    record = get_object_or_404(MemberUpdateRequest.objects.select_related('member', 'access'), pk=pk)
    form = UpdateReviewForm(request.POST if request.method == 'POST' else None,
        initial={'version': record.version, 'member_version': record.member.version})
    if request.method == 'POST' and form.is_valid():
        values = form.cleaned_data
        arguments = {'user': request.user, 'version': values['version'], 'member_version': values['member_version']}
        operation = request.POST.get('action')
        try:
            if operation == 'invite':
                service.invite_member(pk, **arguments)
                messages.success(request, 'Office-verification invitation recorded. Check its delivery status below.')
            elif operation == 'retry':
                service.retry_invitation(pk, **arguments)
                messages.success(request, 'Invitation retry recorded. Check its delivery status below.')
            elif operation in ('approved', 'needs_verification'):
                service.decide_update(pk, **arguments, decision=operation, reason=values['reason'],
                    interview_confirmed=values['interview_confirmed'])
                messages.success(request, 'Updated information approved.' if operation == 'approved' else
                    'Marked Needs verification. New program applications are blocked until this update is approved.')
            else:
                raise ValidationError('Choose an available review action.')
        except ValidationError as error:
            form.add_error(None, error)
        else:
            return redirect('members:update_review', pk=pk)
    job = getattr(record, 'invitation', None)
    return render(request, 'members/update/review.html', {'update': record, 'form': form,
        'comparison': service.comparison(record), 'invitation': job,
        'delivery_label': update_mail.describe(job), 'invitation_accepted': update_mail.accepted(job),
        'delivery_help': delivery_help(job),
        'can_retry': bool(job and job.state in ('failed', 'queued')), 'can_act': service.can_request(record.member),
        'record_changed': record.member.version != record.member_version})
