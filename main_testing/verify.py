"""Independent numerical replay, actual exports, permission and navigation checks."""
import csv
from decimal import Decimal, localcontext
from fractions import Fraction
from io import BytesIO, StringIO
import json
from pathlib import Path
from time import perf_counter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from openpyxl import load_workbook
from .seed import require_environment


def verify():
    require_environment()
    from ewaf.operational_models import OperationalRun, OperationalConfiguration
    from ewaf.operational_services import ordered
    from members.models import Member
    from programs.models import Program, ProgramApplication
    from assistance.models import AssistanceRelease, AssistanceCase
    from announcements.models import Announcement
    from reports.services import report_data, report_row
    from core.demo_seed import counts
    codes = ('SI', 'ES', 'PA', 'ND')
    out = Path(settings.MEDIA_ROOT).parent / 'verification'
    out.mkdir(exist_ok=True)
    evidence = {'database': connection.settings_dict['NAME'], 'counts': counts(), 'configurations': 0,
                'scores': 0, 'exports': {}, 'pages': {}, 'permissions': {}}
    from django.db import DatabaseError
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM santolan_pwd.auth_user')
    except DatabaseError:
        evidence['database_account_cannot_read_port8001'] = True
    else:
        raise AssertionError('Testing account can access the preserved database')
    evidence['counts'].update(assistance_records=AssistanceRelease.objects.count(),
        eligible=AssistanceCase.objects.filter(eligibility_id='eligible').count(),
        ineligible=AssistanceCase.objects.filter(eligibility_id='ineligible').count())
    for config in OperationalConfiguration.objects.all():
        # Rational reconstruction independent of the application's AHP implementation.
        matrix = {a: {b: Fraction(1) for b in codes} for a in codes}
        for pair, value in config.judgments.items():
            a, b = pair.split(':')
            matrix[a][b] = Fraction(value)
            matrix[b][a] = 1 / matrix[a][b]
        weights = {a: sum(matrix[a][b] / sum(matrix[c][b] for c in codes) for b in codes) / 4 for a in codes}
        lam = sum(sum(matrix[a][b] * weights[b] for b in codes) / weights[a] for a in codes) / 4
        cr = ((lam - 4) / 3) / Fraction(9, 10)
        assert 0 <= cr < Fraction(1, 10)
        with localcontext() as ctx:
            ctx.prec = 80
            for code in codes:
                expected = Decimal(weights[code].numerator) / weights[code].denominator
                assert abs(expected - Decimal(config.validation['weights'][code])) < Decimal('1e-45')
        evidence['configurations'] += 1
    for run in OperationalRun.objects.select_related('configuration'):
        scores = []
        for row in ordered(run):
            inputs = run.snapshot['eligible'][row['application']]['inputs']
            expected_score = Decimal(0)
            with localcontext() as ctx:
                ctx.prec = 80
                for trace in row['traces']:
                    code = trace['criterion']
                    rule = run.configuration.policy['criteria'][code]
                    raw = inputs[code]['value']
                    encoded = Decimal(rule['encoding'][raw] if rule.get('encoding') else str(raw))
                    lower, upper = Decimal(rule['bounds']['lower']), Decimal(rule['bounds']['upper'])
                    normalized = (upper - encoded if rule['direction'] == 'inverse' else encoded - lower) / (upper - lower)
                    assert 0 <= normalized <= 1
                    contribution = normalized * Decimal(run.configuration.validation['weights'][code])
                    assert abs(normalized - Decimal(trace['normalized'])) < Decimal('1e-24')
                    assert abs(contribution - Decimal(trace['contribution'])) < Decimal('1e-24')
                    expected_score += contribution * 100
                assert abs(expected_score - Decimal(row['score_0_100'])) < Decimal('1e-23')
            scores.append(Decimal(row['score_0_100']))
            evidence['scores'] += 1
        assert scores == sorted(scores, reverse=True)
        for row in ordered(run):
            score = Decimal(row['score_0_100'])
            assert row['comparison']['higher'] == sum(value > score for value in scores)
            assert row['comparison']['equal'] == sum(value == score for value in scores)
    actor = get_user_model().objects.get(username=settings.MAIN_TESTING_MANIFEST['admin_username'])
    client = Client()
    client.force_login(actor)
    expected_counts = {'members': Member.objects.count(), 'programs': Program.objects.count(),
                       'applications': ProgramApplication.objects.count(), 'assistance': AssistanceRelease.objects.successful().count()}
    for kind, expected in expected_counts.items():
        url = reverse('reports:' + kind)
        response = client.get(url, {'format': 'csv'})
        assert response.status_code == 200
        csv_rows = list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))
        assert len(csv_rows) - 1 == expected, (kind, len(csv_rows), expected)
        records, columns = report_data(kind, {})
        actual = [[str(v) for v in report_row(kind, item, reveal_assistance=True)] for item in records]
        assert csv_rows[0] == columns and csv_rows[1:] == actual
        xlsx = client.get(url, {'format': 'xlsx'})
        assert xlsx.status_code == 200
        book = load_workbook(BytesIO(xlsx.content), read_only=True)
        # Empty Excel string cells can be represented as None by openpyxl.
        assert [[str(v or '') for v in row] for row in book.active.values] == csv_rows
        book.close()
        pdf = client.get(url, {'format': 'pdf'})
        assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF-')
        for extension, result in (('csv', response), ('xlsx', xlsx), ('pdf', pdf)):
            (out / (kind + '.' + extension)).write_bytes(result.content)
        evidence['exports'][kind] = {'rows': expected, 'csv_matches_database': True, 'xlsx_matches_csv': True,
                                    'pdf_bytes': len(pdf.content)}
        empty = client.get(url, {'start': '1900-01-01', 'end': '1900-01-02', 'format': 'csv'})
        assert len(list(csv.reader(StringIO(empty.content.decode('utf-8-sig'))))) == 1
    for program in Program.objects.all():
        response = client.get(reverse('reports:applications'), {'program': program.pk, 'format': 'csv'})
        assert len(list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))) - 1 == program.applications.count()
    voids = client.get(reverse('reports:assistance'), {'status': 'voided', 'format': 'csv'})
    assert len(list(csv.reader(StringIO(voids.content.decode('utf-8-sig'))))) - 1 == AssistanceRelease.objects.filter(voided_at__isnull=False).count()
    lab = Program.objects.get(name='EWAF Lab — Balanced Weights')
    app = lab.applications.first()
    routes = ['/testing/', '/workspace/applications/', '/members/', '/programs/manage/', '/assistance/releases/',
        '/reports/applications/', '/membership/applications/new/', '/events/manage/observances/',
        f'/programs/manage/{lab.pk}/applications/{app.pk}/', f'/ewaf/programs/{lab.pk}/']
    for route in routes:
        started = perf_counter()
        with CaptureQueriesContext(connection) as queries:
            response = client.get(route)
        assert response.status_code == 200, (route, response.status_code)
        evidence['pages'][route] = {'seconds': perf_counter() - started, 'queries': len(queries)}
    proposal = client.get(reverse('programs:proposal', args=[lab.pk]))
    assert proposal.status_code == 200 and proposal.content.startswith(b'%PDF-')
    (out / 'proposal.pdf').write_bytes(proposal.content)
    public = Client()
    for route in ('/members/', '/reports/applications/', f'/ewaf/programs/{lab.pk}/'):
        assert public.get(route).status_code == 302
    for item in Announcement.objects.published().filter(program__isnull=False):
        payload = item.result_revision.public_payload
        assert all(row['status'] == 'Received' for row in payload['rows'])
        assert len(payload['rows']) == AssistanceRelease.objects.successful().filter(application__program=item.program).count()
        for member in Member.objects.all():
            assert member.full_name not in str(payload)
            assert member.control_number not in str(payload)
    viewer = Client()
    viewer.force_login(get_user_model().objects.get(username='lab_viewer'))
    for route in ('/reports/applications/', f'/ewaf/programs/{lab.pk}/'):
        assert viewer.get(route).status_code == 403
    evidence['permissions'] = {'anonymous_private_access_blocked': True, 'unprivileged_staff_blocked': True,
                               'recipient_masks_verified': True, 'voided_receipts_excluded': True}
    evidence['dataset'] = str(Path(settings.MEDIA_ROOT).parent / 'dataset.json')
    (out / 'results.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(json.dumps(evidence, indent=2), flush=True)
