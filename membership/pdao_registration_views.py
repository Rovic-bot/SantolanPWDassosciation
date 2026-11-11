"""Saved PDAO submissions and the permission-scoped Admin queue."""
from functools import wraps
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_safe, require_POST
from django.views.decorators.clickjacking import xframe_options_sameorigin

from accounts.decorators import dashboard_required
from . import pdao_services as services
from .guidance import membership_guidance
from .pdao_forms import PDAOOnlineForm, PDAOOnsiteForm, PDAOForwardForm, PDAOReviewForm, PDAOClaimNoticeForm, PRIVACY_NOTICE
from .pdao_models import PDAORegistration
from .pdao_presentation import record_summary
from . import pdao_email
from . import pdao_claim_email
from .prpwd import registry_url
from .registration_policy import RegistrationUnavailable, available
from core.reference_services import lookup_key


def private_page(view):
    @never_cache
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            response = view(request, *args, **kwargs)
        except RegistrationUnavailable:
            response = render(request, 'membership/registration/unavailable.html', status=503)
        response['Referrer-Policy'] = 'same-origin'
        response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
        return response
    return wrapped


@private_page
@csrf_exempt
@require_http_methods(['GET', 'HEAD', 'POST'])
def apply(request):
    services.require_enabled()
    try:
        length = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        return HttpResponse(status=400)
    if length < 0 or length > 64 * 1024:
        return HttpResponse('The form is too large. No uploads are needed.', status=413)
    services.reserve_attempt(request)
    return _apply(request)


@csrf_protect
@sensitive_post_parameters()
def _apply(request):
    if request.method in ('GET', 'HEAD'):
        if request.session.get(services.RECEIPT_KEY):
            try:
                services.receipt_for(request)
            except Http404:
                pass
            else:
                return redirect('membership:pdao_receipt')
        token = services.issue_token(request)
        form = PDAOOnlineForm(initial={'date_applied': timezone.localdate(), 'accomplished_by': 'Applicant',
                                      'submission_token': token})
    else:
        form = PDAOOnlineForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                registration = services.submit(request)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                request.session[services.RECEIPT_KEY] = str(registration.pk)
                return redirect('membership:pdao_receipt')
    return render(request, 'membership/pdao/apply.html', {'form': form, 'privacy_notice': PRIVACY_NOTICE},
                  status=400 if form.errors else 200)


@private_page
@require_safe
def receipt(request):
    registration = services.receipt_for(request)
    return render(request, 'membership/pdao/receipt.html', {'reference': registration.reference,
        'received_at': registration.received_at, 'submitted': registration.data, **membership_guidance()})


@private_page
@require_safe
@xframe_options_sameorigin
def receipt_form(request):
    registration = services.receipt_for(request)
    return render(request, 'membership/pdao/receipt_form.html', {'reference': registration.reference,
        'received_at': registration.received_at, 'submitted': registration.data, **membership_guidance()})


@private_page
@require_POST
@csrf_protect
def finish(request):
    services.finish(request)
    return redirect('core:membership')


@private_page
@dashboard_required
@require_safe
def review_home(request):
    actor = get_user_model().objects.get(pk=request.user.pk)
    if not actor.has_perm('membership.view_membershipapplication') and not actor.has_perm(services.VIEW):
        raise PermissionDenied
    return render(request, 'membership/reviews.html', {'association_online': available('staff')
        and actor.has_perm('membership.view_registrationintake')})


@private_page
@dashboard_required
@require_safe
def inbox(request):
    services.require_staff(request.user)
    records = services.review_records()
    query = request.GET.get('q', '').strip()[:200]
    state = request.GET.get('state', '')
    if state not in PDAORegistration.Status.values:
        state = ''
    if query:
        short_key = lookup_key('pdao', query)
        if short_key is not None:
            records = records.filter(pk=short_key) if short_key else records.none()
        elif query.upper().startswith('PDAO-'):
            from uuid import UUID
            try:
                key = UUID(query[5:])
            except ValueError:
                records = records.none()
            else:
                records = records.filter(pk=key)
        else:
            records = records.filter(Q(_review_name__icontains=query))
    counts = dict(records.order_by().values('status').annotate(total=Count('pk')).values_list('status', 'total'))
    status_tabs = [{'value': '', 'label': 'All applications', 'count': sum(counts.values())}]
    status_tabs.extend({'value': value, 'label': label, 'count': counts.get(value, 0)}
                       for value, label in PDAORegistration.Status.choices)
    if state:
        records = records.filter(status=state)
    page_obj = Paginator(records, 25).get_page(request.GET.get('page'))
    can_bulk_claim = state == 'forwarded' and request.user.has_perm(services.FORWARD)
    if state == 'forwarded':
        page_obj.object_list = pdao_claim_email.claim_records(page_obj.object_list, request.user)
    return render(request, 'membership/pdao/inbox.html', {'page_obj': page_obj,
        'search_query': query, 'state_query': state, 'states': PDAORegistration.Status.choices,
        'status_tabs': status_tabs, 'can_bulk_claim': can_bulk_claim,
        'claim_form': PDAOClaimNoticeForm(initial={'return_to': 'inbox', 'query': query, 'page': page_obj.number}),
        'claim_eligible_count': sum(bool(item.claim['can_send_claim_notice']) for item in page_obj) if can_bulk_claim else 0})


@private_page
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@csrf_protect
@sensitive_post_parameters()
def onsite(request):
    services.require_staff(request.user, services.ADD)
    if request.method in ('GET', 'HEAD'):
        form = PDAOOnsiteForm(initial={'date_applied': timezone.localdate(), 'accomplished_by': 'Applicant',
            'submission_token': services.issue_token(request, onsite=True)})
    else:
        form = PDAOOnsiteForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                registration = services.submit(request, onsite=True)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Onsite PDAO application saved for review.')
                return redirect('membership:pdao_detail', key=registration.pk)
    return render(request, 'membership/pdao/onsite.html', {'form': form, 'privacy_notice': PRIVACY_NOTICE,
        'pdao_onsite': True}, status=400 if form.errors else 200)


@private_page
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@csrf_protect
@sensitive_post_parameters()
def detail(request, key):
    registration = services.staff_record(key, request.user)
    submitted = registration.current_data
    status = 200
    action = 'forwarded' if registration.status == 'ready' else 'ready'
    correcting = request.method == 'POST' and request.POST.get('action') == 'correct'
    form = PDAOForwardForm(request.POST if request.method == 'POST' and not correcting else None,
                           initial={'version': registration.version, 'action': action})
    needs_form = PDAOForwardForm(request.POST if request.method == 'POST' and request.POST.get('action') == 'needs_info' else None,
        initial={'version': registration.version, 'action': 'needs_info'}, auto_id='needs_%s')
    editor = PDAOReviewForm(request.POST if correcting else None, request.FILES if correcting else None,
        initial=submitted | {'version': registration.version, 'action': 'correct'})
    if correcting:
        services.require_staff(request.user, services.CORRECT)
        if editor.is_valid():
            try:
                services.correct(key, request.user, request.POST, request.FILES)
            except ValidationError as error:
                editor.add_error(None, error)
                status = 409
            else:
                messages.success(request, 'Reviewed PDAO details saved. Printing now uses these details. Verify onsite before forwarding.')
                return redirect('membership:pdao_detail', key=key)
        else:
            status = 400
    elif request.method == 'POST':
        services.require_staff(request.user, services.FORWARD)
        if form.is_valid():
            try:
                services.transition(key, request.user, request.POST)
            except ValidationError as error:
                form.add_error(None, error)
                status = 409
            else:
                messages.success(request, 'PDAO processing status updated. Check the email status below.'
                    if registration.data.get('intake_channel', 'online') == 'online' and request.POST.get('action') in ('ready', 'needs_info')
                    else 'PDAO processing status updated. No review email is sent for onsite applications.'
                    if registration.data.get('intake_channel') != 'online' else 'Forwarding to PDAO recorded.')
                return redirect('membership:pdao_detail', key=key)
        else:
            status = 400
    return render(request, 'membership/pdao/detail.html', {'registration': registration,
        'submitted': submitted, 'form': form, 'needs_form': needs_form, 'editor_form': editor,
        'online_review': registration.data.get('intake_channel', 'online') == 'online',
        'prpwd_lookup_url': registry_url(), **pdao_email.notification_context(registration, request.user),
        'claim_form': PDAOClaimNoticeForm(initial={'return_to': 'detail'}),
        'pdao_summary': record_summary(submitted, registration.status),
        'review_history': list(registration.revisions.all()),
        'processing_history': registration.events.order_by('-occurred_at', '-pk'),
        'can_edit': request.user.has_perm(services.CORRECT) and registration.status != 'forwarded'}, status=status)


@private_page
@dashboard_required
@require_POST
@csrf_protect
def retry_email(request, key, email_id):
    try:
        pdao_email.retry_review_email(key, user=request.user, identifier=email_id)
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    else:
        messages.success(request, 'The saved PDAO email was queued for another delivery attempt.')
    return redirect('membership:pdao_detail', key=key)


@private_page
@dashboard_required
@require_POST
@csrf_protect
def send_claim_notices(request):
    services.require_staff(request.user, services.FORWARD)
    form = PDAOClaimNoticeForm(request.POST)
    if form.is_valid():
        try:
            result = pdao_claim_email.queue_claim_notices(user=request.user,
                selections=form.cleaned_data['applications'], confirmed=form.cleaned_data['confirmed'])
        except ValidationError as error:
            messages.error(request, ' '.join(error.messages))
        else:
            if result['queued']:
                count = result['queued']
                messages.success(request, f'{count} PWD ID claim notice{"s" if count != 1 else ""} queued. Each applicant receives a separate email. Refresh email status to check delivery.')
            if result['already_requested']:
                messages.info(request, 'Previously requested claim notices were kept; no duplicate emails were created. Review their delivery status before retrying.')
        if form.cleaned_data.get('return_to') == 'detail' and len(form.cleaned_data['applications']) == 1:
            return redirect('membership:pdao_detail', key=next(iter(form.cleaned_data['applications'])))
    else:
        messages.error(request, ' '.join(message for errors in form.errors.values() for message in errors))
    params = {'state': 'forwarded', 'q': request.POST.get('query', '').strip()[:200]}
    page = request.POST.get('page', '')
    if page.isdecimal() and len(page) <= 7:
        params['page'] = page
    return redirect(reverse('membership:pdao_inbox') + '?' + urlencode(params))


@private_page
@dashboard_required
@require_safe
@xframe_options_sameorigin
def print_form(request, key):
    registration = services.staff_record(key, request.user, printing=True)
    return render(request, 'membership/pdao/print.html', {'registration': registration,
        'submitted': registration.current_data, 'embedded_preview': request.GET.get('preview') == '1',
        **membership_guidance()})
