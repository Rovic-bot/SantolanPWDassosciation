"""Back up and compare the existing fictional workspace during UI-only changes."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from .demo_data import require_local

LABELS = (
    'auth.User', 'auth.Group', 'members.Member', 'members.DisabilityType',
    'membership.MembershipApplication', 'membership.MembershipSettings',
    'documents.MembershipApplicationDocument', 'documents.DocumentVerification',
    'programs.Program', 'programs.ProgramApplication', 'programs.ProgramDocument',
    'programs.ApplicationPhoto', 'programs.PhotoVerification',
    'assistance.AssistanceCase', 'assistance.AssistanceRelease',
    'announcements.Announcement', 'announcements.ProgramResultRevision',
    'ewaf.OperationalConfiguration', 'ewaf.OperationalRun', 'ewaf.OperationalDecision',
    'ewaf.CriterionAssessment',
)


def snapshot():
    result = {}
    for label in LABELS:
        model = apps.get_model(label)
        rows = json.loads(serializers.serialize('json', model.objects.order_by('pk')))
        result[label] = {}
        for row in rows:
            row['fields'].pop('last_login', None)
            result[label][str(row['pk'])] = hashlib.sha256(
                json.dumps(row, sort_keys=True).encode()).hexdigest()
    return result


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--capture', action='store_true')

    def handle(self, *args, **options):
        name, identity = require_local()
        manifest = getattr(settings, 'DEMO_MANIFEST', {})
        if (not getattr(settings, 'EWAF_FICTIONAL_DEMO', False) or name != manifest.get('database')
                or identity != manifest.get('server_uuid')):
            raise CommandError('Use only the existing isolated fictional workspace.')
        root = settings.BASE_DIR / '.local/ui-cleanup'
        root.mkdir(exist_ok=True)
        baseline = root / 'preservation.json'
        if options['capture']:
            if baseline.exists():
                raise CommandError('A preservation baseline already exists; it will not be overwritten.')
            from scripts.local_mysql import MYSQL
            config = connection.settings_dict
            dump = root / 'before.sql'
            env = {**os.environ, 'MYSQL_PWD': config['PASSWORD']}
            with (root / 'backup.log').open('wb') as log:
                subprocess.run([str(MYSQL / 'bin/mysqldump.exe'), '--no-defaults',
                    '--host=127.0.0.1', '--port=3307', '--user=' + config['USER'],
                    '--single-transaction', '--skip-lock-tables', '--no-tablespaces',
                    '--set-gtid-purged=OFF', '--hex-blob', '--routines', '--events', '--triggers',
                    '--result-file=' + str(dump), name], env=env, check=True, stdout=log,
                    stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if not dump.stat().st_size:
                raise CommandError('Empty backup.')
            with dump.open('rb') as source:
                checksum = hashlib.file_digest(source, 'sha256').hexdigest()
            baseline.write_text(json.dumps({'database': name, 'backup_sha256': checksum,
                'records': snapshot()}, indent=2), encoding='utf-8')
            self.stdout.write('Existing fictional database backed up; preservation hashes captured. No records changed.')
        else:
            before = json.loads(baseline.read_text(encoding='utf-8'))
            if before['database'] != name:
                raise CommandError('Database identity changed.')
            after = snapshot()
            for label, rows in before['records'].items():
                for pk, digest in rows.items():
                    if after[label].get(pk) != digest:
                        raise CommandError(f'Existing record changed or missing: {label} {pk}')
            self.stdout.write(f'PASS: {sum(map(len, before["records"].values()))} existing records, '
                'relationships, credentials, decisions and calculation payloads unchanged.')
