"""Local synthetic EWAF workspace; never loads the normal database connection."""
import json
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

_root = Path(__file__).resolve().parent.parent
_local = _root / '.local/ewaf-twelve-demo'
_manifest = json.loads((_local / 'connection.json').read_text(encoding='utf-8'))
if (_manifest.get('purpose') != 'EWAF_TWELVE_PERSISTENT_DEMO'
        or _manifest.get('database') != 'santolan_ewaf_twelve_demo'
        or Path(_manifest['datadir']).resolve() != (_local / 'mysql-data').resolve()
        or Path(_manifest['media']).resolve() != (_local / 'private-media').resolve()):
    raise ImproperlyConfigured('Use the dedicated EWAF demo launcher and its own manifest.')
for _key, _value in {
    'PYTHON_DOTENV_DISABLED': '1', 'SECRET_KEY': _manifest['secret'], 'DEBUG': '1',
    'DB_HOST': '127.0.0.1', 'DB_PORT': str(_manifest['mysql_port']),
    'DB_NAME': _manifest['database'], 'DB_USER': _manifest['user'], 'DB_PASSWORD': _manifest['password'],
    'DB_TEST_NAME': 'test_ewaf_twelve_unused', 'ALLOWED_HOSTS': 'localhost,127.0.0.1,testserver',
    'SESSION_COOKIE_SECURE': '0', 'CSRF_COOKIE_SECURE': '0', 'SECURE_SSL_REDIRECT': '0',
}.items():
    os.environ[_key] = _value

from .settings import *

EWAF_TWELVE_DEMO = _manifest
EWAF_FICTIONAL_DEMO = True
EWAF_VAULT_ENABLED = True
EWAF_DATASET_POLICY_ENABLED = True
EWAF_DATASET_SCORING_ENABLED = True
PROGRAM_APPLICATION_WORKFLOW_ENABLED = True
PDAO_ENFORCEMENT_ENABLED = True
REFERRAL_ENABLED = False
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
MEDIA_ROOT = _local / 'private-media'
SESSION_COOKIE_NAME = 'santolan_ewaf_twelve_session'
CSRF_COOKIE_NAME = 'santolan_ewaf_twelve_csrf'
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
ROOT_URLCONF = 'scripts.ewaf_twelve_demo_web'
MIDDLEWARE = ['scripts.ewaf_twelve_demo_web.DevelopmentIdentityMiddleware', *MIDDLEWARE]
LOGIN_REDIRECT_URL = '/ewaf-demo/'
# This standalone fixture schema is created from current models, as in the
# validated G12 baseline. It never applies or fakes historical migrations.
MIGRATION_MODULES = {name: None for name in (
    'admin', 'auth', 'contenttypes', 'sessions', 'core', 'accounts', 'members',
    'membership', 'announcements', 'events', 'programs', 'documents', 'assistance',
    'ewaf', 'analytics', 'reports', 'audit')}

from django.db.backends.signals import connection_created
from scripts.ewaf_twelve_demo_web import verify_connection
connection_created.connect(verify_connection, dispatch_uid='ewaf_twelve_demo_identity', weak=False)
