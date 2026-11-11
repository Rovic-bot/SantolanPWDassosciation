"""Prepare repeatable fictional data without deleting protected application history."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from datetime import datetime
from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

MASTERS = (
    'auth.Group', 'auth.User', 'members.DisabilityType', 'membership.MembershipSettings',
    'documents.DocumentType', 'documents.MembershipDocumentRequirement',
    'assistance.EligibilityStatus', 'core.PublicContent',
    'events.AnnualObservance',
)


def require_local():
    from scripts.local_mysql import check_instance
    config = connection.settings_dict
    if not settings.DEBUG or config['HOST'] != '127.0.0.1' or str(config['PORT']) != '3307':
        raise CommandError('This command only manages the project-local development database.')
    check_instance(connection)
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE(), @@server_uuid')
        return cursor.fetchone()


class Command(BaseCommand):
    help = ('Preview retained data; --reset creates a NEW isolated fictional workspace and retains the old database. '
            '--seed is idempotent and only works with config.demo_settings. Authentication is never flushed.')

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true')
        parser.add_argument('--seed', action='store_true')
        parser.add_argument('--import-masters')

    def handle(self, *args, **options):
        name, identity = require_local()
        tables = set(connection.introspection.table_names())
        if options['seed'] or options['import_masters']:
            if not getattr(settings, 'EWAF_FICTIONAL_DEMO', False) or not hasattr(settings, 'DEMO_MANIFEST'):
                raise CommandError('Seeding requires the dedicated fictional workspace settings.')
            if name != settings.DEMO_MANIFEST['database'] or identity != settings.DEMO_MANIFEST['server_uuid']:
                raise CommandError('Fictional database identity mismatch.')
            if options['import_masters']:
                self.import_masters(Path(options['import_masters']))
                return
            from core.demo_seed import seed
            self.stdout.write(json.dumps(seed(), indent=2))
            return
        preview = {}
        protected = []
        for model in apps.get_models():
            if model._meta.db_table in tables and model._meta.app_label in (
                    'members', 'membership', 'programs', 'documents', 'ewaf', 'assistance', 'announcements'):
                preview[model._meta.label] = model.objects.count()
                protected.extend(f'{model._meta.label}.{field.name}' for field in model._meta.fields
                    if field.is_relation and getattr(field.remote_field.on_delete, '__name__', '') == 'PROTECT')
        self.stdout.write(f'Verified local source: {name}; server UUID: {identity}')
        self.stdout.write(json.dumps({'retained_records': sum(preview.values()),
            'related_tables': len(preview), 'protected_relationships': len(protected)}))
        if not options['reset']:
            self.stdout.write('Preview only. No data changed. --reset creates a fresh fictional workspace; existing history stays retained.')
            return
        root = Path(settings.BASE_DIR)
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S') + '_' + secrets.token_hex(3)
        destination = 'santolan_demo_' + stamp
        directory = root / '.local/backups' / ('demo-' + stamp)
        directory.mkdir(parents=True)
        (directory / 'reset-preview.json').write_text(json.dumps({
            'retained_record_counts': preview, 'protected_relationships': protected,
            'deletions': [], 'strategy': 'New isolated database; protected source history retained.'}, indent=2), encoding='utf-8')
        config = connection.settings_dict
        from scripts.local_mysql import MYSQL, connect, check_instance
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        dump = directory / 'before.sql'
        env = {k: v for k, v in os.environ.items() if k.upper() in {'SYSTEMROOT', 'WINDIR', 'PATH', 'TEMP', 'TMP'}}
        env['MYSQL_PWD'] = config['PASSWORD']
        with (directory / 'backup.log').open('wb') as log:
            subprocess.run([str(MYSQL / 'bin/mysqldump.exe'), '--no-defaults', '--host=127.0.0.1',
                '--port=3307', '--user=' + config['USER'], '--single-transaction', '--skip-lock-tables',
                '--no-tablespaces', '--set-gtid-purged=OFF', '--hex-blob', '--routines', '--events',
                '--triggers', '--result-file=' + str(dump), name], env=env, check=True,
                stdout=log, stderr=subprocess.STDOUT, creationflags=flags)
        if not dump.stat().st_size:
            raise CommandError('Backup is empty; no workspace was created.')
        with dump.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        (directory / 'backup.sha256').write_text(checksum + '  before.sql\n', encoding='ascii')
        (directory / 'RESTORE.txt').write_text(
            'Source database remains untouched: ' + name + '\n'
            'Recovery does not require importing anything: stop the demo server and use Start System.cmd.\n'
            'To recover a separate copy, verify project MySQL on 127.0.0.1:3307 and create an empty database.\n'
            'Verify before.sql against backup.sha256, then use the bundled mysql.exe client with --password\n'
            '(interactive prompt), --host=127.0.0.1 --port=3307 and the empty database name.\n'
            'At the mysql prompt run SOURCE followed by the absolute before.sql path using forward slashes.\n'
            'Verify row counts and application checks before changing any connection. Never import over live data.\n',
            encoding='utf-8')
        rows = []
        for label in MASTERS:
            model = apps.get_model(label)
            if model._meta.db_table in tables:
                rows.extend(model.objects.order_by('pk'))
        fixture = directory / 'retained-masters.json'
        fixture.write_text(serializers.serialize('json', rows,
            use_natural_foreign_keys=True, use_natural_primary_keys=True), encoding='utf-8')
        auth_before = serializers.serialize('json', [
            *apps.get_model('auth.Group').objects.order_by('pk'),
            *apps.get_model('auth.User').objects.order_by('pk')],
            use_natural_foreign_keys=True, use_natural_primary_keys=True)
        admin = connect()
        try:
            check_instance(admin)
            with admin.cursor() as cursor:
                cursor.execute(f'CREATE DATABASE `{destination}` CHARACTER SET utf8mb4')
                grant_name = destination.replace('_', '\\_')
                cursor.execute(f'GRANT ALL ON `{grant_name}`.* TO %s@%s', (config['USER'], 'localhost'))
        finally:
            admin.close()
        manifest_path = root / '.local/demo/connection.json'
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        if manifest_path.exists():
            (directory / 'previous-connection.json').write_bytes(manifest_path.read_bytes())
        manifest_path.write_text(json.dumps({'purpose': 'FICTIONAL_LOCAL_DEMONSTRATION',
            'database': destination, 'server_uuid': identity, 'source_database': name,
            'source_backup': str(directory), 'created_at': stamp,
            'auth_fingerprint': hashlib.sha256(auth_before.encode()).hexdigest()}, indent=2), encoding='utf-8')
        command = [sys.executable, 'manage.py']
        # Every migration and import uses a separate process whose DEFAULT database is the new one.
        # Even old RunPython migrations which do not honor aliases cannot reach the source.
        for number, arguments in enumerate((
                ['migrate', '--noinput'],
                ['demo_data', '--import-masters', str(fixture)],
                ['demo_data', '--seed'])):
            with (directory / f'prepare-{number}.log').open('wb') as output:
                result = subprocess.run([*command, *arguments, '--settings=config.demo_settings'],
                    cwd=root, stdout=output, stderr=subprocess.STDOUT, creationflags=flags)
            if result.returncode:
                raise CommandError(f'Isolated workspace preparation stopped; source retained. Inspect {directory / f"prepare-{number}.log"}')
        auth_after = serializers.serialize('json', [
            *apps.get_model('auth.Group').objects.order_by('pk'),
            *apps.get_model('auth.User').objects.order_by('pk')],
            use_natural_foreign_keys=True, use_natural_primary_keys=True)
        if auth_after != auth_before:
            raise CommandError('Source accounts changed during preparation; inspect the retained backup.')
        self.stdout.write(f'Fictional workspace ready: {destination}. Source records and accounts retained. Backup: {directory}')

    def import_masters(self, path):
        from django.db import transaction
        from documents.models import DocumentType, MembershipDocumentRequirement
        data = json.loads(path.read_text(encoding='utf-8'))
        # Additive capture migrations may already have created these named document
        # types. Match their stable identities; never delete them to force old PKs.
        document_types = [row for row in data if row['model'] == 'documents.documenttype']
        requirements = [row for row in data if row['model'] == 'documents.membershipdocumentrequirement']
        others = [row for row in data if not row['model'].startswith('documents.')]
        with transaction.atomic():
            for record in serializers.deserialize('json', json.dumps(others)):
                record.save()
            mapping = {}
            for row in document_types:
                fields = row['fields'].copy()
                name = fields.pop('name')
                item, _ = DocumentType.objects.update_or_create(name=name, defaults=fields)
                mapping[row['pk']] = item.pk
            for row in requirements:
                fields = row['fields'].copy()
                document_type = mapping[fields.pop('document_type')]
                MembershipDocumentRequirement.objects.update_or_create(document_type_id=document_type, defaults=fields)
        auth = serializers.serialize('json', [
            *apps.get_model('auth.Group').objects.order_by('pk'),
            *apps.get_model('auth.User').objects.order_by('pk')],
            use_natural_foreign_keys=True, use_natural_primary_keys=True)
        if hashlib.sha256(auth.encode()).hexdigest() != settings.DEMO_MANIFEST['auth_fingerprint']:
            raise CommandError('Copied account, password, role or permission data differs from the source.')
        self.stdout.write('Accounts, password hashes, group memberships and permissions match the retained source.')
