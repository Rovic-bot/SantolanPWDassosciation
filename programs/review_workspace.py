"""Read-only program selection and aggregate application context."""
from collections import defaultdict
from typing import TypedDict

from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from .catalog import program_cards, STATUSES
from .models import Program, ProgramApplication
from .portfolio import card_presentation


class StatusCount(TypedDict):
    label: str
    count: int
    accent: str


class ReviewProgram(TypedDict):
    id: str
    name: str
    code: str
    category: str
    status: str
    status_label: str
    accent: str
    registration: str
    registration_state: str
    schedule: str
    applications: int
    capacity: str
    demand: int | None
    progress: int
    excess: int
    available: str
    readiness: str
    eligibility: str
    statuses: list[StatusCount]
    review_url: str
    detail_url: str


def date_range(start, end):
    def label(value):
        return date_format(timezone.localtime(value), 'M j, Y')
    if not start:
        return f'Ends {label(end)}' if end else 'Not scheduled'
    return f'{label(start)} - {label(end)}' if end and timezone.localtime(end).date() != timezone.localtime(start).date() else label(start)


def application_workspace_context(request):
    now = timezone.now()
    programs = Program.objects.all()
    closed = request.GET.get('status') == 'closed'
    context = program_cards(request, programs.filter(status='published', registration_closes_at__lte=now) if closed else programs)
    context['statuses'] = [*STATUSES, ('closed', 'Registration closed')]
    if closed:
        context['status'] = 'closed'
    rows = list(context['page_obj'])
    counts = defaultdict(dict)
    for item in ProgramApplication.objects.filter(program_id__in=[p.pk for p in rows]).order_by().values('program_id', 'status').annotate(total=Count('pk')):
        counts[item['program_id']][item['status']] = item['total']
    can_view_eligibility = request.user.has_perm('assistance.view_assistancecase')
    outcomes = defaultdict(dict)
    rate = None
    rate_detail = 'Eligibility access restricted'
    if can_view_eligibility:
        source = ProgramApplication.objects.all()
        totals = source.aggregate(eligible=Count('pk', filter=Q(assistance_case__eligibility_id='eligible')),
                                  ineligible=Count('pk', filter=Q(assistance_case__eligibility_id='ineligible')))
        decided = totals['eligible'] + totals['ineligible']
        rate = round(totals['eligible'] * 100 / decided) if decided else None
        rate_detail = 'Of recorded eligible / ineligible outcomes' if decided else 'No decided eligibility outcomes'
        for item in source.filter(program_id__in=[p.pk for p in rows]).order_by().values('program_id', 'assistance_case__eligibility_id').annotate(total=Count('pk')):
            outcomes[item['program_id']][item['assistance_case__eligibility_id']] = item['total']
    metrics = [
        {'value': programs.count(), 'suffix': '', 'label': 'Total programs', 'detail': 'Across all publication states', 'accent': 'blue'},
        {'value': ProgramApplication.objects.count(), 'suffix': '', 'label': 'Total applications', 'detail': 'Across all program records', 'accent': 'violet'},
        {'value': programs.accepting_applications(at=now).count(), 'suffix': '', 'label': 'Accepting applications', 'detail': 'Registration currently open', 'accent': 'green'},
        {'value': rate, 'suffix': '%' if rate is not None else '', 'label': 'Eligibility rate', 'detail': rate_detail, 'accent': 'orange'},
    ]
    records: list[ReviewProgram] = []
    for program in rows:
        presentation = card_presentation(program)
        if program.assistance_type == 'Healthcare & Medical Aid':
            presentation['accent'] = 'blue'
        statuses = counts[program.pk]
        pending = statuses.get('PENDING_PHOTO_VERIFICATION', 0)
        reviewing = statuses.get('PHOTO_VERIFIED', 0) + statuses.get('ELIGIBILITY_REVIEW', 0)
        breakdown = [
            {'label': 'New', 'count': pending, 'accent': 'cyan'},
            {'label': 'Under review', 'count': reviewing, 'accent': 'violet'},
            {'label': 'Eligible', 'count': statuses.get('ELIGIBLE', 0), 'accent': 'green'},
        ]
        mapped = {'PENDING_PHOTO_VERIFICATION', 'PHOTO_VERIFIED', 'ELIGIBILITY_REVIEW', 'ELIGIBLE'}
        for status, label in ProgramApplication.Status.choices:
            if status not in mapped and statuses.get(status):
                breakdown.append({'label': label, 'count': statuses[status], 'accent': 'orange' if status in ('NEEDS_INFORMATION', 'VERIFICATION_FAILED', 'INELIGIBLE') else 'muted'})
        eligibility = 'Eligibility access restricted'
        if can_view_eligibility:
            findings = outcomes[program.pk]
            eligibility = f"{findings.get('eligible', 0)} eligible / {findings.get('ineligible', 0)} ineligible recorded"
        available = 'Usage restricted'
        if program.can_view_capacity:
            available = f'{program.available_slots} unallocated' if program.available_slots is not None else 'Capacity not set'
        awaiting = pending + reviewing + statuses.get('NEEDS_INFORMATION', 0)
        readiness = 'No applications yet' if not program.applicant_count else (f'{awaiting} awaiting review' if awaiting else 'Recorded outcomes available')
        records.append({
            'id': str(program.pk), 'name': program.name, 'code': program.public_code or 'Code not assigned',
            'category': program.assistance_type, 'status': program.status, 'status_label': program.get_status_display(),
            'accent': presentation['accent'], 'registration': date_range(program.registration_opens_at, program.registration_closes_at),
            'registration_state': {'open': 'Registration open', 'ended': 'Registration closed', 'upcoming': 'Not yet open',
                                   'unavailable': 'Registration unavailable', 'cancelled': 'Cancelled'}.get(program.public_application_status, ''),
            'schedule': date_range(program.starts_at, program.ends_at), 'applications': program.applicant_count,
            'capacity': program.capacity_label,
            'demand': presentation['demand'], 'progress': presentation['progress'], 'excess': presentation['excess'],
            'available': available, 'readiness': readiness, 'eligibility': eligibility, 'statuses': breakdown,
            'review_url': reverse('programs:applications', args=[program.pk]),
            'detail_url': reverse('programs:manage_detail', args=[program.pk]),
        })
    selected = next((row for row in records if row['id'] == request.GET.get('selected')), records[0] if records else None)
    context.update(review_metrics=metrics, review_programs=records, selected_program=selected)
    return context
