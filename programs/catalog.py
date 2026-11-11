"""Shared private program-card search, filters and deterministic ordering."""
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.utils import timezone
from .models import Program
from .publication_recency import newly_published_condition

SORTS = (
    ('newest', 'Newest created first'), ('oldest', 'Oldest created first'),
    ('az', 'Alphabetically A–Z'), ('za', 'Alphabetically Z–A'),
    ('start', 'Program start date'), ('end', 'Program end date'),
)
REGISTRATION = (('open', 'Open'), ('upcoming', 'Not yet open'), ('ended', 'Closed'),
                ('unavailable', 'Unavailable'))
STATUSES = tuple((value, label) for value, label in Program.Status.choices if value != 'cancelled')


def program_cards(request, queryset=None, *, include_new=False):
    at = timezone.now()
    programs = Program.objects.all() if queryset is None else queryset
    statuses = (*STATUSES, ('new', 'New (last hour)')) if include_new else STATUSES
    types = list(Program.objects.exclude(assistance_type='').order_by('assistance_type').values_list('assistance_type', flat=True).distinct())
    query = request.GET.get('q', '').strip()[:200]
    assistance_type = request.GET.get('assistance_type', '')
    status = request.GET.get('status', '')
    registration = request.GET.get('registration', '')
    sort = request.GET.get('sort', 'newest')
    sort = sort if sort in dict(SORTS) else 'newest'
    programs = programs.annotate(applicant_count=Count('applications', distinct=True)).with_public_application_status(at=at)
    if query:
        programs = programs.filter(Q(name__icontains=query) | Q(public_code__icontains=query) |
                                   Q(description__icontains=query) | Q(assistance_type__icontains=query))
    if assistance_type in types:
        programs = programs.filter(assistance_type=assistance_type)
    else:
        assistance_type = ''
    if include_new and status == 'new':
        programs = programs.filter(newly_published_condition(at))
    elif status in dict(STATUSES):
        programs = programs.filter(status=status)
    else:
        status = ''
    if registration in dict(REGISTRATION):
        programs = programs.filter(public_application_status=registration)
    else:
        registration = ''
    has_applications = request.GET.get('with_applications') == '1'
    if has_applications:
        programs = programs.filter(applicant_count__gt=0)
    newest_field = '-published_at' if status == 'new' else '-created_at'
    sort_options = tuple((value, 'Newest published first' if status == 'new' and value == 'newest' else label)
                         for value, label in SORTS)
    ordering = {'newest': (newest_field, '-pk'), 'oldest': ('created_at', 'pk'),
                'az': ('name', 'pk'), 'za': ('-name', 'pk'),
                'start': (F('starts_at').asc(nulls_last=True), 'pk'),
                'end': (F('ends_at').asc(nulls_last=True), 'pk')}[sort]
    page = Paginator(programs.order_by(*ordering), 20).get_page(request.GET.get('page'))
    for program in page:
        capacity_context(program, request.user)
    return {'page_obj': page,
            'query': query, 'assistance_types': types, 'assistance_type': assistance_type,
            'statuses': statuses, 'status': status, 'registration_options': REGISTRATION,
            'registration': registration, 'sort_options': sort_options, 'sort': sort,
            'with_applications': has_applications}


def capacity_context(program, user):
    """Present the same reservations enforced by beneficiary selection."""
    from assistance.services import VIEW_PERMISSIONS, reserved_slots
    program.can_view_capacity = user.has_perms(VIEW_PERMISSIONS)
    program.allocated_slots = reserved_slots(program) if program.can_view_capacity else None
    program.available_slots = (max(0, program.slot_limit - program.allocated_slots)
                               if program.can_view_capacity and program.slot_limit is not None else None)
    program.usage_percent = (min(100, round(100 * program.allocated_slots / program.slot_limit))
                             if program.can_view_capacity and program.slot_limit else None)
    return program
