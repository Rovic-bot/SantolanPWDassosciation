"""Loopback-only fictional workspace. Normal settings and its database stay intact."""
import json
import re
from django.core.exceptions import ImproperlyConfigured
from .settings import *

DEMO_MANIFEST_PATH = BASE_DIR / '.local/demo/connection.json'
if not DEBUG or DATABASES['default']['HOST'] != '127.0.0.1' or str(DATABASES['default']['PORT']) != '3307':
    raise ImproperlyConfigured('The fictional workspace requires the project-local development MySQL instance.')
if not DEMO_MANIFEST_PATH.is_file():
    raise ImproperlyConfigured('Create the isolated workspace with manage.py demo_data --reset first.')
DEMO_MANIFEST = json.loads(DEMO_MANIFEST_PATH.read_text(encoding='utf-8'))
DB_NAME = DEMO_MANIFEST['database']
if not re.fullmatch(r'santolan_demo_[a-z0-9_]+', DB_NAME) or DEMO_MANIFEST.get('purpose') != 'FICTIONAL_LOCAL_DEMONSTRATION':
    raise ImproperlyConfigured('Invalid fictional workspace manifest.')
DATABASES['default'] = {**DATABASES['default'], 'NAME': DB_NAME,
                        'TEST': {'NAME': 'test_' + DB_NAME, 'CHARSET': 'utf8mb4'}}
DB_TEST_NAME = 'test_' + DB_NAME
MEDIA_ROOT = BASE_DIR / '.local/demo' / DB_NAME / 'media'
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'testserver']
EWAF_FICTIONAL_DEMO = True
