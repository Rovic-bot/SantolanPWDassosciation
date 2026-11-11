"""Production diagnostics must identify failures without disclosing their data."""
from contextlib import redirect_stderr
from io import StringIO
import json
import logging
import subprocess
import sys
from types import SimpleNamespace

from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.test import SimpleTestCase

from config.production_logging import SanitizedRequestFormatter, SanitizedRequestHandler
from . import test_deployment


class ProductionLoggingTests(SimpleTestCase):
    def record(self, exception=None):
        record = logging.LogRecord('django.request', logging.ERROR, 'private-file.py', 1,
            'private URL %s', ('https://secret.invalid/evidence?token=private',),
            (type(exception), exception, None) if exception is not None else None)
        record.status_code = 500
        record.request = SimpleNamespace(resolver_match=SimpleNamespace(view_name='core:about'))
        return record

    def test_only_allowlisted_fields_survive_sensitive_record_and_chained_exception(self):
        error = OperationalError(1045, 'password=private; user=private; SQL parameters=private')
        error.__cause__ = ValueError('token=private')
        record = self.record(error)
        record.exc_text = 'cached private traceback'
        record.stack_info = 'private stack locals'
        record.sql = 'SELECT private'
        record.params = ('private member name',)
        record.request.body = b'private medical evidence'
        record.request.COOKIES = {'sessionid': 'private'}
        record.request.META = {'HTTP_AUTHORIZATION': 'Bearer private'}
        record.request.FILES = {'document': b'private uploaded content'}
        self.assertEqual(json.loads(SanitizedRequestFormatter().format(record)), {
            'event': 'django_request_error', 'route': 'about', 'status': 500,
            'category': 'database', 'exception': 'OperationalError',
            'mysql_code': 1045, 'error': 'authentication_denied',
        })

    def test_unknown_types_codes_routes_and_statuses_cannot_become_log_text(self):
        private_exception = type('PrivateMemberName', (Exception,), {})
        record = self.record(private_exception('private'))
        record.request.resolver_match.view_name = 'private-document-token'
        record.status_code = 'private'
        data = json.loads(SanitizedRequestFormatter().format(record))
        self.assertEqual(data, {'event': 'django_request_error', 'route': 'other',
            'status': None, 'category': 'application', 'exception': 'Exception'})
        for code in ('1045 private', 999999, True):
            with self.subTest(code=code):
                data = json.loads(SanitizedRequestFormatter().format(
                    self.record(ProgrammingError(code, 'private'))))
                self.assertNotIn('mysql_code', data)
                self.assertNotIn('private', json.dumps(data))

    def test_formatter_never_formats_message_exception_or_reads_request_body(self):
        class Unprintable:
            def __str__(self):
                raise AssertionError('Sensitive value formatted')

        class PrivateRequest:
            resolver_match = None

            @property
            def body(self):
                raise AssertionError('Body accessed')

        record = self.record(ValueError(Unprintable()))
        record.msg = Unprintable()
        record.request = PrivateRequest()
        data = json.loads(SanitizedRequestFormatter().format(record))
        self.assertEqual(data['exception'], 'ValueError')
        self.assertEqual(data['route'], 'other')

    def test_stderr_failure_never_dumps_original_log_record(self):
        class BrokenStream:
            def write(self, value):
                raise OSError('private sink details')

        handler = SanitizedRequestHandler(BrokenStream())
        handler.setFormatter(SanitizedRequestFormatter())
        with redirect_stderr(StringIO()) as fallback:
            handler.handle(self.record(ValueError('private')))
        self.assertEqual(fallback.getvalue(), '')

    def test_actual_production_requests_log_once_to_stderr_and_keep_generic_500(self):
        fixture = test_deployment.ProductionSettingsTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        script = r'''
import json
import logging
from unittest.mock import patch
import django
django.setup()
from django.conf import settings
from django.db import OperationalError, ProgrammingError
from django.db.backends.mysql.base import DatabaseWrapper
from django.http import HttpResponseServerError
from django.template import TemplateDoesNotExist
from django.test import Client

assert settings.DEBUG is False
patch.object(DatabaseWrapper, 'get_new_connection',
    side_effect=AssertionError('Unexpected database connection in diagnostic tests')).start()
client = Client(raise_request_exception=False)
cases = [
    ('/', 'core.content.published_content', OperationalError(2026, 'PRIVATE_SECRET TLS hostname')),
    ('/about/', 'core.content.published_content', TemplateDoesNotExist('PRIVATE_SECRET template')),
    ('/programs/', 'programs.views.Program.objects.public', ProgrammingError(1054, 'PRIVATE_SECRET SQL')),
]
for path, target, error in cases:
    with patch(target, side_effect=error):
        response = client.get(path + '?token=PRIVATE_SECRET', secure=True,
            HTTP_HOST='deployment.example.invalid', HTTP_AUTHORIZATION='Bearer PRIVATE_SECRET',
            HTTP_COOKIE='sessionid=PRIVATE_SECRET')
    assert response.status_code == 500
    assert b'PRIVATE_SECRET' not in response.content
    assert b'Traceback' not in response.content
    assert b'Server Error' in response.content

# Django also logs explicit 500 responses without an attached exception.
with patch('core.views.render', return_value=HttpResponseServerError()):
    with patch('core.content.published_content', return_value={}):
        response = client.get('/about/', secure=True, HTTP_HOST='deployment.example.invalid')
assert response.status_code == 500
with patch('django.middleware.security.SecurityMiddleware.process_request',
           side_effect=OSError('PRIVATE_SECRET middleware')):
    response = client.get('/private-evidence-token/', secure=True,
        HTTP_HOST='deployment.example.invalid')
assert response.status_code == 500
assert b'PRIVATE_SECRET' not in response.content
assert client.get('/healthz/', secure=True, HTTP_HOST='deployment.example.invalid').status_code == 200
logger = logging.getLogger('django.request')
assert not logger.propagate and len(logger.handlers) == 1
assert not logger.disabled
print('production request checks passed')
'''
        result = subprocess.run([sys.executable, '-c', script], env=fixture.environment,
            cwd=settings.BASE_DIR, text=True, capture_output=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'production request checks passed')
        self.assertNotIn('PRIVATE_SECRET', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        # WhiteNoise may warn that this checkout has no collected STATIC_ROOT.
        lines = [line for line in result.stderr.splitlines() if line.startswith('{')]
        records = [json.loads(line) for line in lines]
        self.assertEqual(len(records), 5, result.stderr)
        self.assertEqual([item['route'] for item in records], ['home', 'about', 'programs', 'about', 'other'])
        self.assertEqual([item['exception'] for item in records],
            ['OperationalError', 'TemplateDoesNotExist', 'ProgrammingError', 'none', 'OSError'])
        self.assertEqual(records[0]['error'], 'tls_connection_failed')
        self.assertEqual(records[2]['error'], 'unknown_column')
