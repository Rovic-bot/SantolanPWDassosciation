"""Read-only aggregates for the dashboard. No records or workflow services are run.

See docs/dashboard-overview-2026-10-29/definitions.md for scope and permissions.
"""
from datetime import date, datetime, time, timedelta
import logging

from django.db import DatabaseError
from django.db.models import Case, Count, F, IntegerField, Q, Value, When
from django.db.models.functions import ExtractYear, Floor
from django.utils import timezone

from assistance.models import AssistanceRelease
from assistance.referral_models import ReferralTicket
from assistance.referral_services import enabled as desk_enabled
from assistance.services import VIEW_PERMISSIONS
from core.permissions import require_workspace_permissions
from events.models import Event
from members.models import Member
from programs.models import Program, ProgramApplication
from reports.services import PERMISSIONS

logger = logging.getLogger(__name__)


def number(value):
    return f'{value:,}'


def result(**values):
    return {'state': 'ready', **values}


def scoped(user, permissions, loader):
    if not user.has_perms(permissions):
        return {'state': 'restricted', 'message': 'Not permitted',
                'detail': 'Your account does not have access to these metrics.'}
    try:
        return loader()
    except DatabaseError as error:
        # A missing analytics source is not a zero; do not expose SQL or record data.
        missing = error.args and error.args[0] in (1054, 1146)
        logger.warning('Dashboard source %s %s', loader.__name__, 'unavailable' if missing else 'failed')
        return {'state': 'unavailable' if missing else 'failed',
                'message': 'Unavailable' if missing else 'Could not load',
                'detail': 'This analytics source is unavailable.' if missing else 'Refresh the page to try again.'}


def chart(key, title, scope, rows, *, monthly=False, note=''):
    """Only aggregates and recorded classification labels reach the template."""
    maximum = max((count for _, count in rows), default=0)
    # Whole-count scale with four equal intervals, beginning at zero.
    step = max(1, (maximum + 3) // 4)
    ceiling = step * 4
    return {'id': key, 'title': title, 'scope': scope, 'note': note,
            'monthly': monthly and len(rows) <= 12,
            'total': sum(count for _, count in rows),
            'ticks': [number(step * index) for index in range(5)],
            'rows': [{'label': label, 'count': count, 'display': number(count),
                      'size': f'{count / ceiling * 100:.4f}'} for label, count in rows]}


def month_ranges(values, *, date_only=False):
    current = values['start'].replace(day=1)
    while current <= values['end']:
        following = date(current.year + (current.month == 12), current.month % 12 + 1, 1)
        start, end = max(current, values['start']), min(following, values['end'] + timedelta(days=1))
        if not date_only:
            zone = timezone.get_default_timezone()
            start = timezone.make_aware(datetime.combine(start, time.min), zone)
            end = timezone.make_aware(datetime.combine(end, time.min), zone)
        yield current.strftime('%b %Y'), start, end
        current = following


def activity(source, field, values, *, date_only=False, recipient=None):
    """One bounded aggregate; Python timezone bounds avoid MySQL TZ table dependence."""
    lower = values['start'] if date_only else values['lower']
    upper = values['end'] + timedelta(days=1) if date_only else values['upper']
    interval = Q(**{field + '__gte': lower, field + '__lt': upper})
    missing = Q(**{field + '__isnull': True})
    months = list(month_ranges(values, date_only=date_only))
    expressions = {'total': Count('pk', filter=interval, distinct=True),
                   'undated': Count('pk', filter=missing, distinct=True)}
    for index, (_, start, end) in enumerate(months):
        expressions[f'm{index}'] = Count('pk', distinct=True, filter=Q(**{
            field + '__gte': start, field + '__lt': end}))
    if recipient:
        expressions['recipients'] = Count(recipient, distinct=True, filter=interval)
    totals = source.filter(interval | missing).aggregate(**expressions)
    return totals, [(label, totals[f'm{index}']) for index, (label, _, _) in enumerate(months)]


def state_counts(source, field, choices, *, missing_label='Not recorded'):
    counts = {row[field]: row['count'] for row in source.order_by().values(field).annotate(count=Count('pk', distinct=True))}
    rows = [(label, counts.pop(code, 0)) for code, label in choices]
    if None in counts or '' in counts:
        rows.append((missing_label, counts.pop(None, 0) + counts.pop('', 0)))
    if counts:
        rows.append(('Unrecognized state', sum(counts.values())))
    # Retain all observed states, including unknown values without disclosing raw text.
    return [(label, count) for label, count in rows if count]


def cohort(source, field, values):
    return source.filter(**{field + '__gte': values['lower'], field + '__lt': values['upper']})


def program_scope(source, values, field='program'):
    program = values.get('program')
    return source.filter(**{field: program.pk}) if program is not None else source


def membership(values, scope, now=None):
    current = Member.objects.filter(archived_at__isnull=True)
    total = current.count()
    # Match PersonalRecord.disability_ids: M2M is authoritative, legacy FK is fallback.
    classified = current.filter(disability_types__isnull=False).order_by().values(
        'disability_types__id', 'disability_types__name').annotate(count=Count('pk', distinct=True))
    legacy = current.filter(disability_types__isnull=True).order_by().values(
        'disability_type_id', 'disability_type__name').annotate(count=Count('pk', distinct=True))
    counts, names, missing = {}, {}, 0
    for item in classified:
        key = item['disability_types__id']
        counts[key], names[key] = item['count'], item['disability_types__name']
    for item in legacy:
        key = item['disability_type_id']
        if key is None:
            missing += item['count']
        else:
            counts[key] = counts.get(key, 0) + item['count']
            names[key] = item['disability_type__name']
    rows = [(names[key], counts[key]) for key in sorted(counts, key=lambda key: (-counts[key], names[key]))]
    if missing:
        rows.append(('Classification not recorded', missing))
    totals, months = activity(Member.objects.all(), 'joined_at', values)
    now = now or timezone.now()
    year_start = timezone.localtime(now).replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    new_year = Member.objects.filter(joined_at__gte=year_start, joined_at__lte=now).count()
    return result(total=total, growth=chart('membership-growth', 'Members joined', scope, months, monthly=True),
        new=totals['total'], new_year=new_year, undated=totals['undated'],
        disability=chart('disability', 'Members by recorded classification', 'Current official members', rows),
        missing=missing)


def releases(values, scope):
    source = program_scope(AssistanceRelease.objects.successful(), values, 'application__program')
    totals, rows = activity(source, 'released_on', values,
                            date_only=True, recipient='application__member_id')
    mix = source.filter(released_on__gte=values['start'], released_on__lte=values['end']).order_by(
        'assistance_type').values('assistance_type').annotate(count=Count('pk', distinct=True))
    return result(**totals, mix=[(row['assistance_type'] or 'Type not recorded', row['count']) for row in mix],
                  chart=chart('releases', 'Confirmed releases by month', scope, rows, monthly=True))


def applications(values, scope):
    source = program_scope(ProgramApplication.objects.all(), values)
    totals, rows = activity(source, 'submitted_at', values)
    completion = list(cohort(source, 'submitted_at', values).order_by('program__name', 'program_id').values(
        'program__name', 'program_id').annotate(total=Count('pk', distinct=True),
            completed=Count('pk', filter=Q(status=ProgramApplication.Status.COMPLETED), distinct=True),
            pending=Count('pk', filter=Q(status=ProgramApplication.Status.PENDING_PHOTO_VERIFICATION), distinct=True)))
    return result(**totals, completion=completion,
        completed=sum(row['completed'] for row in completion), pending=sum(row['pending'] for row in completion),
        chart=chart('applications', 'Submitted applications by month', scope, rows, monthly=True))


def eligibility(values, scope):
    source = cohort(program_scope(ProgramApplication.objects.all(), values), 'submitted_at', values)
    choices = [
        ('pending', 'Pending'), ('eligible', 'Eligible'), ('review', 'Needs Information'),
        ('ineligible', 'Ineligible'), (None, 'No review recorded'), ('unknown', 'Unrecognized outcome')]
    grouped = source.order_by('program__name', 'program_id').values(
        'program_id', 'program__name', 'assistance_case__eligibility_id').annotate(count=Count('pk', distinct=True))
    rows = {}
    for row in grouped:
        program = rows.setdefault(row['program_id'], {'name': row['program__name'], 'counts': [0] * len(choices)})
        code = row['assistance_case__eligibility_id']
        index = next((i for i, (value, _) in enumerate(choices) if value == code), len(choices) - 1)
        program['counts'][index] += row['count']
    return result(total=sum(sum(row['counts']) for row in rows.values()),
                  labels=[label for _, label in choices], rows=list(rows.values()))


def programs(now, values):
    rows = state_counts(program_scope(Program.objects.all(), values, 'pk'), 'status', Program.Status.choices)
    return result(total=sum(count for _, count in rows), active=program_scope(Program.objects.accepting_applications(at=now), values, 'pk').count(),
        chart=chart('programs', 'Programs by publication state', 'Current program records', rows))


def events(values, scope):
    # Use local-day UTC boundaries instead of requiring MySQL named-timezone tables.
    # One occurrence contributes to exactly one (local month, ISO weekday) bucket.
    months = list(month_ranges(values))
    indexes = {(start.year, start.month): i for i, (_, start, _) in enumerate(months)}
    matrix = [[0] * 7 for _ in months]
    day, cases = values['start'], []
    zone = timezone.get_default_timezone()
    while day <= values['end']:
        lower = timezone.make_aware(datetime.combine(day, time.min), zone)
        upper = timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min), zone)
        bucket = indexes[(day.year, day.month)] * 7 + day.weekday()
        cases.append(When(starts_at__gte=lower, starts_at__lt=upper, then=Value(bucket)))
        day += timedelta(days=1)
    source = cohort(Event.objects.all(), 'starts_at', values)
    for row in source.order_by().annotate(bucket=Case(*cases, output_field=IntegerField())).values('bucket').annotate(count=Count('pk', distinct=True)):
        month, weekday = divmod(row['bucket'], 7)
        matrix[month][weekday] = row['count']
    states = state_counts(cohort(Event.objects.all(), 'starts_at', values), 'status', Event.Status.choices)
    return result(total=sum(sum(row) for row in matrix), months=[label for label, _, _ in months], matrix=matrix,
                  undated=Event.objects.filter(starts_at__isnull=True).count(),
                  states=', '.join(f'{number(count)} {label.lower()}' for label, count in states))


def ages(now):
    as_of = timezone.localdate(now, timezone=timezone.get_default_timezone())
    source = Member.objects.filter(archived_at__isnull=True)
    exclusions = source.aggregate(missing=Count('pk', filter=Q(birthdate__isnull=True)),
                                  invalid=Count('pk', filter=Q(birthdate__gt=as_of)))
    # Completed birthdays, using portable date extraction on MySQL/PostgreSQL.
    # A February 29 birthday advances on March 1 in non-leap years, as before.
    birthday_pending = Q(birthdate__month__gt=as_of.month) | Q(
        birthdate__month=as_of.month, birthdate__day__gt=as_of.day)
    age = Value(as_of.year) - ExtractYear('birthdate') - Case(
        When(birthday_pending, then=Value(1)), default=Value(0), output_field=IntegerField())
    groups = source.filter(birthdate__lte=as_of).order_by().annotate(
        band=Floor(age / Value(10.0))).values('band').annotate(count=Count('pk', distinct=True))
    counts = {int(row['band']): row['count'] for row in groups}
    rows = [(f'{i * 10}–{i * 10 + 9}', counts.get(i, 0)) for i in range(max(counts, default=-1) + 1)]
    return result(as_of=as_of, rows=rows, total=sum(counts.values()), **exclusions)


def capacity(values, now):
    closed = cohort(program_scope(Program.objects.all(), values, 'pk'), 'registration_closes_at', values).filter(registration_closes_at__lte=now)
    excluded = closed.filter(slots__isnull=True).count()
    # Entire original submission window for this closed-program cohort, not just
    # submissions inside the dashboard dates; configured slots are not remaining slots.
    records = closed.filter(slots__isnull=False).annotate(submissions=Count('applications', distinct=True,
        filter=Q(applications__submitted_at__gte=F('registration_opens_at'),
                 applications__submitted_at__lt=F('registration_closes_at')))).order_by('registration_closes_at', 'pk')
    rows = list(records.values('name', 'slots', 'submissions', 'registration_opens_at', 'registration_closes_at'))
    return result(rows=rows, total=len(rows), excluded=excluded)


def desk(values, scope):
    if not desk_enabled():
        return {'state': 'unavailable', 'message': 'Unavailable', 'detail': 'Community Assistance Desk is not enabled.'}
    source = cohort(ReferralTicket.objects.all(), 'received_at', values)
    rows = state_counts(source, 'status', ReferralTicket.Status.choices)
    return result(total=sum(count for _, count in rows), chart=chart('desk', 'Current request states', scope, rows),
                  undated=ReferralTicket.objects.filter(received_at__isnull=True).count())


def overview(user, values, *, now=None):
    require_workspace_permissions(user)
    if values.get('program') is not None:
        require_workspace_permissions(user, 'programs.view_program')
    now = now or timezone.now()
    scope = f"{values['start']:%d %b %Y} – {values['end']:%d %b %Y}"
    members = scoped(user, PERMISSIONS['members'], lambda: membership(values, scope, now))
    delivered = scoped(user, PERMISSIONS['assistance'], lambda: releases(values, scope))
    submitted = scoped(user, PERMISSIONS['applications'], lambda: applications(values, scope))
    findings = scoped(user, VIEW_PERMISSIONS, lambda: eligibility(values, scope))
    program_data = scoped(user, PERMISSIONS['programs'], lambda: programs(now, values))
    event_data = scoped(user, ('events.view_event',), lambda: events(values, scope))
    desk_data = scoped(user, ('assistance.view_referralticket',), lambda: desk(values, scope))
    age_data = scoped(user, PERMISSIONS['members'], lambda: ages(now))
    capacity_data = scoped(user, PERMISSIONS['applications'], lambda: capacity(values, now))
    metrics = []
    for label, data, key, caption in [
        ('Official members', members, 'total', 'Current · active and inactive; archived excluded'),
        ('New members this year', members, 'new_year', f'Joined in {timezone.localtime(now).year} through today · includes since archived'),
        ('Confirmed assistance releases', delivered, 'total', 'Actually delivered in the selected period'),
        ('Active programs', program_data, 'active', 'Current · accepting applications under existing rules'),
        ('Scheduled events', event_data, 'total', 'Starts in the selected period · all recorded states'),
        ('Community Assistance Desk requests', desk_data, 'total', 'Submitted in the selected period'),
        ('Pending photo verification', submitted, 'pending', 'Applications awaiting photo review · submitted in period'),
        ('Completed applications', submitted, 'completed', 'Current Completed status · submitted in period'),
    ]:
        metrics.append({'label': label, 'value': number(data[key]) if data['state'] == 'ready' else data['message'],
                        'caption': caption, 'state': data['state']})
    data = {'metrics': metrics, 'members': members, 'releases': delivered, 'applications': submitted,
            'eligibility': findings, 'programs': program_data, 'events': event_data, 'desk': desk_data,
            'ages': age_data, 'capacity': capacity_data,
            'scope': scope, 'program_label': values['program'].name if values.get('program') else 'All programs',
            'zone': str(timezone.get_default_timezone()), 'updated': now}
    from .visualizations import inventory
    data['visualizations'] = inventory(data)
    return data
