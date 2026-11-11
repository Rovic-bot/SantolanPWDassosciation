"""Read-only search and presentation for the authorized Association inbox."""
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, F, Q

from .models import MembershipApplication
from .registration_models import RegistrationIntake
from .registration_services import normalize_reference
from core.reference_services import parse_code


def inbox_context(params):
    records = RegistrationIntake.objects.filter(category='association')
    query = params.get('q', '').strip()[:200]
    legacy_reference = 'reference' in params
    if legacy_reference:
        query = params.get('reference', '').strip()[:200]
    reference_search = legacy_reference or query.upper().startswith('AMR-') or parse_code('association', query) is not None
    state = params.get('state', '').strip()[:40]
    tab = params.get('tab', 'all' if query or legacy_reference or state else 'awaiting')
    states = RegistrationIntake._meta.get_field('state').choices
    reference_error = filter_error = ''

    # A complete reference presented at the Help Desk must not be hidden by
    # stale filters. Keep the legacy reference URL's exact-match behavior.
    if reference_search:
        tab, state = 'all', ''
        try:
            records = records.filter(reference=normalize_reference(query))
        except ValidationError as error:
            records = records.none()
            reference_error = error.messages[0]
    else:
        if query:
            # Search only the current form revision, never correction history.
            records = records.filter(revisions__number=F('current_revision'),
                                     revisions__data__full_name__icontains=query)
        if state and state not in dict(states):
            records = records.none()
            filter_error = 'Choose a listed processing status.'
        else:
            if state:
                records = records.filter(state=state)
        if tab not in ('awaiting', 'completed', 'all'):
            records = records.none()
            filter_error = 'Choose a listed registration tab.'
            tab = 'awaiting'

    completed = Q(membership_application__status__in=(
        MembershipApplication.Status.APPROVED, MembershipApplication.Status.REJECTED))
    counts = records.aggregate(all=Count('pk'), completed=Count('pk', filter=completed))
    counts['awaiting'] = counts['all'] - counts['completed']
    if tab == 'completed':
        records = records.filter(completed)
    elif tab == 'awaiting':
        records = records.exclude(completed)
    page = Paginator(records.select_related('membership_application').prefetch_related('revisions'), 20).get_page(params.get('page'))
    for item in page:
        item.submitted = next(revision.data for revision in item.revisions.all()
                              if revision.number == item.current_revision)
        decision = item.membership_application.status if item.membership_application_id else None
        if decision in (MembershipApplication.Status.APPROVED, MembershipApplication.Status.REJECTED):
            item.inbox_status = item.membership_application.get_status_display()
            item.inbox_status_style = decision
            item.inbox_completed = True
        else:
            item.inbox_status = ('Awaiting onsite' if item.state == 'received'
                                 else item.get_state_display())
            item.inbox_status_style = 'awaiting'
            item.inbox_completed = False
    return {
        'page_obj': page, 'search_query': query, 'reference_query': query if reference_search else '',
        'reference_error': reference_error, 'filter_error': filter_error,
        'state_query': state, 'states': states,
        'reference_search': reference_search, 'active_tab': tab, 'tab_counts': counts,
        'tab_search_query': '' if reference_search else query,
    }
