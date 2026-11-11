"""Phase 2A tests on fresh synthetic MySQL, with migration execution disabled.

Use g12_test_runner.py only. Django TEST.MIGRATE=False builds temporary tables
from installed models; it does not apply migration files or exercise migration
history. Ordinary application settings and the startup guard are untouched.
"""
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test.utils import override_settings

from scripts.durable_test_runner import DurableTestRunner


class ReferenceRetrievalTestRunner(DurableTestRunner):
    def run_tests(self, test_labels, **kwargs):
        directory = Path(os.environ.get('G12_ARTIFACT_DIR', '')).resolve()
        if (os.environ.get('PYTHON_DOTENV_DISABLED') != '1' or
                directory.parent != Path(tempfile.gettempdir()).resolve() or
                not directory.name.startswith('santolan-g12-tests-')):
            raise PermissionDenied('Use the verified fresh-instance G12 launcher only.')
        with tempfile.TemporaryDirectory(prefix='phase2a-private-media-', dir=directory) as media:
            with override_settings(MEDIA_ROOT=media):
                print(f'Phase 2A synthetic private media: {media}', flush=True)
                with patch('django.db.migrations.executor.MigrationExecutor.apply_migration',
                           side_effect=PermissionDenied('Phase 2A forbids applying migrations.')), \
                     patch('django.db.migrations.executor.MigrationExecutor.unapply_migration',
                           side_effect=PermissionDenied('Phase 2A forbids reversing migrations.')):
                    return super().run_tests(test_labels, **kwargs)

    def setup_databases(self, **kwargs):
        original = connection.settings_dict['TEST'].get('MIGRATE', True)
        connection.settings_dict['TEST']['MIGRATE'] = False
        try:
            result = super().setup_databases(**kwargs)
        finally:
            connection.settings_dict['TEST']['MIGRATE'] = original
        with connection.cursor() as cursor:
            if 'django_migrations' in connection.introspection.table_names():
                cursor.execute('SELECT COUNT(*) FROM django_migrations')
                if cursor.fetchone()[0]:
                    raise PermissionDenied('Migration records are forbidden in this test setup.')
        # The existing regression fixtures expect these four model-defined
        # labels, normally supplied by a baseline data migration. Reuse the
        # existing synthetic fixture helper without executing that migration.
        from assistance.tests import seed_statuses
        seed_statuses()
        print('Synthetic fixture: existing four eligibility labels (no policy changes).', flush=True)
        print('Phase 2A: temporary model-derived test tables; zero migrations applied.', flush=True)
        return result
