"""Serve the real Admin workflow on a verified empty disposable MySQL instance."""
import json
import os
from pathlib import Path
import secrets
import tempfile
from unittest import TestCase
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Serve fictional EWAF through the isolated g12_test_runner wrapper. Never opens the application database.'

    def add_arguments(self, parser):
        parser.add_argument('--port', type=int, default=8019)

    def handle(self, *args, **options):
        directory = Path(os.environ.get('G12_ARTIFACT_DIR', '')).resolve()
        if (os.environ.get('PYTHON_DOTENV_DISABLED') != '1' or not directory.name.startswith('santolan-g12-tests-') or
                directory.parent != Path(tempfile.gettempdir()).resolve() or
                connection.settings_dict['HOST'] != '127.0.0.1' or connection.settings_dict['NAME'] != 'g12_empty'):
            raise CommandError('Run only through scripts/g12_test_runner.py against its new isolated instance.')
        with connection.cursor() as cursor:
            cursor.execute('SELECT DATABASE(), @@datadir')
            database, datadir = cursor.fetchone()
            if database != 'g12_empty' or Path(datadir).resolve() != directory / 'data':
                raise CommandError('Disposable database identity mismatch.')
            cursor.execute('SHOW TABLES')
            if cursor.fetchall():
                raise CommandError('Refusing to seed any nonempty database.')
        # Verified fresh isolated instance only. There is no application-database migrate path.
        call_command('migrate', interactive=False, verbosity=0)
        from ewaf.operational_testsupport import OperationalHelpers
        from ewaf import operational_services as service
        from ewaf.four_criterion_development import ahp
        class Fixture(OperationalHelpers, TestCase):
            pass
        fixture = Fixture()
        settings.EWAF_FICTIONAL_DEMO = True
        # Cookies are scoped by host, not port. Keep this disposable login from
        # replacing the user's regular local Admin session or CSRF cookie.
        settings.SESSION_COOKIE_NAME = 'fictional_ewaf_demo_session'
        settings.CSRF_COOKIE_NAME = 'fictional_ewaf_demo_csrf'
        settings.MESSAGE_STORAGE = 'django.contrib.messages.storage.session.SessionStorage'
        try:
            fixture.setup_operational(additional=3)
            user = fixture.officer
            user.username = 'fictional_ewaf_admin'
            password = secrets.token_urlsafe(18)
            user.set_password(password)
            user.save(update_fields=['username', 'password'])
            service.record_configuration(fixture.program.pk, user=user, expected=service.configuration_token(fixture.program),
                proposed=fixture.proposal, judgments=ahp()['pairs'], status='DRAFT',
                reason='Fictional demonstration draft: review and lock through Admin. Not Association authority.')
            port = options['port']
            if not 1024 <= port <= 65535:
                raise CommandError('Use an unprivileged local port.')
            access = {'url': f'http://127.0.0.1:{port}/ewaf/', 'login': f'http://127.0.0.1:{port}/accounts/login/',
                'username': user.username, 'password': password, 'program': str(fixture.program.pk),
                'fictional_only': True, 'data_lifetime': 'Until this isolated demo process stops; application database unchanged.'}
            output = Path(settings.BASE_DIR) / '.local/ewaf-final/demo-access.json'
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(access, indent=2), encoding='utf-8')
            self.stdout.write('Fictional EWAF Admin ready: ' + access['url'])
            self.stdout.write('Local throwaway login saved to .local/ewaf-final/demo-access.json')
            call_command('runserver', f'127.0.0.1:{port}', use_reloader=False, verbosity=1)
        finally:
            fixture.doCleanups()
