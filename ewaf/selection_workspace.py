"""Read-only ranking workspace. All readiness and scores come from EWAF services."""
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.urls import reverse

from programs.catalog import capacity_context
from programs.models import Program
from . import operational_services as service
from .operational_forms import GenerateForm
from .operational_models import OperationalRun
from .program_cards import CONFIGURATIONS, SORTS, applicant_counts, configuration_summary

STATES = (('ready', 'Ready'), ('pending', 'Pending scoring'))
QUEUE_STATES = (('review', 'Ready for scoring checks'), ('pending', 'Pending scoring'))


def readiness(program, user):
    summary = configuration_summary(program)
    summary['weights_available'] = any(row['percent'] is not None for row in summary['rows'])
    program.ewaf_card = summary
    expected = None
    configured = summary['state'] == 'ready'
    reviews_complete = program.eligible_count > 0 and program.pending_count == 0
    if configured:
        try:
            expected = service.context(program.pk, user=user)
        except ValidationError:
            pass
    state = 'ready' if expected is not None else 'pending'
    checks = [
        {'label': 'Eligible pool reviewed', 'complete': reviews_complete},
        {'label': 'Assessment and cutoff checks', 'complete': expected is not None},
    ]
    completed = sum(check['complete'] for check in checks)
    return {'state': state, 'label': dict(STATES)[state], 'expected': expected,
            'checks': checks, 'completed': completed, 'percent': round(100 * completed / len(checks)),
            'can_generate': expected is not None and user.has_perm('ewaf.calculate_operational')}


def ranking_preview(program, user):
    run = OperationalRun.objects.filter(program=program).select_related('configuration').first()
    if not run:
        return None
    try:
        run.clean()
    except ValidationError:
        return {'invalid': True, 'run': run}
    active = False
    try:
        with service.fence(program.pk, user) as (current, locked, applications):
            service.current_result_run(locked, applications, current, run.pk)
        active = True
    except ValidationError:
        pass
    # Ranking order and exact ties are retained by the existing service.
    rows = service.ordered(run)[:3]
    names = {str(item.pk): item.member.full_name for item in
             program.applications.filter(pk__in=[row['application'] for row in rows]).select_related('member')}
    for row in rows:
        row['member_name'] = names.get(row['application'], 'Applicant')
        row['rank'] = row['comparison']['higher'] + 1
        row['display_score'] = row.get('score_display') or row['score_0_100']
    return {'run': run, 'active': active, 'rows': rows}


def workspace(request):
    query = request.GET.get('q', '').strip()[:200]
    state = request.GET.get('configuration', '')
    if state == 'ready':
        state = 'review'
    if state not in dict(QUEUE_STATES) and state not in dict(CONFIGURATIONS):
        state = ''
    sort = request.GET.get('sort', 'newest')
    sort = sort if sort in dict(SORTS) else 'newest'
    ordering = {'newest': ('-created_at', '-pk'), 'oldest': ('created_at', 'pk'),
                'az': ('name', 'pk'), 'za': ('-name', 'pk')}[sort]
    programs = list(applicant_counts(Program.objects.filter(ewaf_applicable=True)).order_by(*ordering))
    for program in programs:
        # Only cheap configuration and recorded review summaries belong in the
        # queue. Full pool capture/locking and saved-run validation are deferred
        # to the selected panel, never cached as authorization to generate.
        program.ewaf_card = configuration_summary(program)
        queue_state = ('review' if program.ewaf_card['state'] == 'ready'
                       and program.eligible_count > 0 and program.pending_count == 0 else 'pending')
        program.selection = {'state': queue_state, 'label': dict(QUEUE_STATES)[queue_state]}
        capacity_context(program, request.user)
    matches = [p for p in programs if
               (not query or query.casefold() in (p.name + ' ' + (p.public_code or '')).casefold()) and
               (not state or (p.selection['state'] == state if state in dict(QUEUE_STATES) else p.ewaf_card['state'] == state))]
    # The admin portfolio is loaded once so text/status filters do not repeat
    # expensive evidence validation or cause a navigation on each keystroke.
    page = Paginator(matches, max(20, len(matches))).get_page(1)
    matching_ids = {p.pk for p in matches}
    selected = request.GET.get('selected', '')
    if selected not in {str(p.pk) for p in page}:
        selected = str(page[0].pk) if page else ''
    for program in programs:
        program.selection['selected'] = str(program.pk) == selected
        program.selection['visible'] = program.pk in matching_ids
        program.selection['url'] = reverse('ewaf:operational_workspace', args=[program.pk])
        program.selection['panel_url'] = reverse('ewaf:selection_panel', args=[program.pk])
    return {'ewaf_selection_workspace': True, 'page_obj': page, 'program_rows': programs, 'selected_id': selected,
            'query': query, 'configuration_status': state, 'configuration_options': QUEUE_STATES,
            'sort': sort, 'sort_options': SORTS}


def panel(program, user):
    selection = readiness(program, user)
    selection.update(selected=True, url=reverse('ewaf:operational_workspace', args=[program.pk]),
                     preview=ranking_preview(program, user),
                     form=GenerateForm(auto_id='generate_' + str(program.pk) + '_%s',
                         initial={'expected': selection['expected'], 'request_key': uuid4()}))
    return {'program': program, 'selection': selection}
