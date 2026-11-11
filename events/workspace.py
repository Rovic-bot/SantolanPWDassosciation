"""Read-only presentation for the private event agenda and annual calendar."""
from calendar import Calendar, month_abbr, month_name
from datetime import date, datetime, time, timedelta
from zlib import crc32

from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .models import AnnualObservance, Event
from .services import observance_storage_ready


def observance_context(user) -> dict:
    allowed = user.has_perm('events.view_annualobservance')
    ready = observance_storage_ready() if allowed else False
    records = list(AnnualObservance.objects.order_by('month', 'title', 'pk')) if ready else []
    can_edit = user.has_perms(('events.change_annualobservance', 'events.publish_annualobservance'))
    months = []
    for month in range(1, 13):
        rows = []
        for record in records:
            if record.month == month:
                rows.append({'record': record, 'url': reverse(
                    'events:observance_edit' if can_edit and record.status != 'archived'
                    else 'events:observance_detail', args=[record.pk])})
        months.append({'number': month, 'name': month_name[month], 'abbr': month_abbr[month], 'rows': rows})
    return {'can_view_observances': allowed, 'storage_ready': ready,
        'observance_count': sum(record.status == 'published' and record.published_at is not None
            and record.published_at <= timezone.now() for record in records),
        'quarters': [{'number': index + 1, 'range': f'{month_abbr[index * 3 + 1]} – {month_abbr[index * 3 + 3]}',
                      'months': months[index * 3:index * 3 + 3]} for index in range(4)]}


def event_presentation(item, user) -> dict:
    linked = item.application_program
    colors = {'healthcare': 'blue', 'medical': 'blue', 'assistive devices': 'violet',
              'livelihood': 'orange', 'community': 'green', 'education': 'orange', 'food & nutrition': 'magenta'}
    accents = ('blue', 'violet', 'green', 'orange', 'magenta')
    accent = colors.get(linked.assistance_type.casefold()) if linked else None
    # Decorative accents do not change historical event data.
    if not accent:
        for words, color in ((('medical', 'health'), 'blue'), (('assistive', 'distribution'), 'violet'),
                             (('livelihood', 'training', 'workshop'), 'orange'),
                             (('awareness', 'observance', 'day of'), 'magenta'), (('sports', 'community'), 'green')):
            if any(word in item.title.casefold() for word in words):
                accent = color
                break
    accent = accent or accents[crc32(str(item.pk).encode()) % len(accents)]
    return {'record': item, 'accent': accent,
        'type': 'Community event',
        'detail_url': reverse('events:manage_detail', args=[item.pk])}


def parse_day(value):
    try:
        parsed = date.fromisoformat(value)
        return parsed if 1900 <= parsed.year <= 2100 else None
    except (ValueError, TypeError):
        return None


def query_url(request, **changes):
    params = request.GET.copy()
    for key, value in changes.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return reverse('event_workspace') + ('?' + params.urlencode() if params else '')


def mini_calendar(request, items, selected_day):
    today = timezone.localdate()
    month = parse_day(request.GET.get('month', '') + '-01') or (selected_day.replace(day=1) if selected_day else today.replace(day=1))
    following = (month.replace(day=28) + timedelta(days=4)).replace(day=1)
    previous = (month - timedelta(days=1)).replace(day=1)
    start = timezone.make_aware(datetime.combine(month, time.min))
    end = timezone.make_aware(datetime.combine(following, time.min))
    scheduled = list(items.exclude(status__in=['cancelled', 'archived']).filter(
        starts_at__lt=end, ends_at__gt=start).values('starts_at', 'ends_at', 'title'))
    weeks = []
    for week in Calendar(firstweekday=6).monthdatescalendar(month.year, month.month):
        days = []
        for day in week:
            titles = [item['title'] for item in scheduled if
                timezone.localdate(item['starts_at']) <= day <= timezone.localdate(item['ends_at'] - timedelta(microseconds=1))]
            active = day.month == month.month and bool(titles)
            days.append({'day': day, 'in_month': day.month == month.month, 'active': active,
                'today': day == today, 'selected': day == selected_day, 'count': len(titles),
                'url': query_url(request, month=month.strftime('%Y-%m'), day=day.isoformat(), period='all', page=None) if active else '',
                'label': f'{day.strftime("%B %d, %Y")}: {len(titles)} event{"s" if len(titles) != 1 else ""}'})
        weeks.append(days)
    return {'month': month, 'weeks': weeks,
        'previous': query_url(request, month=previous.strftime('%Y-%m'), day=None, page=None) if previous.year >= 1900 else '',
        'next': query_url(request, month=following.strftime('%Y-%m'), day=None, page=None) if following.year <= 2100 else ''}


def workspace_context(request) -> dict:
    user, now = request.user, timezone.now()
    context = observance_context(user)
    can_view_events = user.has_perm('events.view_event')
    context['can_view_events'] = can_view_events
    if not can_view_events:
        return context
    items = Event.objects.select_related('application_program')
    upcoming = items.filter(status='published', published_at__lte=now, ends_at__gte=now)
    next_event = upcoming.order_by('starts_at', 'pk').first()
    status = request.GET.get('status', '')
    if status not in Event.Status.values:
        status = ''
    period = request.GET.get('period', 'upcoming')
    if period not in ('upcoming', 'past', 'all'):
        period = 'upcoming'
    query = request.GET.get('q', '').strip()[:200]
    if query:
        items = items.filter(Q(title__icontains=query) | Q(location__icontains=query))
    if status:
        items = items.filter(status=status)
    selected_day = parse_day(request.GET.get('day', ''))
    calendar = mini_calendar(request, items, selected_day)
    if selected_day:
        start = timezone.make_aware(datetime.combine(selected_day, time.min))
        items = items.filter(starts_at__lt=start + timedelta(days=1), ends_at__gt=start)
        period = 'all'
    elif period == 'upcoming':
        items = items.filter(ends_at__gte=now)
    elif period == 'past':
        items = items.filter(ends_at__lt=now)
    page = Paginator(items.order_by('starts_at', 'pk'), 20).get_page(request.GET.get('page'))
    context.update({'page_obj': page, 'agenda': [event_presentation(item, user) for item in page],
        'calendar': calendar, 'next_event': event_presentation(next_event, user) if next_event else None,
        'query': query, 'status': status,
        'statuses': Event.Status.choices, 'period': period, 'selected_day': selected_day,
        'all_dates_url': query_url(request, day=None, page=None)})
    return context
