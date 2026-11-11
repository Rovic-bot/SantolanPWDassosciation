"""Read-only presentation for the private program portfolio."""
from datetime import timedelta
from typing import TypedDict
from zlib import crc32

from django.db.models import Count, Q, Sum
from django.urls import reverse
from django.utils import timezone

from .catalog import program_cards
from .models import Program, ProgramApplication


class CardPresentation(TypedDict):
    accent: str
    demand: int | None
    progress: int
    excess: int


def card_presentation(program: Program) -> CardPresentation:
    colors = {'Healthcare': 'blue', 'Medical': 'blue', 'Assistive Devices': 'violet',
              'Livelihood': 'orange', 'Food & Nutrition': 'magenta', 'Community': 'green',
              'Financial': 'cyan', 'Education': 'blue'}
    accents = ('blue', 'violet', 'orange', 'magenta', 'green', 'cyan')
    accent = colors.get(program.assistance_type,
                        accents[crc32(program.assistance_type.encode('utf-8')) % len(accents)])
    demand = round(program.applicant_count * 100 / program.slot_limit) if program.slot_limit else None
    return {'accent': accent, 'demand': demand, 'progress': min(100, demand or 0),
            'excess': max(0, program.applicant_count - program.slot_limit) if program.slot_limit else 0}


def portfolio_context(request) -> dict:
    now = timezone.now()
    programs = Program.objects.all()
    closed = request.GET.get('status') == 'closed'
    context = program_cards(request, programs.filter(status='published', registration_closes_at__lte=now)
                            if closed else programs, include_new=True)
    context['statuses'] = [*context['statuses'], ('closed', 'Registration closed')]
    if closed:
        context['status'] = 'closed'
    for program in context['page_obj']:
        program.portfolio = card_presentation(program)
    totals = programs.aggregate(total=Count('pk'), categories=Count('assistance_type', distinct=True),
        published=Count('pk', filter=Q(status='published')), draft=Count('pk', filter=Q(status='draft')),
        registration_closed=Count('pk', filter=Q(status='published', registration_closes_at__lte=now)),
        cancelled=Count('pk', filter=Q(status='cancelled')), archived=Count('pk', filter=Q(status='archived')),
        upcoming=Count('pk', filter=Q(status='published', published_at__lte=now,
                                     starts_at__gte=now, starts_at__lt=now + timedelta(days=30))),
        places=Sum('slots'),
        unspecified=Count('pk', filter=Q(slots__isnull=True)))
    applicants = ProgramApplication.objects.count()
    capacity_applicants = ProgramApplication.objects.filter(program__ewaf_applicable=True, program__slots__isnull=False).count()
    accepting = programs.accepting_applications(at=now)
    metrics = [
        {'value': totals['total'], 'label': 'Total programs', 'accent': 'cyan', 'detail': f'Across {totals["categories"]} categories'},
        {'value': totals['published'], 'label': 'Published programs', 'accent': 'green', 'detail': f'{accepting.count()} accepting applications'},
        {'value': applicants, 'label': 'Program applications', 'accent': 'violet', 'detail': 'Across all programs'},
        {'value': totals['upcoming'], 'label': 'Upcoming programs', 'accent': 'orange', 'detail': 'Starting within 30 days'},
    ]
    deadline = accepting.order_by('registration_closes_at', 'pk').first()
    deadline_label = ''
    if deadline:
        days = (timezone.localtime(deadline.registration_closes_at).date() - timezone.localdate(now)).days
        deadline_label = 'Closes today' if days == 0 else f'Closes in {days} day{"s" if days != 1 else ""}'
    attention = programs.filter(status='draft').order_by('-updated_at', 'pk').first()
    places = totals['places'] or 0
    demand = round(capacity_applicants * 100 / places) if places else None
    context.update({
        'portfolio_metrics': metrics, 'portfolio_totals': totals,
        'portfolio_capacity': {'applications': capacity_applicants, 'places': places,
            'percent': demand, 'progress': min(100, demand or 0),
            'unspecified': totals['unspecified']},
        'portfolio_deadline': deadline, 'portfolio_deadline_label': deadline_label, 'portfolio_attention': attention,
        'portfolio_statuses': [{'label': label, 'count': totals[value], 'value': value,
            'accent': {'published': 'green', 'draft': 'orange', 'cancelled': 'magenta', 'archived': 'muted'}[value]}
            for value, label in Program.Status.choices if totals[value] or value in ('published', 'draft')],
        'can_review_applications': request.user.has_perm('programs.view_programapplication'),
        'application_review_url': (reverse('programs:applications', args=[deadline.pk]) if deadline else reverse('core:application_programs')),
    })
    return context
