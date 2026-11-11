"""Private visual editor; public pages read published snapshots only."""
from copy import deepcopy
import json
import uuid

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.urls import resolve, reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from django.views.decorators.clickjacking import xframe_options_sameorigin

from accounts.decorators import dashboard_required
from announcements.images import prepare_image
from .content import current_editor
from .permissions import require_workspace_permissions
from .portal_models import PortalPage, PortalPageRevision
from .portal_fields import FIELDS

PAGES = (
    ('home', 'Home', 'core:home'), ('about', 'About', 'core:about'),
    ('announcements', 'Announcements', 'core:announcements'), ('events', 'Events', 'core:events'),
    ('programs', 'Programs', 'core:programs'),
    ('membership', 'Membership & PWD ID', 'core:membership'),
    ('resources', 'Resources & Help', 'core:resources'),
)
PAGE_MAP = {key: (label, route) for key, label, route in PAGES}
ROUTE_PAGES = {route: key for key, _, route in PAGES}
ROUTE_PAGES['programs:list'] = 'programs'


def page_key(key):
    if key not in PAGE_MAP:
        raise Http404
    return key


def state_for(request):
    if hasattr(request, '_portal_state'):
        return request._portal_state
    key = getattr(request, '_portal_page', None) or ROUTE_PAGES.get(getattr(request.resolver_match, 'view_name', ''))
    preview = bool(getattr(request, '_portal_preview', False))
    item = PortalPage.objects.filter(pk=key).first() if key else None
    state = {'key': key, 'preview': preview, 'values': (item.content if preview else item.published) if item else {}}
    request._portal_state = state
    return state


def snapshot(item):
    return {'content': deepcopy(item.content), 'published': deepcopy(item.published), 'version': item.version}


def save_page(key, *, user, version, changes, files, reset=None):
    page_key(key)
    reset = [] if reset is None else reset
    actor = current_editor(user)
    publish = actor.has_perm('core.publish_publiccontent')
    if (not isinstance(changes, dict) or not isinstance(reset, list)
            or any(not isinstance(name, str) for name in reset)):
        raise ValidationError('Choose valid page changes.')
    fields = FIELDS[key]
    if set(changes) - fields.keys() or set(files) - fields.keys() or set(reset) - fields.keys():
        raise ValidationError('One of these fields cannot be edited on this page.')
    if set(changes) & set(reset) or set(files) & set(reset):
        raise ValidationError('Reset a field or change it, not both.')
    cleaned = {}
    for name, value in changes.items():
        if fields[name]['kind'] != 'text' or not isinstance(value, str) or len(value) > 20000:
            raise ValidationError('Enter plain text of no more than 20,000 characters per field.')
        cleaned[name] = value.strip()
    images = {}
    for name, upload in files.items():
        if fields[name]['kind'] != 'image':
            raise ValidationError('Choose a picture field for this upload.')
        images[name] = prepare_image(upload)
    written = []
    try:
        with transaction.atomic():
            item, _ = PortalPage.objects.get_or_create(key=key)
            item = PortalPage.objects.select_for_update().get(pk=key)
            if item.version != version:
                raise ValidationError('This page was changed by another editor. Reload it before saving.')
            if not (cleaned or images or reset) and not (publish and item.content != item.published):
                raise ValidationError('There are no changes to save.')
            before = snapshot(item)
            values = deepcopy(item.content)
            for name in reset:
                values.pop(name, None)
            values.update(cleaned)
            for name, image in images.items():
                stored = default_storage.save(f'portal-artwork/{key}/{uuid.uuid4().hex}.png', image)
                written.append(stored)
                values[name] = {'file': stored, 'token': uuid.uuid4().hex}
            item.content = values
            if publish:
                current_editor(user, publication=True)
                item.published = deepcopy(values)
            item.version += 1
            item.updated_by = actor
            item.save()
            actor = current_editor(user, publication=publish)
            PortalPageRevision.objects.create(page=item, actor=actor, actor_label=actor.get_username(),
                version=item.version, action='publish' if publish else 'draft', before=before, after=snapshot(item))
            return item, publish
    except Exception:
        for name in written:
            default_storage.delete(name)
        raise


@never_cache
@dashboard_required
@require_safe
def editor(request):
    require_workspace_permissions(request.user, 'core.view_publiccontent')
    key = request.GET.get('page', 'home')
    page_key(key)
    can_edit = request.user.has_perm('core.change_publiccontent')
    return render(request, 'content/portal_editor.html', {
        'portal_pages': PAGES, 'selected_page': key, 'can_edit': can_edit,
        'can_publish': request.user.has_perm('core.publish_publiccontent'),
        'editor_config': {'selected': key, 'canEdit': can_edit,
            'canPublish': request.user.has_perm('core.publish_publiccontent'), 'pages': {
            page: {'label': label, 'publicUrl': reverse(route),
                   'previewUrl': reverse('core:portal_preview', args=[page]),
                   'saveUrl': reverse('core:portal_save', args=[page]),
                   'stateUrl': reverse('core:portal_state', args=[page])}
            for page, label, route in PAGES}},
    })


@never_cache
@dashboard_required
@require_safe
def editor_state(request, key):
    page_key(key)
    require_workspace_permissions(request.user, 'core.view_publiccontent')
    item = PortalPage.objects.filter(pk=key).first()
    return JsonResponse({'version': item.version if item else 0,
        'hasDraft': bool(item and item.content != item.published)})


@never_cache
@dashboard_required
@require_http_methods(['POST'])
def save(request, key):
    page_key(key)
    current_editor(request.user)
    if getattr(request, 'upload_limit_exceeded', False):
        return JsonResponse({'error': 'The upload is too large. Choose a smaller picture.'}, status=413)
    try:
        version = int(request.POST.get('version', '-1'))
        changes = json.loads(request.POST.get('changes', '{}'))
        reset = json.loads(request.POST.get('reset', '[]'))
        if version < 0:
            raise ValueError
        item, published = save_page(key, user=request.user, version=version,
            changes=changes, files=request.FILES, reset=reset)
    except (ValueError, TypeError):
        return JsonResponse({'error': 'The page changes could not be read. Reload and try again.'}, status=400)
    except ValidationError as error:
        return JsonResponse({'error': ' '.join(error.messages)}, status=400)
    return JsonResponse({'version': item.version, 'published': published,
        'message': 'Saved to the public portal.' if published else 'Draft saved. A publisher can review and save it to the public portal.'})


@never_cache
@dashboard_required
@require_safe
@xframe_options_sameorigin
def preview(request, key):
    page_key(key)
    require_workspace_permissions(request.user, 'core.view_publiccontent')
    request._portal_preview = True
    request._portal_page = key
    match = resolve(reverse(PAGE_MAP[key][1]))
    request.resolver_match = match
    response = match.func(request, *match.args, **match.kwargs)
    response['Content-Security-Policy'] = "frame-ancestors 'self'"
    return response


@never_cache
@require_safe
def image(request, key, field, token):
    page_key(key)
    if FIELDS[key].get(field, {}).get('kind') != 'image':
        raise Http404
    item = PortalPage.objects.filter(pk=key).first()
    if not item:
        raise Http404
    value = item.published.get(field)
    if request.GET.get('preview') == '1':
        require_workspace_permissions(request.user, 'core.view_publiccontent')
        value = item.content.get(field)
    if not isinstance(value, dict) or value.get('token') != token:
        raise Http404
    try:
        handle = default_storage.open(value['file'], 'rb')
    except FileNotFoundError:
        raise Http404
    response = FileResponse(handle, content_type='image/png')
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return response
