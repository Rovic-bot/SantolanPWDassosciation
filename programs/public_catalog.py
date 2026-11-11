"""Public catalog presentation; application policy remains in the existing services."""
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Case, CharField, Count, F, Q, Value, When
from django.utils import timezone

from .application_workflow import availability, enabled
from .models import Program
from .publication_recency import newly_published_condition
from .public_deadlines import prepare_registration_notice


def catalog_context(request):
    at = timezone.now()
    items = Program.objects.public(at=at).with_public_application_status(at=at)
    categories = list(items.exclude(assistance_type='').order_by('assistance_type')
        .values_list('assistance_type', flat=True).distinct())
    query = request.GET.get('q', '').strip()[:200]
    category = request.GET.get('category', '')[:120]
    if category not in categories:
        category = ''
    if query:
        items = items.filter(Q(name__icontains=query) | Q(description__icontains=query)
            | Q(assistance_type__icontains=query))
    if category:
        items = items.filter(assistance_type=category)

    # Counts and cards use the same readiness check as the application flow,
    # including programs awaiting approved EWAF configuration.
    if enabled():
        not_ready = [item.pk for item in items.filter(public_application_status='open')
            .select_related('organizational_event') if not availability(item)]
        if not_ready:
            items = items.annotate(public_application_status=Case(
                When(pk__in=not_ready, then=Value('unavailable')),
                default=F('public_application_status'), output_field=CharField()))

    periods = [('all', 'All programs'), ('new', 'New'), ('available', 'Open'), ('upcoming', 'Upcoming'),
        ('past', 'Closed'), ('unavailable', 'Unavailable')]
    conditions = {'all': Q(),
        'new': newly_published_condition(at),
        'available': Q(public_application_status='open'),
        'upcoming': Q(status='published', registration_opens_at__gt=at),
        'past': Q(registration_closes_at__lte=at),
        'unavailable': Q(public_application_status__in=['cancelled', 'unavailable']),
        'current': Q(registration_closes_at__gt=at)}
    period = request.GET.get('period', 'all')
    if period not in conditions:
        period = 'all'
    if period == 'current':
        periods.append(('current', 'Current application periods'))
    counts = items.aggregate(**{value: Count('pk', filter=conditions[value]) for value, _ in periods})
    items = items.filter(conditions[period])
    if period == 'new':
        items = items.order_by('-published_at', '-pk')
    elif period == 'available':
        items = items.order_by('registration_closes_at', 'pk')
    elif period == 'upcoming':
        items = items.order_by('registration_opens_at', 'pk')
    elif period == 'past':
        items = items.order_by('-registration_closes_at', '-pk')
    result_page = Paginator(items.select_related('picture_asset'), 6).get_page(request.GET.get('page'))
    for program in result_page:
        prepare_registration_notice(program, at=at)

    def link(selected_period=period, page_number=None):
        params = {'period': selected_period}
        if query:
            params['q'] = query
        if category:
            params['category'] = category
        if page_number is not None:
            params['page'] = page_number
        return '?' + urlencode(params)

    return {'page_obj': result_page, 'period': period, 'periods': periods,
        'period_label': dict(periods)[period], 'query': query, 'category': category, 'categories': categories,
        'period_filters': [{'value': value, 'label': label, 'count': counts[value], 'url': link(value)}
            for value, label in periods],
        'page_links': [{'number': number, 'url': link(page_number=number) if isinstance(number, int) else ''}
            for number in result_page.paginator.get_elided_page_range(result_page.number, on_each_side=1, on_ends=1)],
        'previous_page_url': link(page_number=result_page.previous_page_number()) if result_page.has_previous() else '',
        'next_page_url': link(page_number=result_page.next_page_number()) if result_page.has_next() else '',
    }
