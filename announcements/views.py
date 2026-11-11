from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from .forms import AnnouncementForm, AnnouncementComposerForm, PublicationForm, ResultDraftForm
from .models import Announcement, NOTICE_CATEGORIES
from .notices import public_notice
from .public_claims import result_with_claim_status
from .services import change_publication, save_announcement


@never_cache
@require_safe
def public_list(request):
    from .public_board import board_context
    return render(request, 'announcements/public_board.html', board_context(request))


@never_cache
@require_safe
def public_detail(request, pk):
    item = get_object_or_404(Announcement.objects.filter(pk=pk).published())
    participation = None
    if item.linked_program_id:
        from .participation import public_program_participation
        participation = public_program_participation(item.linked_program)
    elif item.result_revision_id and item.result_revision.public_payload.get('kind') == 'program_participation':
        participation = item.result_revision.public_payload
    template = 'announcements/public_popup.html' if request.GET.get('popup') == '1' else 'announcements/public_detail.html'
    return render(request, template, {
        'announcement': public_notice(item), 'participation': participation,
        'published_result': result_with_claim_status(item) if item.result_revision_id else None})


def image_response(item):
    if not item.image:
        raise Http404
    try:
        handle = item.image.open('rb')
    except FileNotFoundError:
        raise Http404
    response = FileResponse(handle, content_type='image/png', filename='image.png')
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return response


@never_cache
@require_safe
def public_image(request, pk):
    return image_response(get_object_or_404(Announcement.objects.in_category('general').filter(pk=pk).published()))


@never_cache
@dashboard_required
@require_safe
def preview_image(request, pk):
    require_workspace_permissions(request.user, 'announcements.view_announcement')
    return image_response(get_object_or_404(Announcement, pk=pk))


@never_cache
@dashboard_required
@require_safe
def manage_list(request):
    require_workspace_permissions(request.user, 'announcements.view_announcement')
    from .results import RESULT_PERMISSIONS
    if request.user.has_perms([*RESULT_PERMISSIONS, 'announcements.add_announcement', 'announcements.change_announcement']):
        return prepare_result_draft(request, landing=True)
    return manage_notices(request)


@never_cache
@dashboard_required
@require_safe
def manage_notices(request):
    require_workspace_permissions(request.user, 'announcements.view_announcement')
    items = Announcement.objects.select_related('linked_program')
    category = request.GET.get('category', '')
    if category not in dict(NOTICE_CATEGORIES):
        category = ''
    items = items.in_category(category)
    status = request.GET.get('status', '')
    if status in Announcement.Status.values:
        items = items.filter(status=status)
    else:
        status = ''
        items = items.exclude(status='deleted')
    query = request.GET.get('q', '').strip()[:200]
    if query:
        items = items.filter(Q(title__icontains=query) | Q(content__icontains=query)
            | Q(source_office__icontains=query) | Q(linked_program__name__icontains=query)
            | Q(linked_program__description__icontains=query))
    return render(request, 'announcements/manage_list.html', {
        'page_obj': Paginator(items, 20).get_page(request.GET.get('page')),
        'statuses': Announcement.Status.choices, 'status': status, 'query': query,
        'categories': NOTICE_CATEGORIES, 'category': category,
        'review_url': _requested_review_url(request)})


def _requested_review_url(request):
    from uuid import UUID
    try:
        pk = UUID(request.GET.get('review', ''))
    except (ValueError, TypeError):
        return ''
    return reverse('announcements:manage_detail', args=[pk]) + '?popup=1'


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def edit(request, pk=None):
    require_workspace_permissions(request.user, 'announcements.view_announcement',
                                  'announcements.change_announcement' if pk else 'announcements.add_announcement')
    item = get_object_or_404(Announcement.objects.exclude(status='deleted'), pk=pk) if pk else Announcement()
    if item.program_id:
        recipients = item.result_revision and item.result_revision.public_payload.get('kind') == 'assistance_recipients'
        return redirect('announcements:prepare_recipients' if recipients else 'announcements:prepare_results', program_id=item.program_id)
    if item.status == 'published':
        require_workspace_permissions(request.user, 'announcements.publish_announcement')
    if item.linked_program_id:
        require_workspace_permissions(request.user, 'programs.view_program')
    composer = not item.linked_program_id
    popup = composer and request.GET.get('popup') == '1'
    form_class = AnnouncementComposerForm if composer else AnnouncementForm
    form = form_class(request.POST if request.method == 'POST' else None, request.FILES or None,
                            instance=item, user=request.user)
    status_code = 200
    if request.method == 'POST':
        if getattr(request, 'upload_limit_exceeded', False):
            form.add_error(None, 'The upload is too large. Select a smaller image and try again.')
            status_code = 413
        elif form.is_valid():
            try:
                saved = save_announcement(user=request.user, data=request.POST, files=request.FILES,
                                          pk=pk, address=request.META.get('REMOTE_ADDR'), composer=composer)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Draft saved. Review and approve it before publishing.')
                if popup:
                    return JsonResponse({'redirect': reverse('announcements:manage_detail', args=[saved.pk])})
                return redirect('announcements:manage_detail', pk=saved.pk)
    template = ('announcements/composer_form.html' if popup else 'announcements/composer_page.html') if composer else 'announcements/edit.html'
    return render(request, template, {'announcement': item, 'editing': bool(pk), 'form': form,
        'image_limit_mb': settings.ANNOUNCEMENT_IMAGE_MAX_BYTES // 1048576}, status=status_code)


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def manage_detail(request, pk):
    require_workspace_permissions(request.user, 'announcements.view_announcement')
    review_popup = request.GET.get('popup') == '1' or request.headers.get('X-Announcement-Dialog') == '1'
    item = get_object_or_404(Announcement, pk=pk)
    if item.linked_program_id:
        require_workspace_permissions(request.user, 'programs.view_program')
    if not review_popup:
        return redirect(reverse('announcements:manage_list') + f'?selected=notice-{pk}&review={pk}')
    actions = []
    if item.status != 'deleted':
        if request.user.has_perm('announcements.publish_announcement'):
            actions.extend((value, label) for value, label in [
                ('published', 'Publish on the public website'), ('draft', 'Withdraw to draft'),
                ('archived', 'Archive announcement')] if value != item.status)
        if request.user.has_perm('announcements.delete_announcement'):
            actions.append(('deleted', 'Delete announcement (retain audit history)'))
    form = PublicationForm(request.POST if request.method == 'POST' else None,
                           actions=actions, initial={'version': item.version})
    if item.program_id or item.linked_program_id:
        form.fields['confirm'].label = 'I reviewed these results and authorize publication with names masked on the public website.'
    else:
        form.fields['confirm'].label = 'I reviewed the content, responsible source or office, and any linked program and authorize this publication change.'
    if request.method == 'POST':
        require_workspace_permissions(request.user,
            'announcements.delete_announcement' if request.POST.get('action') == 'deleted' else 'announcements.publish_announcement')
        if form.is_valid():
            try:
                change_publication(pk, user=request.user, version=form.cleaned_data['version'],
                    action=form.cleaned_data['action'], address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Announcement publication status updated.')
                if review_popup:
                    return redirect(reverse('announcements:manage_detail', args=[pk]) + '?popup=1')
                return redirect('announcements:manage_detail', pk=pk)
    from .results import results_current, RESULT_PERMISSIONS
    from .admin_results import admin_projection
    participation, admin_results = None, None
    result_revisions = list(item.result_revisions.all()) if request.user.has_perm('announcements.view_announcementevent') else []
    can_review_results = request.user.has_perms(RESULT_PERMISSIONS)
    if item.program_id and can_review_results:
        if item.result_revision_id:
            admin_results = admin_projection(item.program, item.result_revision.public_payload, user=request.user)
        for revision in result_revisions:
            revision.admin_payload = admin_projection(item.program, revision.public_payload, user=request.user)
    if item.linked_program_id and request.user.has_perms(RESULT_PERMISSIONS):
        from .participation import public_program_participation
        payload = public_program_participation(item.linked_program)
        if payload:
            participation = admin_projection(item.linked_program, payload, user=request.user)
    return render(request, 'announcements/review_dialog.html', {'announcement': item, 'form': form, 'review_popup': review_popup,
        'participation': participation, 'admin_results': admin_results,
        'notice': public_notice(item),
        'results_current': results_current(item) if item.program_id else True,
        'result_revisions': result_revisions,
        'can_prepare_results': request.user.has_perms([*RESULT_PERMISSIONS, 'announcements.add_announcement', 'announcements.change_announcement']),
        'can_edit': item.status != 'deleted' and request.user.has_perm('announcements.change_announcement')
                    and (item.status != 'published' or request.user.has_perm('announcements.publish_announcement')),
        'actions': actions, 'history': (Paginator(item.events.all(), 20).get_page(request.GET.get('page'))
            if request.user.has_perm('announcements.view_announcementevent') else None)})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def prepare_result_draft(request, program_id=None, recipients=False, landing=False):
    from programs.models import Program
    from .results import RESULT_PERMISSIONS, prepare_results
    require_workspace_permissions(request.user, *RESULT_PERMISSIONS, 'announcements.add_announcement', 'announcements.change_announcement')
    program = get_object_or_404(Program, pk=program_id) if program_id else None
    item = Announcement.objects.filter(program=program).first() if program else None
    form = ResultDraftForm(request.POST if request.method == 'POST' else None, program=program,
                           initial={'version': item.version if item else 0})
    # The earlier private-draft POST remains available for retained review links.
    from .forms import GenerateResultsForm
    from .generation import PERMISSIONS, generate_results, review_roster, review_messages
    from .recorded_results import recorded_preview, publish_recorded_results
    from .admin_results import admin_projection, review_pool
    generation_form, preview, preview_errors = None, None, []
    action = request.POST.get('action')
    generating = request.method == 'POST' and action in ('GENERATE_RESULTS', 'PUBLISH_RECORDED_RESULTS')
    if generating:
        require_workspace_permissions(request.user, *PERMISSIONS)
        generation_form = GenerateResultsForm(request.POST)
        if program and generation_form.is_valid():
            try:
                publish = publish_recorded_results if action == 'PUBLISH_RECORDED_RESULTS' else generate_results
                saved = publish(program.pk, user=request.user,
                    address=request.META.get('REMOTE_ADDR'), **generation_form.cleaned_data)
            except ValidationError as error:
                generation_form.add_error(None, review_messages(error.messages))
            else:
                messages.success(request, 'Program results published.')
                if request.headers.get('X-Announcement-Dialog') == '1':
                    return redirect('announcements:prepare_results', program_id=program.pk)
                return redirect('announcements:manage_detail', pk=saved.pk)
    if program and request.user.has_perms(PERMISSIONS):
        try:
            preview = recorded_preview(program.pk, user=request.user)
        except ValidationError as error:
            preview_errors = review_messages(error.messages)
        if generation_form is None and preview:
            generation_form = GenerateResultsForm(initial={key: preview[key] for key in ('version', 'expected', 'selection_reason')})
        elif generation_form is not None and preview:
            # A failed stale submission displays the new list and its new token.
            # Publishing still requires another explicit click on that list.
            generation_form.data = generation_form.data.copy()
            generation_form.data.update({key: preview[key] for key in ('version', 'expected')})
    if request.method == 'POST' and not generating and form.is_valid():
        selected = form.cleaned_data['program']
        # Selecting a program first loads its actual current revision for review.
        if program is None:
            return redirect('announcements:prepare_results', program_id=selected.pk)
        try:
            saved = prepare_results(program.pk, user=request.user, version=form.cleaned_data['version'],
                reason='Administrator prepared the program applicant and selected-member tables.',
                address=request.META.get('REMOTE_ADDR'), roster=True)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Private result draft prepared. Review the exact public preview before authorizing publication.')
            if request.headers.get('X-Announcement-Dialog') == '1':
                return redirect('announcements:prepare_results', program_id=program.pk)
            return redirect('announcements:manage_detail', pk=saved.pk)
    from .catalog import result_program_cards
    cards = result_program_cards(request, selected_program=program)
    roster = preview['payload'] if preview else None
    if program and roster is None:
        try:
            roster = review_roster(program)
        except ValidationError as error:
            preview_errors.extend(review_messages(error.messages))
    if program and roster:
        roster = admin_projection(program, roster, user=request.user)
    from .certificate_delivery import certificate_context
    return render(request, 'announcements/result_draft.html', {**cards,
        **certificate_context(program, request.user), 'form': form, 'program': program,
        'generation_form': generation_form, 'preview': preview, 'roster': roster, 'preview_errors': preview_errors,
        'review_pool': review_pool(program, roster) if program and roster else None,
        'landing': landing, 'review_url': _requested_review_url(request)})
