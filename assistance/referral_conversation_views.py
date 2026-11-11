from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from . import referral_conversations as conversations
from . import referral_services as service
from .referral_forms import ConversationAccessForm, ConversationReplyForm
from .referral_models import ReferralTicket
from .referral_live import wants_json
from .referral_views import available, binding, SESSION_KEY as INTAKE_SESSION_KEY

SESSION_KEY = 'referral_conversation_v1'
PAGES_SESSION_KEY = 'referral_conversation_pages_v1'


def access_token(request, page_id=None):
    if page_id is None:
        return request.session.get(SESSION_KEY)
    entry = request.session.get(PAGES_SESSION_KEY, {}).get(str(page_id), {})
    return entry.get('token')


def clear_access(request, page_id=None):
    token = access_token(request, page_id)
    if page_id is not None:
        pages = dict(request.session.get(PAGES_SESSION_KEY, {}))
        if str(page_id) in pages:
            pages.pop(str(page_id))
            request.session[PAGES_SESSION_KEY] = pages
    if SESSION_KEY in request.session and request.session.get(SESSION_KEY) == token:
        request.session.pop(SESSION_KEY, None)


def open_page(request, ticket, token=None):
    """Give the session a navigation URL that does not expose its private ASR key."""
    try:
        token = token or conversations.issue_access(ticket, binding(request))
    except conversations.ConversationClosed:
        return finished(request)
    except PermissionDenied:
        return redirect('assistance:referral_conversation_verify')
    pages = dict(request.session.get(PAGES_SESSION_KEY, {}))
    page_id = next((key for key, entry in pages.items() if entry.get('ticket') == str(ticket.pk)), str(uuid4()))
    pages.pop(page_id, None)
    # Bound the session size while preserving independently opened conversations.
    while len(pages) >= 10:
        pages.pop(next(iter(pages)))
    pages[page_id] = {'ticket': str(ticket.pk), 'token': token}
    request.session[PAGES_SESSION_KEY] = pages
    request.session[SESSION_KEY] = token
    return redirect('assistance:referral_conversation_page', page_id=page_id)


def finished(request, page_id=None):
    clear_access(request, page_id)
    return render(request, 'assistance/referrals/conversation_finished.html')


@never_cache
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters()
@available
def verify(request):
    form = ConversationAccessForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        request.session.pop(SESSION_KEY, None)
        session_binding = binding(request)
        if not service.reserve_attempt('conversation:' + request.POST.get('conversation_reference', '')[:40],
                request.META.get('REMOTE_ADDR', ''), session_binding):
            form.add_error(None, 'Unable to open a conversation right now. Please try again later or contact the Help Desk.')
        elif form.is_valid():
            try:
                token = conversations.verify_conversation(binding=session_binding, **form.cleaned_data)
                ticket = conversations.get_conversation(token, session_binding)
            except conversations.ConversationClosed:
                return finished(request)
            except PermissionDenied:
                form.add_error(None, conversations.ACCESS_ERROR)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                return open_page(request, ticket, token)
    return render(request, 'assistance/referrals/conversation_verify.html', {'form': form},
        status=400 if form.errors else 200)


@never_cache
@require_POST
@available
def start(request):
    """The original verified submitter can open their conversation from the receipt."""
    try:
        grant = service.get_grant(request.session.get(INTAKE_SESSION_KEY), binding(request))
    except (PermissionDenied, ValidationError):
        return redirect('assistance:referral_conversation_verify')
    ticket = get_object_or_404(ReferralTicket.objects.select_related('member__application'), grant=grant)
    return open_page(request, ticket)


def current_ticket(request, page_id=None):
    token = access_token(request, page_id)
    if not token or not request.session.session_key:
        raise PermissionDenied
    return conversations.get_conversation(token, binding(request))


@never_cache
@require_http_methods(['GET', 'POST'])
@sensitive_post_parameters()
@available
def conversation(request, page_id=None):
    try:
        ticket = current_ticket(request, page_id)
    except conversations.ConversationClosed:
        if wants_json(request):
            clear_access(request, page_id)
            return JsonResponse({'closed': True}, status=410)
        return finished(request, page_id)
    except PermissionDenied:
        clear_access(request, page_id)
        if wants_json(request):
            return JsonResponse({'expired': True}, status=403)
        return redirect('assistance:referral_conversation_verify')
    if page_id is None and request.method == 'GET':
        return open_page(request, ticket, access_token(request))
    form = ConversationReplyForm(request.POST if request.method == 'POST' else None,
        initial={'version': ticket.version})
    if request.method == 'POST' and request.POST.get('conversation_ticket', str(ticket.pk)) != str(ticket.pk):
        if wants_json(request):
            return JsonResponse({'mismatch': True}, status=409)
        form.add_error(None, 'Another conversation was opened in this browser. Reopen the intended conversation before sending.')
    if request.method == 'POST' and form.is_valid():
        try:
            ticket = conversations.reply(access_token(request, page_id), binding(request), data=request.POST)
        except conversations.ConversationClosed:
            if wants_json(request):
                clear_access(request, page_id)
                return JsonResponse({'closed': True}, status=410)
            return finished(request, page_id)
        except PermissionDenied:
            clear_access(request, page_id)
            if wants_json(request):
                return JsonResponse({'expired': True}, status=403)
            form.add_error(None, 'Your private session expired or your member record changed. Save your message, then reopen using your conversation reference.')
        except ValidationError as error:
            form.add_error(None, error)
            try:
                ticket = current_ticket(request, page_id)
            except conversations.ConversationClosed:
                if wants_json(request):
                    clear_access(request, page_id)
                    return JsonResponse({'closed': True}, status=410)
                return finished(request, page_id)
            except PermissionDenied:
                clear_access(request, page_id)
                if wants_json(request):
                    return JsonResponse({'expired': True}, status=403)
                return redirect('assistance:referral_conversation_verify')
            # Show current history and retain the draft for a deliberate retry.
            form.data = form.data.copy()
            form.data['version'] = ticket.version
        else:
            if wants_json(request):
                return JsonResponse({**conversations.conversation_payload(ticket), 'sent': True})
            if page_id is None:
                return open_page(request, ticket, access_token(request))
            return redirect('assistance:referral_conversation_page', page_id=page_id)
    if request.method == 'POST' and wants_json(request):
        return JsonResponse({**conversations.conversation_payload(ticket), 'sent': False,
            'errors': [str(error) for errors in form.errors.values() for error in errors]}, status=400)
    return render(request, 'assistance/referrals/conversation.html', {'ticket': ticket, 'form': form,
        'conversation_url': reverse('assistance:referral_conversation_page', args=[page_id]) if page_id else reverse('assistance:referral_conversation'),
        'updates_url': reverse('assistance:referral_conversation_page_updates', args=[page_id]) if page_id else reverse('assistance:referral_conversation_updates'),
        'conversation_messages': conversations.visible_messages(ticket)}, status=400 if form.errors else 200)


@never_cache
@require_safe
@available
def updates(request, page_id=None):
    try:
        ticket = current_ticket(request, page_id)
    except conversations.ConversationClosed:
        clear_access(request, page_id)
        return JsonResponse({'closed': True}, status=410)
    except PermissionDenied:
        clear_access(request, page_id)
        return JsonResponse({'expired': True}, status=403)
    return JsonResponse(conversations.conversation_payload(ticket))
