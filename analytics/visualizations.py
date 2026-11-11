"""Presentation projection: one source of values for each chart, legend and table."""
from itertools import accumulate
from django.utils import timezone
from .services import number

STATUS_TONES = {'draft': 4, 'published': 0, 'cancelled': 5, 'archived': 2,
                'received': 4, 'in review': 1, 'needs information': 3, 'referred': 2,
                'closed': 0, 'pending': 4, 'eligible': 0, 'ineligible': 5,
                'no review recorded': 1, 'unrecognized outcome': 2}


def status_tone(label):
    return STATUS_TONES.get(label.lower(), 4)


def visual(key, title, kind, source, scope, summary='', note='', *, labels=None, series=None,
           columns=None, rows=None, total=0, wide=False, payload=None):
    result = {'id': key, 'title': title, 'kind': kind, 'scope': scope, 'summary': summary,
              'note': note, 'wide': wide, 'state': source['state'],
              'message': source.get('message', ''), 'detail': source.get('detail', '')}
    if source['state'] != 'ready':
        return result
    result.update(columns=columns or ['Category / month', 'Count'], rows=rows or [], total=total,
                  payload={'kind': kind, 'labels': labels or [], 'series': series or [], 'total': total, **(payload or {})})
    return result


def simple(key, title, kind, source, scope, summary, note, pairs, *, cumulative=False):
    if source.get('undated'):
        note += f" {number(source['undated'])} undated records are excluded from period attribution."
    pairs = list(pairs)
    counts = [n for _, n in pairs]
    if cumulative:
        counts = list(accumulate(counts))
    total = counts[-1] if cumulative and counts else sum(counts)
    rows = [[label, number(count)] for (label, _), count in zip(pairs, counts)]
    if kind in ('pie', 'donut', 'rings'):
        # Largest remainder at 0.1% precision makes the displayed partition sum to 100%.
        units = [count * 1000 // total for count in counts] if total else [0] * len(counts)
        order = sorted(range(len(counts)), key=lambda i: (-(counts[i] * 1000 % total), i)) if total else []
        for i in order[:1000 - sum(units) if total else 0]:
            units[i] += 1
        rows = [row + [f'{unit / 10:.1f}%'] for row, unit in zip(rows, units)]
    item = visual(key, title, kind, source, scope, summary, note,
        labels=[label for label, _ in pairs], series=[{'name': 'Count', 'values': counts}],
        columns=['Status', 'Count', 'Percent'] if kind in ('pie', 'donut', 'rings') else ['Month' if kind in ('line', 'area', 'column') else 'Category', 'Count'],
        rows=rows, total=total)
    if source['state'] == 'ready' and kind in ('pie', 'donut', 'rings'):
        item['payload']['colors'] = [status_tone(label) for label, _ in pairs]
        item['legend'] = [{'label': row[0], 'value': f'{row[1]} ({row[2]})', 'index': i + 1,
                           'tone': status_tone(row[0]) + 1} for i, row in enumerate(rows)]
    return item


def pairs(source, key='chart'):
    return [(row['label'], row['count']) for row in source.get(key, {}).get('rows', [])]


def inventory(data):
    members, releases, apps = data['members'], data['releases'], data['applications']
    programs, desk, eligibility = data['programs'], data['desk'], data['eligibility']
    age, capacity, events = data['ages'], data['capacity'], data['events']
    scope = f"{data['scope']} · {data['zone']}"
    current = f"Current as of {timezone.localtime(data['updated']):%d %b %Y} · {data['zone']}"
    # Keep the reference's four-card overview; secondary metrics remain in a disclosure.
    metric_labels = {
        'Official members': ('Registered members', 'Current registry'),
        'Confirmed assistance releases': ('Assistance releases', 'Confirmed delivery'),
        'Active programs': ('Active programs', 'Accepting applications'),
        'Scheduled events': ('Scheduled events', 'Selected period'),
        'New members this year': ('New members this year', 'Year to date'),
        'Community Assistance Desk requests': ('Assistance requests', 'Selected period'),
        'Pending photo verification': ('Pending photo review', 'Submitted in period'),
        'Completed applications': ('Completed applications', 'Submitted in period'),
    }
    primary_labels = list(metric_labels)[:4]
    metric_cards = [{**metric, 'short_label': metric_labels[metric['label']][0],
                     'short_caption': metric_labels[metric['label']][1]} for metric in data['metrics']]
    data['primary_metrics'] = [metric for label in primary_labels for metric in metric_cards if metric['label'] == label]
    data['additional_metrics'] = [metric for metric in metric_cards if metric['label'] not in primary_labels]
    charts = [
        simple('membership-area', 'Cumulative new memberships', 'area', members, scope,
            f"{number(members.get('new', 0))} new memberships recorded in this period.",
            'Running total of recorded joining dates in this period, including members since archived. Not current active membership.',
            pairs(members, 'growth'), cumulative=True),
        simple('disability-bar', 'Members by disability type', 'member-donut', members, current,
            f"{number(members.get('total', 0))} current official members; archived records excluded.",
            'Ring segments show the relative counts of recorded classifications, including missing classification as a separate category. Legend percentages use current members; members with multiple classifications may appear in more than one category, so these percentages can total more than 100%.',
            pairs(members, 'disability')),
        simple('release-column', 'Monthly assistance releases', 'column', releases, scope,
            f"{number(releases.get('total', 0))} confirmed releases to {number(releases.get('recipients', 0))} distinct recipients.",
            'By actual delivery month. Voided releases excluded; applications and selections are not delivery.', pairs(releases)),
        simple('application-line', 'Program applications over time', 'line', apps, scope,
            f"{number(apps.get('total', 0))} applications submitted; monthly counts.",
            'Distinct program applications by submission month. Membership registrations and Desk requests are excluded.', pairs(apps)),
        simple('program-pie', 'Programs by current status', 'rings', programs, current,
            f"{number(programs.get('total', 0))} programs; one existing stored status per program.",
            'Draft, Published, Cancelled and Archived are the existing stored states. Published does not mean accepting applications; no completion state is inferred.', pairs(programs)),
        simple('desk-donut', 'Community Assistance Desk status', 'donut', desk, scope,
            f"{number(desk.get('total', 0))} submitted tickets; one current status per ticket.",
            'A reply is not automatically resolution. Closed or referred requests do not confirm assistance delivery.', pairs(desk)),
    ]
    if members['state'] == 'ready':
        # Category shares use the member denominator; classifications can overlap.
        charts[1]['payload']['denominator'] = members['total']
        charts[1]['columns'] = ['Disability type', 'Members', 'Share of members']
        charts[1]['rows'] = [[label, number(count), f"{count / members['total'] * 100 if members['total'] else 0:.1f}%"]
                             for label, count in pairs(members, 'disability')]
    if desk['state'] == 'ready':
        closed = next((count for label, count in pairs(desk) if label == 'Closed'), 0)
        charts[5]['payload']['closed'] = closed
    charts.append(simple('release-mix', 'Service release mix', 'proportional', releases, scope,
        f"{number(releases.get('total', 0))} confirmed releases by recorded assistance type.",
        'Share of non-voided releases by actual delivery date. Counts represent releases, not cash value.', releases.get('mix', [])))
    completed = apps.get('completion', [])
    charts.append(visual('program-completion', 'Application completion by program', 'progress', apps, scope,
        f"{number(apps.get('completed', 0))} completed of {number(apps.get('total', 0))} submitted applications.",
        'Current Completed application status within the submission cohort. This is not a program closure or a delivery rate.',
        labels=[row['program__name'] for row in completed],
        series=[{'name': 'Completed applications', 'values': [row['completed'] for row in completed]}],
        columns=['Program', 'Completed', 'Submitted', 'Completion share'],
        rows=[[row['program__name'], number(row['completed']), number(row['total']),
               f"{row['completed'] / row['total'] * 100:.1f}%"] for row in completed],
        total=apps.get('total', 0), payload={'denominators': [row['total'] for row in completed]}))
    rows = eligibility.get('rows', [])
    labels = eligibility.get('labels', [])
    chart = visual('eligibility-stack', 'Eligibility outcomes by program', 'stacked', eligibility, scope,
        f"{number(eligibility.get('total', 0))} applications in the selected submission cohort, across {number(len(rows))} programs.",
        'Current recorded eligibility findings, including pending and unreviewed cases. Each application contributes once; selection and delivery are not stacked.',
        labels=[f"{i + 1}. {row['name']}" for i, row in enumerate(rows)],
        series=[{'name': label, 'tone': status_tone(label), 'values': [row['counts'][i] for row in rows]} for i, label in enumerate(labels)],
        columns=['Program', *labels, 'Total'],
        rows=[[f"{i + 1}. {row['name']}", *[number(n) for n in row['counts']], number(sum(row['counts']))] for i, row in enumerate(rows)],
        total=eligibility.get('total', 0), wide=True)
    chart['legend'] = [{'label': label, 'value': '', 'index': i + 1, 'tone': status_tone(label) + 1} for i, label in enumerate(labels)] if eligibility['state'] == 'ready' else []
    charts.append(chart)
    rows = capacity.get('rows', [])
    charts.append(visual('capacity-scatter', 'Applications versus recorded slots', 'scatter', capacity, scope,
        f"{number(len(rows))} programs closed in this period; {number(capacity.get('excluded', 0))} excluded for unknown capacity.",
        'One dot per program closed by the refresh time. X = configured slots, not remaining slots. Y = submissions within its full application window [open, close). A dashed linear trend is descriptive only; it is omitted when fewer than two distinct slot counts exist.',
        columns=['Dot / program', 'Recorded slots', 'Applications in window', 'Window opens', 'Window closes'],
        rows=[[f"{i + 1}. {row['name']}", number(row['slots']), number(row['submissions']),
               timezone.localtime(row['registration_opens_at']).strftime('%d %b %Y, %H:%M'),
               timezone.localtime(row['registration_closes_at']).strftime('%d %b %Y, %H:%M')] for i, row in enumerate(rows)],
        total=len(rows), payload={'points': [{'label': str(i + 1), 'x': row['slots'], 'y': row['submissions']} for i, row in enumerate(rows)]}))
    charts.append(simple('age-histogram', 'Member age distribution', 'histogram', age, current,
        f"{number(age.get('total', 0))} members with usable birth dates. Missing: {number(age.get('missing', 0))}; invalid future dates: {number(age.get('invalid', 0))}.",
        'Completed years as of the displayed current date, in equal-width 10-year intervals. Descriptive only; not an eligibility or scoring rule. No birth dates or individual ages are sent to the chart.', age.get('rows', [])))
    matrix = events.get('matrix', [])
    highest = max((n for row in matrix for n in row), default=0)
    chart = visual('event-heatmap', 'Scheduled events by month and weekday', 'heatmap', events, scope,
        f"{number(events.get('total', 0))} scheduled occurrences" + (f" ({events['states']})." if events.get('states') else '.'),
        'One occurrence at its local start date. All recorded event states included. Reference observances, RSVP and attendance are excluded; scheduling does not establish completion.',
        columns=['Month', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'],
        rows=[[label, *[number(n) for n in row]] for label, row in zip(events.get('months', []), matrix)],
        total=events.get('total', 0), wide=True)
    chart['heat_rows'] = [{'label': label, 'cells': [{'count': number(n), 'level': 0 if not n else min(4, 1 + (n * 3 // max(highest, 1)))} for n in row]} for label, row in zip(events.get('months', []), matrix)]
    chart['maximum'] = highest
    chart['heat_scale'] = [{'level': 0, 'label': '0'}]
    if highest:
        edges = [(1, (highest + 2) // 3 - 1), (max(1, (highest + 2) // 3), (2 * highest + 2) // 3 - 1),
                 (max(1, (2 * highest + 2) // 3), highest - 1), (highest, highest)]
        chart['heat_scale'] += [{'level': i + 1, 'label': str(low) if low == high else f'{low}–{high}'}
                                for i, (low, high) in enumerate(edges) if low <= high]
    charts.append(chart)
    order = ['membership-area', 'disability-bar', 'release-column', 'program-completion',
             'application-line', 'program-pie', 'capacity-scatter', 'age-histogram',
             'eligibility-stack', 'desk-donut', 'release-mix', 'event-heatmap']
    charts.sort(key=lambda item: order.index(item['id']))
    completion_share = f"{apps.get('completed', 0) / apps['total'] * 100:.0f}%" if apps.get('total') else '0%'
    headlines = {
        'membership-area': ('Membership growth', 'New memberships', f"+{number(members.get('new', 0))}"),
        'disability-bar': ('Members by support need', 'Current registry', number(members.get('total', 0))),
        'release-column': ('Monthly assistance', 'Confirmed releases', number(releases.get('total', 0))),
        'program-completion': ('Application completion', 'By program', completion_share),
        'application-line': ('Applications over time', 'Monthly received', number(apps.get('total', 0))),
        'program-pie': ('Programs by status', 'Current portfolio', number(programs.get('total', 0))),
        'capacity-scatter': ('Applications versus slots', 'Closed programs', f"{number(capacity.get('total', 0))} programs"),
        'age-histogram': ('Member age distribution', 'Current members', number(age.get('total', 0))),
        'eligibility-stack': ('Eligibility outcomes by program', 'Recorded findings', f"{number(eligibility.get('total', 0))} applications"),
        'desk-donut': ('Community assistance desk', 'Request status', f"{number(desk.get('total', 0))} requests"),
        'release-mix': ('Service release mix', 'Selected period', number(releases.get('total', 0))),
        'event-heatmap': ('Scheduled events by month and weekday', 'Community calendar', f"{number(events.get('total', 0))} events"),
    }
    for item in charts:
        item['display_title'], item['eyebrow'], headline = headlines[item['id']]
        if item['state'] == 'ready':
            item['headline'] = headline
        if item['id'] in ('release-column', 'program-completion', 'application-line', 'program-pie',
                          'capacity-scatter', 'eligibility-stack', 'release-mix'):
            item['scope'] += f" · {data.get('program_label', 'All programs')}"
        if item['state'] != 'ready':
            # Restricted/error cards never carry a fabricated zero summary or payload.
            item['summary'] = ''
    return charts
