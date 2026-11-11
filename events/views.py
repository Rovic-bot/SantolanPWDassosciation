from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from accounts.decorators import dashboard_required
from announcements.views import image_response
from core.permissions import require_workspace_permissions
from .forms import AttendanceForm, EventActionForm, EventForm, OpenAttendanceForm, PublishEventForm, RegistrationForm
from .models import Event, EventAttendance, EventRegistration
from .services import (change_publication, change_registration, occupied_slots, publish_event, register_member,
                       reserve_verification, save_attendance, save_event,
                       public_observance_calendar)


@never_cache
@require_safe
def public_list(request):
    period = request.GET.get('period', 'upcoming')
    if period not in ('upcoming', 'past'):
        period = 'upcoming'
    items = Event.objects.public()
    now = timezone.now()
    items = (items.filter(ends_at__lt=now).order_by('-starts_at', '-pk') if period == 'past'
             else items.filter(ends_at__gte=now).order_by('starts_at', 'pk'))
    months = public_observance_calendar()
    return render(request, 'events/public_list.html', {'observance_months': months,
        'period': period, 'event_display_time': now,
        'events': items,
        'has_observances': any(month['observances'] for month in months)})


@never_cache
@dashboard_required
@require_safe
def observances(request):
    from .workspace import observance_context
    require_workspace_permissions(request.user, 'events.view_annualobservance')
    return render(request, 'events/observances.html', observance_context(request.user))


def _require_observance_storage():
    from django.core.exceptions import ValidationError
    from .services import observance_storage_ready
    if not observance_storage_ready():
        raise ValidationError('Annual observance storage is awaiting local migration approval.')


def _observance_storage_or_404():
    from django.http import Http404
    from .services import observance_storage_ready
    if not observance_storage_ready():
        raise Http404


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def observance_edit(request, pk=None):
    from dataclasses import asdict
    from .models import AnnualObservance
    from .observances import REFERENCE_CATALOGUE
    from .observance_forms import AnnualObservanceEditForm
    from .services import save_observance
    require_workspace_permissions(request.user, 'events.view_annualobservance',
        'events.change_annualobservance' if pk else 'events.add_annualobservance')
    if pk:
        require_workspace_permissions(request.user, 'events.publish_annualobservance')
    try:
        _require_observance_storage()
    except ValidationError as error:
        return render(request, 'events/observance_unavailable.html', {'error': error.messages[0]}, status=503)
    item = get_object_or_404(AnnualObservance, pk=pk) if pk else AnnualObservance()
    if item.status == 'archived':
        messages.error(request, 'Restore this observance to draft before editing.')
        return redirect('events:observance_detail', pk=item.pk)
    reference = next((item for item in REFERENCE_CATALOGUE if str(item.month) == request.GET.get('reference')), None)
    initial = asdict(reference) if reference and not pk else {}
    form_class = AnnualObservanceEditForm
    form = form_class(request.POST if request.method == 'POST' else None,
        request.FILES or None, instance=item, initial=initial, publishing=bool(pk))
    status = 200
    if request.method == 'POST':
        if getattr(request, 'upload_limit_exceeded', False):
            form.add_error(None, 'The upload is too large. Choose a smaller photo.')
            status = 413
        elif form.is_valid():
            try:
                saved = save_observance(user=request.user, data=request.POST, files=request.FILES,
                    pk=pk, address=request.META.get('REMOTE_ADDR'), publish=bool(pk), simplified_editor=True)
            except ValidationError as error:
                form.add_error(None, '; '.join(error.messages))
            else:
                if pk:
                    messages.success(request, 'Observance updated and published.')
                    return redirect('events:observances')
                messages.success(request, 'Draft saved. Review the card before publishing.')
                return redirect('events:observance_detail', pk=saved.pk)
    template = 'events/observance_edit.html' if pk else 'events/observance_create.html'
    return render(request, template, {'form': form, 'observance': item,
        'editing': bool(pk), 'image_limit_mb': settings.EVENT_IMAGE_MAX_BYTES // 1048576}, status=status)


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def observance_detail(request, pk):
    from .models import AnnualObservance
    from .observance_forms import ObservancePublicationForm
    from .services import OBSERVANCE_TRANSITIONS, change_observance_publication
    require_workspace_permissions(request.user, 'events.view_annualobservance')
    _observance_storage_or_404()
    item = get_object_or_404(AnnualObservance, pk=pk)
    actions = OBSERVANCE_TRANSITIONS[item.status] if request.user.has_perm('events.publish_annualobservance') else ()
    form = ObservancePublicationForm(request.POST if request.method == 'POST' else None,
        actions=actions, initial={'version': item.version})
    if request.method == 'POST':
        require_workspace_permissions(request.user, 'events.publish_annualobservance')
        if form.is_valid():
            try:
                change_observance_publication(item.pk, user=request.user,
                    version=form.cleaned_data['version'], action=form.cleaned_data['action'],
                    notes=form.cleaned_data['notes'], address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                form.add_error(None, '; '.join(error.messages))
            else:
                messages.success(request, 'Publication status updated and recorded in history.')
                return redirect('events:observance_detail', pk=item.pk)
    revisions = item.revisions.all() if request.user.has_perm('events.view_annualobservancerevision') else None
    logs = item.history.all() if request.user.has_perm('events.view_annualobservancelog') else None
    return render(request, 'events/observance_detail.html', {'observance': item, 'form': form, 'actions': actions,
        'revisions': Paginator(revisions, 10).get_page(request.GET.get('revision_page')) if revisions is not None else None,
        'logs': Paginator(logs, 10).get_page(request.GET.get('log_page')) if logs is not None else None})


@never_cache
@require_safe
def observance_public_detail(request, pk):
    from .models import AnnualObservance
    _observance_storage_or_404()
    item = get_object_or_404(AnnualObservance.objects.public(), pk=pk)
    public = {name: getattr(item, name) for name in ('pk', 'title', 'description', 'recurrence_rule',
        'legal_basis', 'source_url', 'target_audience', 'who_may_participate', 'image_alt')}
    public.update(image=bool(item.image), category_label=item.get_category_display())
    template = 'events/observance_public_popup.html' if request.GET.get('popup') == '1' else 'events/observance_public_detail.html'
    return render(request, template, {'observance': public})


@never_cache
@require_safe
def observance_image(request, pk):
    from .models import AnnualObservance
    _observance_storage_or_404()
    return image_response(get_object_or_404(AnnualObservance.objects.public(), pk=pk))


@never_cache
@dashboard_required
@require_safe
def observance_preview_image(request, pk):
    from .models import AnnualObservance
    require_workspace_permissions(request.user, 'events.view_annualobservance')
    _observance_storage_or_404()
    return image_response(get_object_or_404(AnnualObservance, pk=pk))


@never_cache
@dashboard_required
@require_safe
def observance_revision_image(request, pk, revision_id):
    from .models import AnnualObservanceRevision
    require_workspace_permissions(request.user, 'events.view_annualobservance', 'events.view_annualobservancerevision')
    _observance_storage_or_404()
    return image_response(get_object_or_404(AnnualObservanceRevision, pk=revision_id, observance_id=pk))


@never_cache
@require_safe
def public_detail(request, pk):
    item = get_object_or_404(Event.objects.public(), pk=pk)
    if request.GET.get('popup') == '1':
        return render(request, 'events/public_popup.html', {'event': item})
    # Keep existing links useful, but event details only open in the list popup.
    period = '?period=past' if item.ends_at < timezone.now() else ''
    return redirect(reverse('core:events') + period + '#scheduled-events')


@never_cache
@require_safe
def public_image(request, pk):
    return image_response(get_object_or_404(Event.objects.public(), pk=pk))


@never_cache
@dashboard_required
@require_safe
def preview_image(request, pk):
    require_workspace_permissions(request.user, 'events.view_event')
    return image_response(get_object_or_404(Event, pk=pk))


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def register(request, pk):
    from django.http import HttpResponseGone
    return HttpResponseGone('Only Verified Members can apply through the event’s linked Program Application. Contact the Association Help Desk for assistance.')


@never_cache
@require_safe
def registered(request, pk):
    from django.http import HttpResponseGone
    return HttpResponseGone('Keep your Program Application reference and monitor official Announcements. Contact the Association Help Desk for assistance.')


@never_cache
@dashboard_required
@require_safe
def manage_list(request):
    require_workspace_permissions(request.user, 'events.view_event')
    from .workspace import workspace_context
    return render(request, 'events/manage_list.html', workspace_context(request))


@never_cache
@dashboard_required
@require_safe
def calendar_workspace(request):
    from .workspace import workspace_context
    if not request.user.has_perm('events.view_event'):
        require_workspace_permissions(request.user, 'events.view_annualobservance')
    return render(request, 'events/manage_list.html', workspace_context(request))


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def edit(request, pk=None):
    require_workspace_permissions(request.user, 'events.view_event', 'events.change_event' if pk else 'events.add_event')
    item = get_object_or_404(Event, pk=pk) if pk else Event()
    if item.status in ('published', 'cancelled'):
        require_workspace_permissions(request.user, 'events.publish_event')
    form = EventForm(request.POST if request.method == 'POST' else None, request.FILES or None, instance=item, user=request.user)
    status_code = 200
    if request.method == 'POST':
        if getattr(request, 'upload_limit_exceeded', False):
            form.add_error(None, 'The upload is too large. Choose a smaller image.')
            status_code = 413
        elif form.is_valid():
            try:
                saved = save_event(user=request.user, data=request.POST, files=request.FILES, pk=pk,
                                   address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Event saved.' if pk else 'Draft saved. Review the event before publishing.')
                return redirect('events:manage_detail', pk=saved.pk)
    return render(request, 'events/builder/page.html', {'event': item, 'form': form, 'editing': bool(pk),
        'image_limit_mb': settings.EVENT_IMAGE_MAX_BYTES // 1048576}, status=status_code)


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def manage_detail(request, pk):
    require_workspace_permissions(request.user, 'events.view_event')
    item = get_object_or_404(Event, pk=pk)
    actions = [(value, label) for value, label in Event.Status.choices if value != item.status
               and (value != 'cancelled' or item.published_at)] if request.user.has_perm('events.publish_event') else []
    can_publish = any(value == 'published' for value, label in actions)
    can_unpublish = item.status == 'published' and any(value == 'draft' for value, label in actions)
    unpublishing = can_unpublish and (request.GET.get('action') == 'draft'
        or (request.method == 'POST' and request.POST.get('action') == 'draft'))
    actions = [(value, label) for value, label in actions if value != 'published']
    publishing = request.method == 'POST' and request.POST.get('action') == 'published'
    return_to_list = publishing and request.POST.get('return_to') == 'list'
    publish_form = PublishEventForm(request.POST if publishing else None,
                                    auto_id='id_publish_%s', initial={'version': item.version})
    form = EventActionForm(request.POST if request.method == 'POST' and not publishing else None,
                           actions=[('draft', 'Unpublish event')] if unpublishing else actions,
                           unpublishing=unpublishing,
                           initial={'version': item.version, 'action': 'draft' if unpublishing else ''})
    if request.method == 'POST':
        require_workspace_permissions(request.user, 'events.publish_event')
        submitted = publish_form if publishing else form
        if submitted.is_valid():
            try:
                if publishing:
                    publish_event(pk, user=request.user, version=publish_form.cleaned_data['version'],
                        address=request.META.get('REMOTE_ADDR'))
                else:
                    change_publication(pk, user=request.user, version=form.cleaned_data['version'],
                        action=form.cleaned_data['action'], notes=form.cleaned_data['notes'],
                        address=request.META.get('REMOTE_ADDR'))
            except ValidationError as error:
                submitted.add_error(None, '; '.join(error.messages))
            else:
                messages.success(request, 'Event published.' if publishing else
                    'Event unpublished. It is now a private draft.' if unpublishing else
                    'Event status updated. History is retained.')
                if return_to_list:
                    return redirect('events:manage_list')
                return redirect('events:manage_detail', pk=pk)
        if return_to_list:
            messages.error(request, f'{item.title}: ' + '; '.join(
                str(error) for errors in submitted.errors.values() for error in errors))
            return redirect('events:manage_list')
    history = item.history.filter(registration__isnull=True)
    return render(request, 'events/manage_detail.html', {'event': item, 'form': form, 'actions': actions,
        'publish_form': publish_form, 'can_publish': can_publish,
        'can_unpublish': can_unpublish, 'unpublishing': unpublishing,
        'can_edit': request.user.has_perm('events.change_event')
            and (item.status not in ('published', 'cancelled') or request.user.has_perm('events.publish_event')),
        'history': Paginator(history, 20).get_page(request.GET.get('page')) if request.user.has_perm('events.view_eventlog') else None})


@never_cache
@dashboard_required
@require_safe
def registrations(request, pk):
    require_workspace_permissions(request.user, 'events.view_event', 'events.view_eventregistration')
    item = get_object_or_404(Event, pk=pk)
    records = item.registrations.select_related('member')
    query = request.GET.get('q', '').strip()[:200]
    if query:
        from core.reference_services import filter_reference
        records = filter_reference(records, 'event', query, Q(member__full_name__icontains=query) |
            Q(member__control_number__icontains=query) | Q(reference__icontains=query))
    status = request.GET.get('status', '')
    if status in EventRegistration.Status.values:
        records = records.filter(status=status)
    else:
        status = ''
    return render(request, 'events/registrations.html', {'event': item, 'query': query, 'status': status,
        'statuses': EventRegistration.Status.choices, 'occupied': occupied_slots(item),
        'page_obj': Paginator(records, 20).get_page(request.GET.get('page'))})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def registration_detail(request, pk, reference):
    require_workspace_permissions(request.user, 'events.view_event', 'events.view_eventregistration')
    registration = get_object_or_404(EventRegistration.objects.select_related('event', 'member'), pk=reference, event_id=pk)
    form = AttendanceForm(request.POST if request.method == 'POST' else None,
                           initial={'version': registration.version, 'status': registration.status})
    if request.method == 'POST':
        require_workspace_permissions(request.user, 'events.change_eventregistration')
        if form.is_valid():
            try:
                change_registration(reference, user=request.user, address=request.META.get('REMOTE_ADDR'), **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Registration status updated and recorded in history.')
                return redirect('events:registration_detail', pk=pk, reference=reference)
    return render(request, 'events/registration_detail.html', {'registration': registration,
        'event': registration.event, 'form': form, 'history': (Paginator(registration.history.all(), 20).get_page(request.GET.get('page'))
            if request.user.has_perm('events.view_eventlog') else None)})


@never_cache
@dashboard_required
@require_safe
def attendance_list(request, pk):
    require_workspace_permissions(request.user, 'events.view_event', 'events.view_eventattendance')
    event = get_object_or_404(Event, pk=pk)
    records = event.attendance.all()
    query = request.GET.get('q', '').strip()[:200]
    if query:
        from core.reference_services import filter_reference
        records = filter_reference(records, 'attendance', query,
            Q(attendee_name__icontains=query) | Q(reference__icontains=query))
    status = request.GET.get('status', '')
    if status in EventAttendance.Status.values:
        records = records.filter(status=status)
    else:
        status = ''
    return render(request, 'events/attendance_list.html', {'event': event, 'query': query, 'status': status,
        'statuses': EventAttendance.Status.choices, 'attended_count': event.attendance.filter(status='attended').count(),
        'page_obj': Paginator(records, 20).get_page(request.GET.get('page'))})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def attendance_detail(request, pk, reference=None):
    require_workspace_permissions(request.user, 'events.view_event', 'events.view_eventattendance')
    event = get_object_or_404(Event, pk=pk)
    item = get_object_or_404(EventAttendance, pk=reference, event=event) if reference else EventAttendance(event=event)
    if not reference or request.method == 'POST':
        require_workspace_permissions(request.user, 'events.change_eventattendance' if reference else 'events.add_eventattendance')
    form = OpenAttendanceForm(request.POST if request.method == 'POST' else None, user=request.user,
        initial={'submission_key': item.pk, 'version': item.version, 'attendee_name': item.attendee_name,
                 'member': item.member_id, 'status': item.status})
    if request.method == 'POST' and form.is_valid():
        try:
            saved = save_attendance(pk, user=request.user, data=request.POST, reference=reference,
                                    address=request.META.get('REMOTE_ADDR'))
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'Attendance saved and recorded in history.')
            return redirect('events:attendance_detail', pk=pk, reference=saved.pk)
    return render(request, 'events/attendance_detail.html', {'event': event, 'attendance': item,
        'editing': bool(reference), 'form': form, 'can_save': request.user.has_perm(
            'events.change_eventattendance' if reference else 'events.add_eventattendance'),
        'history': (Paginator(item.history.all(), 20).get_page(request.GET.get('page'))
                    if reference and request.user.has_perm('events.view_eventattendancelog') else None)})
