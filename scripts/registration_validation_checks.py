"""Run registration rules and template checks with database access disabled."""
from pathlib import Path
import os
import secrets
import sys


if __name__ == '__main__':
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    sys.path.insert(0, str(root))
    os.environ.update(PYTHON_DOTENV_DISABLED='1', DJANGO_SETTINGS_MODULE='config.settings',
        SECRET_KEY=secrets.token_urlsafe(64), DEBUG='1', ALLOWED_HOSTS='testserver,localhost,127.0.0.1',
        DB_NAME='intake_unused', DB_TEST_NAME='test_intake_unused', DB_USER='unused', DB_PASSWORD='unused',
        DB_HOST='127.0.0.1', DB_PORT='1')
    import django
    from django.conf import settings
    settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.dummy'}}
    django.setup()
    from django.core.management import execute_from_command_line
    execute_from_command_line(['manage.py', 'test', 'membership.test_intake_validation',
        'membership.test_document_ocr', '--noinput', '-v', '2'])
