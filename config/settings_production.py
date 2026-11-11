"""Opt-in HTTPS deployment settings. Never read the local development .env."""
import os
from pathlib import Path
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured
from .environment import env_bool, env_list, env_positive_int, required


# Check explicit deployment inputs before importing the common settings.
for _name in ('SECRET_KEY', 'ALLOWED_HOSTS', 'CSRF_TRUSTED_ORIGINS',
              'DB_NAME', 'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT',
              'DB_SSL_CA', 'DEPLOYMENT_STORAGE_BACKEND'):
    required(_name)
if env_bool('DEBUG', False):
    raise ImproperlyConfigured('DEBUG must be false in production.')
os.environ['PYTHON_DOTENV_DISABLED'] = '1'

from .settings import *  # noqa: E402,F403 - keep local settings independent
from .production_logging import REQUEST_LOGGING


DEBUG = False
LOGGING = REQUEST_LOGGING
ROOT_URLCONF = 'config.urls_production'
MIDDLEWARE = list(MIDDLEWARE)
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

if any('*' in host or host.startswith('.') for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured('Production ALLOWED_HOSTS must use explicit hosts, not wildcard domains.')
if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured('Set explicit HTTPS CSRF_TRUSTED_ORIGINS.')
for _origin in CSRF_TRUSTED_ORIGINS:
    _url = urlsplit(_origin)
    if (_url.scheme != 'https' or _url.hostname not in ALLOWED_HOSTS
            or _url.username or _url.password or _url.query or _url.fragment
            or _url.path not in ('', '/')):
        raise ImproperlyConfigured('CSRF_TRUSTED_ORIGINS must use HTTPS and an explicit allowed host.')

SECURE_SSL_REDIRECT = True
# Render terminates TLS and sets this header. Do not expose Gunicorn directly
# or place an untrusted proxy in front of it that preserves spoofed headers.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env_positive_int('SECURE_HSTS_SECONDS', 3600)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', False)
SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', False)

_ca_path = Path(required('DB_SSL_CA'))
if not _ca_path.is_absolute() or not _ca_path.is_file():
    raise ImproperlyConfigured('DB_SSL_CA must point to an existing absolute CA certificate file.')
DATABASES['default']['OPTIONS'] = {
    **DATABASES['default']['OPTIONS'],
    'ssl': {'ca': str(_ca_path)},
    'ssl_mode': 'VERIFY_IDENTITY',
}
DATABASES['default']['CONN_MAX_AGE'] = 60
DATABASES['default']['CONN_HEALTH_CHECKS'] = True

if required('DEPLOYMENT_STORAGE_BACKEND') != 'supabase':
    raise ImproperlyConfigured('Production requires DEPLOYMENT_STORAGE_BACKEND=supabase; local media is not persistent.')
from .storage_configuration import supabase_storage_options

# No default FileSystemStorage fallback on Render's ephemeral filesystem.
MEDIA_ROOT = ''
FILE_UPLOAD_PERMISSIONS = 0o600
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o700
STORAGES = {
    'default': {'BACKEND': 'documents.storage.SupabasePrivateStorage',
                'OPTIONS': supabase_storage_options()},
    # Vendored Bootstrap references source maps that are not in the repository.
    # Compression without manifest rewriting preserves the approved assets.
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'},
}
WHITENOISE_AUTOREFRESH = False
WHITENOISE_USE_FINDERS = False
# MEDIA_ROOT is deliberately not registered with WhiteNoise or public URLs.
