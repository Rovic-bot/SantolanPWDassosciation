"""Check the retained fictional workspace and its actual local browser pages."""
import csv
import hashlib
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
import subprocess
from decimal import Decimal, localcontext
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from openpyxl import load_workbook
from core.management.commands.demo_data import require_local


class Command(BaseCommand):
    help = 'Verify only the isolated fictional database; optionally exercise the local demo browser.'

    def add_arguments(self, parser):
        parser.add_argument('--browser', action='store_true')

    def handle(self, *args, **options):
        name, server = require_local()
        if (not getattr(settings, 'EWAF_FICTIONAL_DEMO', False) or
                name != settings.DEMO_MANIFEST['database'] or server != settings.DEMO_MANIFEST['server_uuid']):
            raise CommandError('The retained fictional workspace identity is required.')
        from core.demo_seed import seed, counts
        from members.models import Member
        from programs.models import Program, ProgramApplication
        from assistance.models import AssistanceRelease
        from announcements.models import Announcement
        from ewaf import operational_services as operational
        from ewaf.operational_models import OperationalRun
        directory = Path(settings.MEDIA_ROOT).parent
        dataset = json.loads((directory / 'dataset.json').read_text(encoding='utf-8'))
        before = counts()
        if not seed()['idempotent'] or counts() != before:
            raise CommandError('Repeat seed changed the retained dataset.')
        # Compare credentials, roles and permissions against the retained safe fixture.
        # Normal sign-in updates last_login; it is not a password/account reset.
        fixture = json.loads((Path(settings.DEMO_MANIFEST['source_backup']) / 'retained-masters.json').read_text(encoding='utf-8'))
        def auth_rows(rows):
            result = []
            for row in rows:
                if row['model'] in ('auth.user', 'auth.group'):
                    row['fields'].pop('last_login', None)
                    result.append(row)
            return result
        copied = json.loads(serializers.serialize('json', [*Group.objects.order_by('pk'),
            *get_user_model().objects.order_by('pk')], use_natural_foreign_keys=True, use_natural_primary_keys=True))
        if auth_rows(copied) != auth_rows(fixture):
            raise CommandError('Account credentials, groups or permissions changed.')
        backup = Path(settings.DEMO_MANIFEST['source_backup'])
        with (backup / 'before.sql').open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        if checksum != (backup / 'backup.sha256').read_text().split()[0]:
            raise CommandError('Backup checksum mismatch.')
        actor = get_user_model().objects.filter(is_active=True, is_staff=True, is_superuser=True).first()
        client = Client()
        client.force_login(actor)
        evidence = {'database': name, 'accounts_preserved': True, 'backup_verified': True,
                    'seed_idempotent': True, 'counts': before, 'reports': {}, 'scores_verified': 0}
        for run in OperationalRun.objects.all():
            run.clean()
            rows = operational.ordered(run)
            values = [Decimal(row['score_0_100']) for row in rows]
            assert values == sorted(values, reverse=True)
            for row in rows:
                with localcontext() as context:
                    context.prec = 80
                    expected = sum(Decimal(t['normalized']) * Decimal(t['weight']) for t in row['traces']) * 100
                assert abs(expected - Decimal(row['score_0_100'])) < Decimal('1e-24')
                assert Decimal(0) <= expected <= Decimal(100)
                assert [t['criterion'] for t in row['traces']] == ['SI', 'ES', 'PA', 'ND']
                evidence['scores_verified'] += 1
        expected_counts = {'members': Member.objects.count(), 'programs': Program.objects.count(),
            'applications': ProgramApplication.objects.count(), 'assistance': AssistanceRelease.objects.successful().count()}
        for kind, count in expected_counts.items():
            url = reverse('reports:' + kind)
            csv_response = client.get(url, {'format': 'csv'})
            csv_rows = list(csv.reader(StringIO(csv_response.content.decode('utf-8-sig'))))
            assert csv_response.status_code == 200 and len(csv_rows) - 1 == count
            xlsx_response = client.get(url, {'format': 'xlsx'})
            workbook = load_workbook(BytesIO(xlsx_response.content), read_only=True)
            assert list(workbook.active.values) == [tuple(row) for row in csv_rows]
            workbook.close()
            pdf = client.get(url, {'format': 'pdf'})
            assert pdf.status_code == 200 and pdf.content.startswith(b'%PDF-')
            for format, response in (('csv', csv_response), ('xlsx', xlsx_response), ('pdf', pdf)):
                (directory / f'{kind}-report.{format}').write_bytes(response.content)
            evidence['reports'][kind] = {'rows': count, 'formats': ['csv', 'xlsx', 'pdf']}
        for program in Program.objects.all():
            proposal = client.get(reverse('programs:proposal', args=[program.pk]))
            assert proposal.status_code == 200 and proposal.content.startswith(b'%PDF-')
            response = client.get(reverse('reports:applications'), {'format': 'csv', 'program': program.pk,
                'assistance_type': program.assistance_type})
            assert len(list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))) - 1 == program.applications.count()
        for kind in ('programs', 'applications', 'assistance'):
            response = client.get(reverse('reports:' + kind), {'start': '1900-01-01', 'end': '1900-01-02', 'format': 'csv'})
            assert len(list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))) == 1
        voids = client.get(reverse('reports:assistance'), {'status': 'voided', 'format': 'csv'})
        assert len(list(csv.reader(StringIO(voids.content.decode('utf-8-sig'))))) - 1 == before['voided_receipts']
        public = Client()
        for item in Announcement.objects.published():
            response = public.get(reverse('announcements:detail', args=[item.pk]))
            assert response.status_code == 200
            if item.program_id:
                payload = item.result_revision.public_payload
                assert all(row['status'] == 'Received' for row in payload['rows'])
                assert len(payload['rows']) == AssistanceRelease.objects.successful().filter(application__program=item.program).count()
                for member in Member.objects.all():
                    assert member.full_name not in str(payload)
                    assert member.address not in str(payload)
                    assert member.control_number not in str(payload)
        first = Member.objects.first()
        assert public.get(reverse('members:detail', args=[first.pk])).status_code == 302
        (directory / 'verification.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        if options['browser']:
            dataset = json.loads((directory / 'dataset.json').read_text(encoding='utf-8'))
            display_run = OperationalRun.objects.filter(program_id=dataset['demonstration_program']).first()
            result = subprocess.run(['node', str(settings.BASE_DIR / 'scripts/demo_portal_qa.cjs')],
                env={**os.environ, 'QA_URL': 'http://127.0.0.1:8001',
                     'QA_COOKIE_NAME': settings.SESSION_COOKIE_NAME,
                     'QA_SESSION': client.cookies[settings.SESSION_COOKIE_NAME].value,
                     'QA_OUTPUT': str(directory), 'QA_DATASET': str(directory / 'dataset.json'),
                     'QA_PROGRAM_COUNT': str(Program.objects.count()),
                     'QA_CURRENT_SCORES': json.dumps([row['score_0_100'] for row in operational.ordered(display_run)]),
                     'QA_MEMBER': str(first.pk), 'QA_REGISTRATION': str(first.application.reference)}, cwd=settings.BASE_DIR, capture_output=True,
                encoding='utf-8', timeout=300)
            if result.returncode:
                raise CommandError(result.stdout + result.stderr)
            self.stdout.write(result.stdout)
        self.stdout.write(json.dumps(evidence, indent=2))
