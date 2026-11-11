"""Announcement previews and result-publication labels for the private workspace."""
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q, F
from django.urls import reverse
from django.utils import timezone

from programs.catalog import program_cards
from programs.models import Program, ProgramApplication
from .models import Announcement


def result_program_cards(request, selected_program=None):
    applications = ProgramApplication.objects.filter(program_id=OuterRef('pk'))
    context = program_cards(request, Program.objects.filter(Exists(applications)))
    programs = list(context['page_obj'])
    items = Announcement.objects.filter(program__in=programs).select_related('program', 'result_revision')
    # Use the public portal's gate, including freshness and revision validation.
    visible = set(items.published().values_list('pk', flat=True))
    by_program = {item.program_id: item for item in items}
    now = timezone.now()
    for program in programs:
        item = by_program.get(program.pk)
        publication = {
            'label': 'Results not published', 'style': 'draft',
            'description': 'Review the applicants and selections, then publish the results.',
        }
        if item:
            if item.pk in visible:
                publication = {
                    'label': 'Results published', 'style': 'published',
                    'description': 'Visible on the public Results page.',
                    'url': reverse('core:result_detail', args=[item.pk]),
                }
            elif item.status == 'published':
                scheduled = item.published_at and item.published_at > now
                publication = {
                    'label': 'Results scheduled' if scheduled else 'Results need review',
                    'style': 'draft' if scheduled else 'cancelled',
                    'description': ('Not public until the publication date and source checks pass.' if scheduled
                                    else 'Hidden from the public portal. Review the current results before publishing again.'),
                }
            else:
                publication = {
                    'label': f'Results {item.get_status_display().lower()}', 'style': item.status,
                    'description': 'Not visible on the public Results page.',
                }
        program.result_publication = publication
    context['show_result_status'] = True
    context['applications_required'] = True
    notices = Announcement.objects.filter(program__isnull=True).exclude(status='deleted').select_related('linked_program')
    if context['query']:
        query = context['query']
        notices = notices.filter(Q(title__icontains=query) | Q(content__icontains=query)
            | Q(source_office__icontains=query) | Q(linked_program__name__icontains=query)
            | Q(linked_program__public_code__icontains=query) | Q(linked_program__description__icontains=query))
    if context['status']:
        notices = notices.filter(status=context['status'])
    if context['assistance_type']:
        notices = notices.filter(linked_program__assistance_type=context['assistance_type'])
    if context['registration']:
        matching_programs = Program.objects.with_public_application_status(at=now).filter(
            public_application_status=context['registration'])
        notices = notices.filter(linked_program__in=matching_programs)
    if context['with_applications']:
        notices = notices.filter(linked_program__applications__isnull=False).distinct()
    ordering = {'newest': ('-created_at', '-pk'), 'oldest': ('created_at', 'pk'),
                'az': ('title', 'pk'), 'za': ('-title', 'pk'),
                'start': (F('linked_program__starts_at').asc(nulls_last=True), 'pk'),
                'end': (F('linked_program__ends_at').asc(nulls_last=True), 'pk')}[context['sort']]
    notice_page = Paginator(notices.order_by(*ordering), 20).get_page(request.GET.get('notice_page'))
    notice_items = list(notice_page)
    public_notices = set(Announcement.objects.filter(pk__in=[item.pk for item in notice_items])
                        .published().values_list('pk', flat=True))
    for item in notice_items:
        item.overview_id = f'notice-{item.pk}'
        item.overview_text = item.linked_program.description if item.linked_program_id else item.content
        item.overview_public = item.pk in public_notices
        item.overview_can_edit = (request.user.has_perm('announcements.change_announcement')
            and (item.status != 'published' or request.user.has_perm('announcements.publish_announcement')))
    notice_page.object_list = notice_items
    selected = request.GET.get('selected', '') or (str(selected_program.pk) if selected_program else '')
    section = request.GET.get('section', '')
    if section not in ('announcements', 'results'):
        result_route = request.resolver_match and request.resolver_match.url_name in (
            'choose_results', 'choose_recipients', 'prepare_results', 'prepare_recipients')
        section = ('announcements' if selected.startswith('notice-') else
                   'results' if selected or selected_program or result_route else 'announcements')
    available = ([item.overview_id for item in notice_items] if section == 'announcements'
                 else [str(program.pk) for program in programs])
    if selected not in available:
        selected = available[0] if available else ''
    for program in programs:
        program.overview_selected = str(program.pk) == selected
    for item in notice_items:
        item.overview_selected = item.overview_id == selected
    context['notice_page'] = notice_page
    context['announcement_workspace'] = True
    context['announcement_section'] = section
    context['selected_id'] = selected
    return context
