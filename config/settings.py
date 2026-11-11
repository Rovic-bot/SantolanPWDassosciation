"""Foundation settings. Secrets come from the environment, never source code."""
from pathlib import Path
import json
import os
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
from .environment import env_bool, env_list, env_positive_int, required

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env', override=False)
SECRET_KEY = required('SECRET_KEY')
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith(('replace-', 'django-insecure-')):
    raise ImproperlyConfigured('SECRET_KEY must be a generated secret of at least 50 characters.')
DEBUG = env_bool('DEBUG', False)
PDAO_ENFORCEMENT_ENABLED = env_bool('PDAO_ENFORCEMENT_ENABLED', False)
ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1' if DEBUG else '')
if not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
    raise ImproperlyConfigured('Set explicit ALLOWED_HOSTS; wildcard hosts are not allowed.')
INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles',
    'core', 'accounts', 'members', 'membership', 'announcements', 'events',
    'programs', 'documents', 'assistance', 'ewaf', 'analytics', 'reports', 'audit',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True,
    'OPTIONS': {'context_processors': [
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'core.context_processors.navigation',
    ]},
}]
WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'
DB_NAME = required('DB_NAME')
DB_TEST_NAME = os.environ.get('DB_TEST_NAME', f'test_{DB_NAME}')
if not DB_TEST_NAME.startswith('test_') or DB_TEST_NAME.casefold() == DB_NAME.casefold():
    raise ImproperlyConfigured('DB_TEST_NAME must be a separate database starting with test_.')
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.mysql', 'NAME': DB_NAME,
    'USER': required('DB_USER'), 'PASSWORD': required('DB_PASSWORD'),
    'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
    'PORT': os.environ.get('DB_PORT', '3306'),
    'OPTIONS': {
        'charset': 'utf8mb4',
        'init_command': "SET sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'",
        'connect_timeout': 5,
    },
    'TEST': {'NAME': DB_TEST_NAME, 'CHARSET': 'utf8mb4'},
}}
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
# Private documents are delivered by a permission-checked attachment view only.
MEMBERSHIP_FILE_MAX_BYTES = env_positive_int('MEMBERSHIP_FILE_MAX_MB', 5) * 1048576
MEMBERSHIP_TOTAL_MAX_BYTES = env_positive_int('MEMBERSHIP_TOTAL_MAX_MB', 20) * 1048576
ANNOUNCEMENT_IMAGE_MAX_BYTES = env_positive_int('ANNOUNCEMENT_IMAGE_MAX_MB', 5) * 1048576
ANNOUNCEMENT_IMAGE_MAX_PIXELS = env_positive_int('ANNOUNCEMENT_IMAGE_MAX_PIXELS', 16000000)
EVENT_IMAGE_MAX_BYTES = env_positive_int('EVENT_IMAGE_MAX_MB', 5) * 1048576
EVENT_IMAGE_MAX_PIXELS = env_positive_int('EVENT_IMAGE_MAX_PIXELS', 16000000)
EVENT_VERIFICATION_ADDRESS_LIMIT = env_positive_int('EVENT_VERIFICATION_ADDRESS_LIMIT', 50)
EVENT_VERIFICATION_MEMBER_LIMIT = env_positive_int('EVENT_VERIFICATION_MEMBER_LIMIT', 10)
EVENT_VERIFICATION_WINDOW_SECONDS = env_positive_int('EVENT_VERIFICATION_WINDOW_SECONDS', 900)
PROGRAM_VERIFICATION_ADDRESS_LIMIT = env_positive_int('PROGRAM_VERIFICATION_ADDRESS_LIMIT', 50)
PROGRAM_VERIFICATION_MEMBER_LIMIT = env_positive_int('PROGRAM_VERIFICATION_MEMBER_LIMIT', 10)
PROGRAM_VERIFICATION_WINDOW_SECONDS = env_positive_int('PROGRAM_VERIFICATION_WINDOW_SECONDS', 900)
PROGRAM_VERIFICATION_GRANT_SECONDS = env_positive_int('PROGRAM_VERIFICATION_GRANT_SECONDS', 900)
PROGRAM_TRACKING_ENABLED = env_bool('PROGRAM_TRACKING_ENABLED', True)
PROGRAM_TRACKING_QR_ENABLED = env_bool('PROGRAM_TRACKING_QR_ENABLED', True)
PROGRAM_TRACKING_GRANT_SECONDS = env_positive_int('PROGRAM_TRACKING_GRANT_SECONDS', 900)
# Enable the integrated confirmation/screening flow in an authorized environment.
PROGRAM_APPLICATION_WORKFLOW_ENABLED = env_bool('PROGRAM_APPLICATION_WORKFLOW_ENABLED', False)
MEMBERSHIP_SUBMISSION_LIMIT = env_positive_int('MEMBERSHIP_SUBMISSION_LIMIT', 20)
MEMBERSHIP_SUBMISSION_WINDOW_SECONDS = env_positive_int('MEMBERSHIP_SUBMISSION_WINDOW_SECONDS', 3600)
REFERRAL_ENABLED = env_bool('REFERRAL_ENABLED', False)
REFERRAL_GRANT_SECONDS = env_positive_int('REFERRAL_GRANT_SECONDS', 900)
REFERRAL_MEMBER_LIMIT = env_positive_int('REFERRAL_MEMBER_LIMIT', 10)
REFERRAL_ADDRESS_LIMIT = env_positive_int('REFERRAL_ADDRESS_LIMIT', 50)
REFERRAL_WINDOW_SECONDS = env_positive_int('REFERRAL_WINDOW_SECONDS', 900)
REFERRAL_REPLY_LIMIT = env_positive_int('REFERRAL_REPLY_LIMIT', 60)
# Optional server-managed SMTP fallback. A Gmail account connected in the
# referral inbox takes precedence and uses its encrypted, sender-bound password.
# Keep SECRET_KEY outside database backups; it protects that stored credential.
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = env_positive_int('EMAIL_PORT', 587)
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = env_bool('EMAIL_USE_SSL', False)
EMAIL_TIMEOUT = env_positive_int('EMAIL_TIMEOUT', 10)
EMAIL_FILE_PATH = BASE_DIR / '.local/referral-email-outbox'
# Certificate delivery is a separate, explicit Resend connection. Keep keys in
# the environment, never in templates, logs, version control, or public files.
CERTIFICATE_RESEND_ENABLED = env_bool('CERTIFICATE_RESEND_ENABLED', False)
CERTIFICATE_EMAIL_PROVIDER = os.environ.get('CERTIFICATE_EMAIL_PROVIDER', 'resend').lower()
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
RESEND_FROM_EMAIL = os.environ.get('RESEND_FROM_EMAIL', '').strip()
CERTIFICATE_EMAIL_BACKGROUND = env_bool('CERTIFICATE_EMAIL_BACKGROUND', True)
CERTIFICATE_OFFICE_EXECUTABLE = os.environ.get('CERTIFICATE_OFFICE_EXECUTABLE', '')
DATA_UPLOAD_MAX_NUMBER_FILES = 20
FILE_UPLOAD_HANDLERS = [
    'documents.upload_handlers.BoundedUploadHandler',
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]
AUTHENTICATION_BACKENDS = ['accounts.backends.StaffBackend']
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'
LOGIN_USERNAME_LIMIT = env_positive_int('LOGIN_USERNAME_LIMIT', 10)
LOGIN_ADDRESS_LIMIT = env_positive_int('LOGIN_ADDRESS_LIMIT', 50)
LOGIN_WINDOW_SECONDS = env_positive_int('LOGIN_WINDOW_SECONDS', 900)
SESSION_COOKIE_AGE = env_positive_int('SESSION_COOKIE_AGE', 3600)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', not DEBUG)
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', not DEBUG)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS')
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '0'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# Shared, versioned household scoring configuration for new programs.
EWAF_VAULT_ENABLED = os.environ.get("EWAF_VAULT_ENABLED", "False").lower() == "true"
# The document calculation is available with the Configuration Vault. A locked
# scoring policy and complete accepted inputs still gate each program's run.
EWAF_DATASET_POLICY_ENABLED = env_bool('EWAF_DATASET_POLICY_ENABLED', EWAF_VAULT_ENABLED)
EWAF_DATASET_SCORING_ENABLED = env_bool('EWAF_DATASET_SCORING_ENABLED', EWAF_VAULT_ENABLED)

# Explicit deployment opt-in; the local owner-authorized instance enables this
# only after the PDAO schema and focused workflow checks have been applied.
ONLINE_MEMBERSHIP_ENABLED = env_bool('ONLINE_MEMBERSHIP_ENABLED', False)
PDAO_REGISTRATION_ENABLED = ONLINE_MEMBERSHIP_ENABLED
SHORT_REFERENCES_ENABLED = env_bool('SHORT_REFERENCES_ENABLED', False)
if ONLINE_MEMBERSHIP_ENABLED:
    from .registration_workflow import association_policy
    ASSOCIATION_REGISTRATION_POLICY = association_policy(MEMBERSHIP_FILE_MAX_BYTES, MEMBERSHIP_TOTAL_MAX_BYTES)
    # Optional, explicit institutional configuration; never read a local runtime
    # manifest or invent an onsite approval when installing a fresh checkout.
    _registration_policy_file = os.environ.get('ASSOCIATION_REGISTRATION_POLICY_FILE', '').strip()
    if _registration_policy_file:
        try:
            _policy_path = Path(_registration_policy_file)
            if not _policy_path.is_absolute():
                _policy_path = BASE_DIR / _policy_path
            ASSOCIATION_REGISTRATION_POLICY = json.loads(_policy_path.read_text(encoding='utf-8'))
            if not isinstance(ASSOCIATION_REGISTRATION_POLICY, dict):
                raise ValueError('Expected a policy object')
        except (OSError, ValueError) as error:
            raise ImproperlyConfigured('The configured Association registration policy could not be loaded.') from error
