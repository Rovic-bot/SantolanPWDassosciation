"""Deployment boundaries checked with synthetic settings and disposable files."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory

from django.conf import settings
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings


class ProductionSettingsTests(SimpleTestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.ca = self.root / 'synthetic-ca.pem'
        # This fixture checks path configuration, never a real TLS connection.
        self.ca.write_text('Synthetic CA path fixture, not an issuing certificate.', encoding='utf-8')
        self.environment = {
            **os.environ,
            'DJANGO_SETTINGS_MODULE': 'config.settings_production',
            'SECRET_KEY': secrets.token_urlsafe(64),
            'DEBUG': 'False',
            'ALLOWED_HOSTS': 'deployment.example.invalid',
            'CSRF_TRUSTED_ORIGINS': 'https://deployment.example.invalid',
            'DB_NAME': 'deployment_check_only',
            'DB_TEST_NAME': 'test_deployment_check_only',
            'DB_USER': 'synthetic_deployment_user',
            'DB_PASSWORD': secrets.token_urlsafe(32),
            'DB_HOST': 'db.example.invalid',
            'DB_PORT': '3306',
            'DB_SSL_CA': str(self.ca),
            'DEPLOYMENT_STORAGE_BACKEND': 'supabase',
            'SUPABASE_PROJECT_REF': 'abcdefghijklmnopqrst',
            'SUPABASE_STORAGE_BUCKET': 'synthetic-private',
            'SUPABASE_S3_REGION': 'ap-southeast-1',
            'SUPABASE_S3_ACCESS_KEY_ID': secrets.token_hex(16),
            'SUPABASE_S3_SECRET_ACCESS_KEY': secrets.token_urlsafe(32),
            'SUPABASE_SECRET_KEY': 'sb_secret_' + secrets.token_urlsafe(32),
            'SECURE_SSL_REDIRECT': 'False',
            'SESSION_COOKIE_SECURE': 'False',
            'CSRF_COOKIE_SECURE': 'False',
            'SECURE_HSTS_SECONDS': '3600',
            'SECURE_HSTS_INCLUDE_SUBDOMAINS': 'False',
            'SECURE_HSTS_PRELOAD': 'False',
        }

    def inspect(self, **changes):
        environment = {**self.environment, **changes}
        environment = {key: value for key, value in environment.items() if value is not None}
        script = '''
import json
from config import settings_production as s
print(json.dumps({
    'debug': s.DEBUG, 'engine': s.DATABASES['default']['ENGINE'],
    'ssl_mode': s.DATABASES['default']['OPTIONS']['ssl_mode'],
    'proxy': s.SECURE_PROXY_SSL_HEADER, 'https': s.SECURE_SSL_REDIRECT,
    'session_secure': s.SESSION_COOKIE_SECURE, 'csrf_secure': s.CSRF_COOKIE_SECURE,
    'media': str(s.MEDIA_ROOT), 'static': str(s.STATIC_ROOT),
    'storage': s.STORAGES['staticfiles']['BACKEND'],
    'private_storage': s.STORAGES['default']['BACKEND'],
    'dotenv_disabled': __import__('os').environ.get('PYTHON_DOTENV_DISABLED'),
    'upload_mode': s.FILE_UPLOAD_PERMISSIONS,
}))
'''
        return subprocess.run([sys.executable, '-c', script], env=environment,
                              cwd=settings.BASE_DIR, text=True, capture_output=True, timeout=20)

    def test_production_preserves_mysql_and_enforces_https_private_storage(self):
        result = self.inspect()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertFalse(data['debug'])
        self.assertEqual(data['engine'], 'django.db.backends.mysql')
        self.assertEqual(data['ssl_mode'], 'VERIFY_IDENTITY')
        self.assertEqual(data['proxy'], ['HTTP_X_FORWARDED_PROTO', 'https'])
        self.assertTrue(data['https'] and data['session_secure'] and data['csrf_secure'])
        self.assertEqual(data['storage'], 'whitenoise.storage.CompressedStaticFilesStorage')
        self.assertNotEqual(data['media'], data['static'])
        self.assertEqual(data['dotenv_disabled'], '1')
        self.assertEqual(data['upload_mode'], 0o600)
        self.assertEqual(data['private_storage'], 'documents.storage.SupabasePrivateStorage')
        self.assertEqual(data['media'], '')

    def test_missing_deployment_secrets_cannot_fall_back_to_local_dotenv(self):
        result = self.inspect(SECRET_KEY=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Missing required environment variable: SECRET_KEY', result.stderr)

    def test_debug_and_wildcard_hosts_are_rejected(self):
        for changes in ({'DEBUG': 'True'}, {'ALLOWED_HOSTS': '*'},
                        {'ALLOWED_HOSTS': '.example.invalid'}):
            with self.subTest(changes=changes):
                self.assertNotEqual(self.inspect(**changes).returncode, 0)

    def test_http_or_unapproved_csrf_origins_are_rejected(self):
        for origin in (' , ', 'http://deployment.example.invalid', 'https://other.example.invalid',
                       'https://deployment.example.invalid/private/'):
            with self.subTest(origin=origin):
                self.assertNotEqual(self.inspect(CSRF_TRUSTED_ORIGINS=origin).returncode, 0)

    def test_ca_file_is_required_and_must_exist(self):
        for ca in (None, 'relative.pem', str(self.root / 'missing.pem')):
            with self.subTest(ca=ca):
                self.assertNotEqual(self.inspect(DB_SSL_CA=ca).returncode, 0)

    def test_production_never_falls_back_to_local_media(self):
        for backend in (None, '', 'filesystem', 'unknown'):
            with self.subTest(backend=backend):
                self.assertNotEqual(self.inspect(DEPLOYMENT_STORAGE_BACKEND=backend).returncode, 0)
        result = self.inspect(PRIVATE_MEDIA_ROOT=str(settings.STATIC_ROOT))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['media'], '')

    def test_missing_storage_configuration_and_unsafe_endpoints_are_rejected(self):
        for key in ('SUPABASE_PROJECT_REF', 'SUPABASE_STORAGE_BUCKET', 'SUPABASE_S3_REGION',
                    'SUPABASE_S3_ACCESS_KEY_ID', 'SUPABASE_S3_SECRET_ACCESS_KEY', 'SUPABASE_SECRET_KEY'):
            with self.subTest(key=key):
                self.assertNotEqual(self.inspect(**{key: None}).returncode, 0)
        for changes in ({'SUPABASE_PROJECT_REF': 'attacker.invalid/'},
                        {'SUPABASE_STORAGE_BUCKET': '../public'},
                        {'SUPABASE_S3_REGION': 'invalid region'},
                        {'SUPABASE_SECRET_KEY': 'sb_publishable_not_a_server_key'}):
            self.assertNotEqual(self.inspect(**changes).returncode, 0)


@override_settings(ROOT_URLCONF='config.urls_production', SECURE_SSL_REDIRECT=True,
                   SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https'))
class DeploymentHTTPTests(SimpleTestCase):
    def test_health_is_db_independent_minimal_and_not_cached(self):
        response = self.client.get('/healthz/', HTTP_X_FORWARDED_PROTO='https')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok'})
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.head('/healthz/', secure=True).content, b'')
        self.assertEqual(self.client.post('/healthz/', secure=True).status_code, 405)

    def test_insecure_request_redirects_without_proxy_loop(self):
        response = self.client.get('/healthz/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], 'https://testserver/healthz/')
        self.assertEqual(self.client.get('/healthz/', HTTP_X_FORWARDED_PROTO='https').status_code, 200)

    def test_collected_admin_assets_are_served_but_private_files_are_not(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            media = root / 'private'
            media.mkdir()
            (media / 'synthetic-private-evidence.txt').write_text('Never publish this fixture.', encoding='utf-8')
            middleware = list(settings.MIDDLEWARE)
            middleware.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
            with override_settings(
                DEBUG=False, STATIC_ROOT=root / 'static', MEDIA_ROOT=media,
                STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
                          'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'}},
                MIDDLEWARE=middleware, WHITENOISE_AUTOREFRESH=False, WHITENOISE_USE_FINDERS=False,
            ):
                call_command('collectstatic', interactive=False, verbosity=0)
                for asset in ('css/admin-ui.css?v=20261010-cleanup', 'css/admin.css',
                              'vendor/bootstrap/bootstrap.min.css', 'js/site.js'):
                    response = self.client.get('/static/' + asset, secure=True)
                    self.assertEqual(response.status_code, 200, asset)
                    response.close()
                response = self.client.get('/media/synthetic-private-evidence.txt', secure=True)
                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, 'Never publish this fixture.', status_code=404)
