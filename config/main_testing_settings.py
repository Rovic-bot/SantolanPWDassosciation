"""Dedicated fictional environment; never inherits an application DB connection."""
import json
import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

manifest_path = Path(os.environ['MAIN_TESTING_MANIFEST']).resolve()
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
if manifest.get('purpose') != 'MAIN_FICTIONAL_TESTING' or not manifest['database'].startswith('santolan_lab_'):
    raise ImproperlyConfigured('A dedicated main-testing manifest is required.')
for key, value in {'DB_NAME': manifest['database'], 'DB_USER': manifest['user'],
                   'DB_PASSWORD': manifest['password'], 'DB_HOST': '127.0.0.1', 'DB_PORT': str(manifest.get('port', 3307)),
                   'DB_TEST_NAME': 'test_' + manifest['database'], 'SECRET_KEY': manifest['secret'],
                   'DEBUG': '1', 'PYTHON_DOTENV_DISABLED': '1', 'ALLOWED_HOSTS': 'localhost,127.0.0.1,testserver',
                   'SECURE_SSL_REDIRECT': '0', 'SESSION_COOKIE_SECURE': '0', 'CSRF_COOKIE_SECURE': '0'}.items():
    os.environ[key] = value
from .settings import *

MAIN_TESTING = True
MAIN_TESTING_MANIFEST = manifest
EWAF_FICTIONAL_DEMO = True
MEDIA_ROOT = Path(manifest['media'])
SESSION_COOKIE_NAME = 'santolan_lab_session'
CSRF_COOKIE_NAME = 'santolan_lab_csrf'
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
MIDDLEWARE = ['main_testing.middleware.EnvironmentMiddleware', *MIDDLEWARE]
INSTALLED_APPS = [*INSTALLED_APPS, 'main_testing', 'program_intake']
PROGRAM_INTAKE_ENABLED = True
TEMPLATES[0]['DIRS'].insert(0, BASE_DIR / 'program_intake/templates')
STATICFILES_DIRS.insert(0, BASE_DIR / 'program_intake/static')
TEMPLATES[0]['DIRS'].insert(0, BASE_DIR / 'main_testing/templates')
TEMPLATES[0]['OPTIONS']['context_processors'].append('main_testing.middleware.environment')
STATICFILES_DIRS.insert(0, BASE_DIR / 'main_testing/static')
ROOT_URLCONF = 'main_testing.urls'
