"""Fresh disposable MySQL; model sync and only the reviewed dataset-policy migration.

No startup guard, ordinary settings, existing runner allowlist or historical
migration is changed. Use through the existing G12 fresh-instance launcher.
"""
from hashlib import sha256
import inspect
import os
from pathlib import Path
import tempfile
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import override_settings
from scripts.durable_test_runner import DurableTestRunner
from scripts.registration_intake_test_runner import RegistrationIntakeTestRunner

TARGET = ('ewaf', '0012_dataset_policy_integration')
# Pin normalized LF text so Git checkout line endings do not change the review.
MIGRATION_SHA256 = '513bde36d409c5dbff0b4f663b2dc9ab77505df8283f5ca9de714c1c6c917654'


class DatasetPolicyTestRunner(RegistrationIntakeTestRunner):
    def run_tests(self, test_labels, **kwargs):
        directory = Path(os.environ.get('G12_ARTIFACT_DIR', '')).resolve()
        if (os.environ.get('PYTHON_DOTENV_DISABLED') != '1' or
                directory.parent != Path(tempfile.gettempdir()).resolve() or
                not directory.name.startswith('santolan-g12-tests-')):
            raise PermissionDenied('Fresh G12 disposable launcher required.')
        migrate = MigrationExecutor.migrate
        apply, unapply = MigrationExecutor.apply_migration, MigrationExecutor.unapply_migration

        def checked(migration):
            if ((migration.app_label, migration.name) != TARGET or
                    sha256(Path(inspect.getfile(type(migration))).read_text(encoding='utf-8').encode('utf-8')).hexdigest() != MIGRATION_SHA256):
                raise PermissionDenied('Only the exact reviewed dataset-policy migration is allowed.')

        def plan_guard(executor, targets, plan=None, *args, **options):
            if options.get('fake') or options.get('fake_initial'):
                raise PermissionDenied('Fake migration execution is forbidden.')
            plan = executor.migration_plan(targets) if plan is None else plan
            for migration, backwards in plan:
                checked(migration)
            return migrate(executor, targets, plan, *args, **options)

        def guard(operation):
            def call(executor, state, migration, *args, **options):
                checked(migration)
                return operation(executor, state, migration, *args, **options)
            return call

        with tempfile.TemporaryDirectory(prefix='revised-ewaf-media-', dir=directory) as media:
            with override_settings(MEDIA_ROOT=media), patch.object(MigrationExecutor, 'migrate', plan_guard), \
                    patch.object(MigrationExecutor, 'apply_migration', guard(apply)), \
                    patch.object(MigrationExecutor, 'unapply_migration', guard(unapply)):
                print('Revised EWAF isolated synthetic media:', media, flush=True)
                return DurableTestRunner.run_tests(self, test_labels, **kwargs)
