"""Public notice browsing; publication and result projections remain authoritative."""
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Q
from django.urls import reverse

from .models import Announcement
from .notices import public_notice
from .public_claims import result_with_claim_status

PUBLIC_TOPICS = (('', 'All'), ('announcements', 'Announcements'), ('results', 'Program Results'))


def board_context(request):
    category = request.GET.get('category', '')
    if category in ('general', 'programs'):
        category = 'announcements'
    if category not in dict(PUBLIC_TOPICS):
        category = ''
    items = Announcement.objects.all()
    if category == 'announcements':
        items = items.filter(program__isnull=True)
    elif category == 'results':
        items = items.in_category('results')
    items = items.published()

    query = request.GET.get('q', '').strip()[:200]
    if query:
        # Search each category's published text, never legacy result content,
        # member rows, references, revision history or stale program-notice copies.
        general = Q(program__isnull=True, linked_program__isnull=True) & (
            Q(title__icontains=query) | Q(content__icontains=query))
        programs = Q(linked_program__isnull=False) & (
            Q(linked_program__name__icontains=query) | Q(linked_program__description__icontains=query))
        results = Q(program__isnull=False) & (
            Q(title__icontains=query) | Q(result_revision__public_payload__description__icontains=query))
        items = items.filter(general | programs | results)
    items = items.select_related('linked_program__picture_asset', 'program__picture_asset',
        'result_revision').order_by('-published_at', '-pk')
    # Filtered topics show one complete notice, with swipe controls following the
    # same GET pagination as the no-JavaScript links. All retains compact batches.
    page = Paginator(items, 1 if category else 24).get_page(request.GET.get('page'))
    notices = []
    for item in page.object_list:
        notice = public_notice(item)
        if category == 'results':
            # Only the authorized public projection, never admin_projection,
            # applicant_rows, legacy result content or private member records.
            notice['results'] = result_with_claim_status(item)
        elif category == 'announcements' and item.linked_program_id:
            notice['content'] = item.linked_program.description
        notices.append(notice)
    page.object_list = notices
    base_url = reverse('core:announcements')

    def link(selected_category=category, page_number=None):
        params = {}
        if selected_category:
            params['category'] = selected_category
        if query:
            params['q'] = query
        if page_number is not None:
            params['page'] = page_number
        return base_url + ('?' + urlencode(params) if params else '')

    return {'page_obj': page, 'category': category, 'categories': PUBLIC_TOPICS, 'query': query,
        'topic_links': [{'value': value, 'label': label,
            'url': link(value)}
            for value, label in PUBLIC_TOPICS],
        'page_links': [{'number': number, 'url': link(page_number=number) if isinstance(number, int) else ''}
            for number in page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1)],
        'previous_page_url': link(page_number=page.previous_page_number()) if page.has_previous() else '',
        'next_page_url': link(page_number=page.next_page_number()) if page.has_next() else '',
        'clear_search_url': base_url + ('?' + urlencode({'category': category}) if category else ''),
    }
