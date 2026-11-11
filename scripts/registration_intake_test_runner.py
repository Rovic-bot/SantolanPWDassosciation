"""Verified disposable MySQL only; baseline sync plus explicitly reviewed new migration tests."""
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test.utils import override_settings

from scripts.durable_test_runner import DurableTestRunner


class RegistrationIntakeTestRunner(DurableTestRunner):
    def run_tests(self, test_labels, **kwargs):
        directory = Path(os.environ.get('G12_ARTIFACT_DIR', '')).resolve()
        if (os.environ.get('PYTHON_DOTENV_DISABLED') != '1'
                or directory.parent != Path(tempfile.gettempdir()).resolve()
                or not directory.name.startswith('santolan-g12-tests-')):
            raise PermissionDenied('Use the fresh-instance G12 launcher only.')
        with tempfile.TemporaryDirectory(prefix='phase2b-private-media-', dir=directory) as media:
            with override_settings(MEDIA_ROOT=media):
                print(f'Phase 2B synthetic private media: {media}', flush=True)
                # Schema baseline is created from models. Only the explicit new
                # migration test may invoke its reviewed Migration.apply/unapply.
                with patch('django.db.migrations.executor.MigrationExecutor.apply_migration',
                           side_effect=PermissionDenied('Blanket/historical migration execution is forbidden.')), \
                     patch('django.db.migrations.executor.MigrationExecutor.unapply_migration',
                           side_effect=PermissionDenied('Historical migration reversal is forbidden.')):
                    return super().run_tests(test_labels, **kwargs)

    def setup_databases(self, **kwargs):
        old = connection.settings_dict['TEST'].get('MIGRATE', True)
        connection.settings_dict['TEST']['MIGRATE'] = False
        try:
            result = super().setup_databases(**kwargs)
        finally:
            connection.settings_dict['TEST']['MIGRATE'] = old
        from assistance.tests import seed_statuses
        seed_statuses()
        print('Phase 2B model-synchronized disposable baseline; no historical migrations applied.', flush=True)
        return result
