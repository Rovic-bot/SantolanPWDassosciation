from functools import wraps
from pathlib import Path

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Max, Q
from django.db.models.functions import Coalesce, Greatest
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST, require_safe
from accounts.decorators import dashboard_required
from core.email_delivery import delivery_help
from . import referral_services as service
from .referral_forms import NewConcernForm, TicketForm, ReviewForm, RetryForm, EmailConnectionSettingsForm
from .referral_models import ReferralTicket, ReferralAttachment, ReferralEmail, ReferralSettings
from .referral_mail import delivery_label, retry_email
from .referral_connection import connection_status
from .referral_live import reply_feedback, ticket_payload, wants_json

SESSION_KEY = 'referral_grant_v1'


def available(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not service.enabled():
            return render(request, 'assistance/referrals/unavailable.html', status=503)
        return view(request, *args, **kwargs)
    return wrapped


def binding(request):
    if not request.session.session_key:
        request.session.create()
    return service.binding_for(request.session.session_key)


@never_cache
@require_safe
def information(request):
    return redirect(f'{reverse("core:resources")}#referral-support')


@never_cache
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters()
@available
def verify(request):
    token = binding(request)
    form = NewConcernForm(request.POST if request.method == 'POST' else None, request.FILES or None,
        initial={'request_key': service.new_request_key(token)})
    if request.method == 'POST':
        permitted = service.reserve_attempt(request.POST.get('control_number', '')[:100],
            request.META.get('REMOTE_ADDR', ''), token)
        if not permitted:
            form.add_error(None, 'Unable to verify membership right now. Please try again later or visit the Association Help Desk.')
        elif form.is_valid():
            try:
                ticket = service.start_concern(binding=token, data=request.POST, files=request.FILES)
            except PermissionDenied:
                form.add_error(None, 'This form has expired. Reload New concern and submit again.')
            except ValidationError as error:
                form.add_error(None, error)
            else:
                from .referral_conversation_views import open_page
                request.session[SESSION_KEY] = str(ticket.grant_id)
                return open_page(request, ticket)
    return render(request, 'assistance/referrals/verify.html', {'form': form}, status=400 if form.errors else 200)


@never_cache
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters()
@available
def apply(request):
    if request.method == 'GET':
        return redirect('assistance:referral_verify')
    try:
        grant = service.get_grant(request.session.get(SESSION_KEY), binding(request))
    except (PermissionDenied, ValidationError):
        request.session.pop(SESSION_KEY, None)
        return redirect('assistance:referral_verify')
    form = TicketForm(request.POST if request.method == 'POST' else None, request.FILES or None, member=grant.member)
    if request.method == 'POST':
        if getattr(request, 'upload_limit_exceeded', False):
            form.add_error(None, 'The combined uploads are too large. Choose smaller files or provide evidence later.')
        elif form.is_valid():
            try:
                ticket = service.submit_ticket(grant.pk, binding(request), data=request.POST, files=request.FILES)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                from .referral_conversation_views import open_page
                return open_page(request, ticket)
    return render(request, 'assistance/referrals/apply.html', {'form': form, 'notice': service.NOTICE},
        status=400 if form.errors else 200)


@never_cache
@require_safe
@available
def receipt(request):
    grant = service.get_grant(request.session.get(SESSION_KEY), binding(request), recheck=False)
    ticket = get_object_or_404(ReferralTicket, grant=grant)
    if ticket.status == ReferralTicket.Status.CLOSED:
        from .referral_conversation_views import finished
        return finished(request)
    email = ticket.emails.order_by('created_at').first()
    return render(request, 'assistance/referrals/receipt.html', {'ticket': ticket,
        'delivery': delivery_label(email) if email else 'Queued', 'notice': service.NOTICE})


@never_cache
@require_POST
def finish(request):
    from .referral_conversation_views import SESSION_KEY as CONVERSATION_SESSION_KEY, PAGES_SESSION_KEY
    request.session.pop(CONVERSATION_SESSION_KEY, None)
    request.session.pop(PAGES_SESSION_KEY, None)
    identifier = request.session.pop(SESSION_KEY, None)
    if identifier:
        try:
            service.finish(identifier, binding(request))
        except (PermissionDenied, ValidationError):
            pass
    return redirect('assistance:referral_information')


@never_cache
@dashboard_required
@require_safe
def inbox(request):
    actor = service.current_actor(request.user)
    rows = ReferralTicket.objects.annotate(
        last_member_reply=Max('actions__recorded_at', filter=Q(actions__action='member_replied')),
    ).annotate(latest_activity=Greatest('received_at', Coalesce('last_member_reply', 'received_at'))
    ).order_by('-latest_activity', '-pk')
    totals = rows.aggregate(total=Count('pk'), received=Count('pk', filter=Q(status='received')),
        closed=Count('pk', filter=Q(status='closed')))
    status = request.GET.get('status', 'open')
    kind = request.GET.get('type', '')
    query = request.GET.get('q', '').strip()[:100]
    if status in ReferralTicket.Status.values:
        rows = rows.filter(status=status)
    elif status != 'all':
        status = 'open'
        rows = rows.exclude(status=ReferralTicket.Status.CLOSED)
    if kind in ReferralTicket.Kind.values:
        rows = rows.filter(assistance_type=kind)
    else:
        kind = ''
    if query:
        from core.reference_services import filter_reference
        rows = filter_reference(rows, 'referral', query,
            Q(reference__icontains=query) | Q(subject__icontains=query) | Q(full_name__icontains=query))
    page = Paginator(rows, 25).get_page(request.GET.get('page'))
    context = {'page': page,
        'can_review': actor.has_perm('assistance.review_referralticket'),
        'statuses': ReferralTicket.Status.choices, 'selected_status': status, 'query': query,
        'kinds': ReferralTicket.Kind.choices, 'selected_kind': kind, 'totals': totals,
        'ticket_closed': request.GET.get('closed') == '1'}
    if wants_json(request):
        from django.template.loader import render_to_string
        return JsonResponse({'totals': totals, 'results_html': render_to_string(
            'assistance/referrals/inbox_results.html', context, request=request)})
    return render(request, 'assistance/referrals/inbox.html', context)


@never_cache
@dashboard_required
@require_safe
def new_concerns(request):
    service.current_actor(request.user)
    return JsonResponse({'new_count': service.new_concern_count()})


@never_cache
@dashboard_required
@require_safe
def updates(request, pk):
    actor = service.current_actor(request.user)
    ticket = get_object_or_404(ReferralTicket, pk=pk)
    return JsonResponse(ticket_payload(ticket, actor, request))


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters()
def detail(request, pk):
    actor = service.current_actor(request.user)
    ticket = get_object_or_404(ReferralTicket.objects.select_related('member__application'), pk=pk)
    can_reply = actor.has_perms(['assistance.review_referralticket', 'assistance.send_referral_email'])
    configuration = ReferralSettings.objects.filter(pk=1).first()
    legacy_post = request.method == 'POST' and 'action' not in request.POST
    form = ReviewForm(request.POST if legacy_post else None,
        initial={'version': ticket.version,
                 'channel': request.session.get('referral_reply_channel', 'email') if can_reply else 'online',
                 'sender_version': configuration.version if configuration else 0},
        sender_email=configuration.sender_email if configuration else '')
    if not can_reply:
        form.fields['channel'].choices = [('online', 'Online conversation')]
    form.fields['channel'].choices = [(code, 'Email' if code == 'email' else label)
                                     for code, label in form.fields['channel'].choices]
    form.fields['member_message'].widget.attrs.update(rows=2, placeholder='Type a message…')
    action_errors = []
    if request.method == 'POST':
        service.current_actor(request.user, 'assistance.review_referralticket')
        if legacy_post and request.POST.get('channel') in ('email', 'email_app'):
            service.current_actor(request.user, 'assistance.send_referral_email')
        if not legacy_post:
            try:
                if request.FILES:
                    raise ValidationError('Choose a ticket action without uploading new files.')
                service.quick_update_ticket(pk, user=request.user, data=request.POST)
            except ValidationError as error:
                action_errors = error.messages
            else:
                if request.POST.get('action') != 'begin_review':
                    messages.success(request, 'Gmail reply recorded.' if request.POST.get('action') == 'record_reply'
                        else 'Ticket closed.')
                if request.POST.get('action') == 'closed':
                    return redirect(f'{reverse("assistance:referral_inbox")}?closed=1')
                return redirect('assistance:referral_detail', pk=pk)
        elif form.is_valid():
            try:
                saved = service.review_ticket(pk, user=request.user, data=request.POST)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                request.session['referral_reply_channel'] = form.cleaned_data['channel']
                notice, delivery_error = reply_feedback(saved, form.cleaned_data, actor)
                if wants_json(request):
                    return JsonResponse({**ticket_payload(saved, actor, request),
                        'sent': True, 'notice': notice, 'delivery_error': delivery_error})
                (messages.error if delivery_error else messages.success)(request, notice)
                return redirect('assistance:referral_detail', pk=pk)
    if request.method == 'POST' and legacy_post and wants_json(request):
        ticket.refresh_from_db()
        return JsonResponse({**ticket_payload(ticket, actor, request), 'sent': False,
            'errors': [str(error) for errors in form.errors.values() for error in errors]}, status=400)
    emails = list(ticket.emails.prefetch_related('attempts'))
    for email in emails:
        email.delivery_label = delivery_label(email)
        email.delivery_help = delivery_help(email)
    attachments = ticket.attachments.all() if request.user.has_perm('assistance.view_referral_documents') else []
    portrait_url = ''
    if actor.has_perm('members.view_member'):
        from members.portraits import member_portrait
        documents = (ticket.member.application.documents.select_related('requirement')
                     if actor.has_perm('documents.view_membershipapplicationdocument') else [])
        _, portrait_url = member_portrait(ticket.member, actor, documents)
    can_review = actor.has_perm('assistance.review_referralticket') and ticket.status != 'closed'
    return render(request, 'assistance/referrals/detail.html', {'ticket': ticket, 'form': form, 'emails': emails,
        'member_name': ticket.member.full_name, 'member_portrait_url': portrait_url,
        'mail_connection': connection_status(configuration),
        'sender_email': configuration.sender_email if configuration else '',
        'attachments': attachments, 'actions': ticket.actions.all(), 'retry_form': RetryForm(),
        'can_review': can_review, 'can_reply': can_reply, 'action_errors': action_errors,
        'begin_review_on_open': can_review and ticket.status == 'received' and request.method == 'GET'},
        status=400 if action_errors or form.errors else 200)


@never_cache
@dashboard_required
@require_safe
def attachment(request, pk):
    actor = service.current_actor(request.user, 'assistance.view_referral_documents')
    item = get_object_or_404(ReferralAttachment.objects.select_related('ticket'), pk=pk)
    if not item.file.storage.exists(item.file.name):
        raise Http404
    from django.db import transaction
    from .referral_models import referral_write
    with transaction.atomic(), referral_write():
        service.record_action(item.ticket, actor=actor, action='evidence_viewed', notes='Private supporting evidence accessed.')
    inline = request.GET.get('view') == 'inline' and item.content_type in ('image/jpeg', 'image/png', 'application/pdf')
    response = FileResponse(item.file.open('rb'), as_attachment=not inline,
        filename='referral-evidence' + Path(item.file.name).suffix, content_type=item.content_type)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    response['Cache-Control'] = 'private, no-store'
    return response


@never_cache
@dashboard_required
@require_POST
def retry(request, pk):
    service.current_actor(request.user, 'assistance.send_referral_email')
    job = get_object_or_404(ReferralEmail, pk=pk)
    form = RetryForm(request.POST)
    if form.is_valid():
        try:
            retry_email(pk, user=request.user, **form.cleaned_data)
        except ValidationError as error:
            messages.error(request, '; '.join(error.messages))
        else:
            messages.success(request, 'The retry was recorded. Check the email history for its result.')
    else:
        messages.error(request, 'Enter a reason and confirm the email retry.')
    return redirect('assistance:referral_detail', pk=job.ticket_id)


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters()
def email_settings(request):
    service.current_actor(request.user, 'assistance.configure_referrals')
    row = ReferralSettings.objects.filter(pk=1).first()
    form = EmailConnectionSettingsForm(request.POST if request.method == 'POST' else None,
        initial={'version': row.version if row else 0, 'sender_email': row.sender_email if row else ''})
    if request.method == 'POST' and form.is_valid():
        try:
            saved = service.set_sender(user=request.user, data={**form.cleaned_data,
                'reason': ('Association Gmail connection updated from settings.'
                           if form.cleaned_data['gmail_app_password'] else
                           'Association email address updated from settings.')})
        except ValidationError as error:
            form.add_error(None, error)
        else:
            if connection_status(saved)['ready']:
                messages.success(request, 'Association email connection saved. No email was sent by this check.')
            else:
                messages.warning(request, 'Address saved, but Gmail is not connected. Enter its app password to enable sending.')
            return redirect('assistance:referral_email_settings')
    from .referral_models import ReferralSettingsEvent
    return render(request, 'assistance/referrals/settings.html', {'form': form,
        'mail_connection': connection_status(row),
        'history': ReferralSettingsEvent.objects.select_related('actor')[:20]}, status=400 if form.errors else 200)
