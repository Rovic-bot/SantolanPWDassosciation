"""Fresh local database, real migrations, and no demo provisioning or fallback."""
import json
import os
from .fresh_development import LOCAL, load_manifest

_manifest = load_manifest()
for _key, _value in {
    'PYTHON_DOTENV_DISABLED': '1', 'SECRET_KEY': _manifest['secret'], 'DEBUG': '1',
    'DB_HOST': _manifest['host'], 'DB_PORT': str(_manifest['mysql_port']),
    'DB_NAME': _manifest['database'], 'DB_USER': _manifest['user'], 'DB_PASSWORD': _manifest['password'],
    'DB_TEST_NAME': 'test_santolan_pwd_development_unused',
    'ALLOWED_HOSTS': 'localhost,127.0.0.1',
    'SESSION_COOKIE_SECURE': '0', 'CSRF_COOKIE_SECURE': '0', 'SECURE_SSL_REDIRECT': '0',
}.items():
    os.environ[_key] = _value

from .settings import *

# Keep the existing feature capabilities; real policy and business records are
# entered by the administrator. No historical/demo settings module is imported.
MIGRATION_MODULES = {}
EWAF_FICTIONAL_DEMO = False
EWAF_VAULT_ENABLED = True
EWAF_DATASET_POLICY_ENABLED = True
EWAF_DATASET_SCORING_ENABLED = True
PROGRAM_APPLICATION_WORKFLOW_ENABLED = True
PDAO_ENFORCEMENT_ENABLED = False
PDAO_REGISTRATION_ENABLED = True
REFERRAL_ENABLED = True
LOGIN_REDIRECT_URL = '/dashboard/'
MEDIA_ROOT = LOCAL / 'private-media'
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.filebased.EmailBackend')
EMAIL_FILE_PATH = LOCAL / 'email-outbox'
CERTIFICATE_EMAIL_PROVIDER = 'gmail'
CERTIFICATE_OFFICE_EXECUTABLE = os.environ.get('CERTIFICATE_OFFICE_EXECUTABLE') or str(
    BASE_DIR / '.local/certificate-resend-20261106/libreoffice/extracted/program/soffice.exe')
SESSION_COOKIE_NAME = 'santolan_development_session'
CSRF_COOKIE_NAME = 'santolan_development_csrf'
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
ROOT_URLCONF = 'config.fresh_development_urls'
MIDDLEWARE = ['config.fresh_development.LocalIdentityMiddleware', *MIDDLEWARE]
ASSOCIATION_REGISTRATION_POLICY = json.loads((LOCAL / 'registration-policy.json').read_text(encoding='utf-8'))

from django.db.backends.signals import connection_created
from .fresh_development import verify_connection
connection_created.connect(verify_connection, dispatch_uid='fresh_local_database_identity', weak=False)
