"""Fresh synthetic MySQL only; allow only exact reviewed additive migrations."""
import hashlib
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

REVIEWED_MIGRATIONS = {
    ('membership', '0006_association_pending_intake'): 'fc897f9ee2f2f1b2433cccc7bf7f6bd531c199363f0cfa5fe2bdcfb9583b224d',
    ('members', '0006_private_information_review'): 'd7202490dceecda7606d7367b2628fd0097d5fbcad55ae01cf03bbacd32812a1',
    ('core', '0002_resource_publication_metadata'): '25245202eb5c7af929aef66e2664779172c5f165ca2ddcd2d241b36dd4a52454',
}


class RemainingPhasesTestRunner(RegistrationIntakeTestRunner):
    def run_tests(self, test_labels, **kwargs):
        directory = Path(os.environ.get('G12_ARTIFACT_DIR', '')).resolve()
        if (os.environ.get('PYTHON_DOTENV_DISABLED') != '1' or directory.parent != Path(tempfile.gettempdir()).resolve()
                or not directory.name.startswith('santolan-g12-tests-')):
            raise PermissionDenied('Fresh isolated G12 launcher required; no database fallback.')
        apply = MigrationExecutor.apply_migration
        unapply = MigrationExecutor.unapply_migration
        migrate = MigrationExecutor.migrate

        def check_migration(migration):
            key = (migration.app_label, migration.name)
            expected = REVIEWED_MIGRATIONS.get(key)
            path = Path(inspect.getfile(type(migration)))
            if not expected or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise PermissionDenied('Migration outside the exact reviewed additive test scope: ' + str(key))

        def checked_plan(executor, targets, plan=None, *args, **options):
            if options.get('fake') or options.get('fake_initial'):
                raise PermissionDenied('Fake migration execution is outside the reviewed test scope.')
            plan = executor.migration_plan(targets) if plan is None else plan
            # Validate the entire plan before any allowed operation: an invalid
            # mixed plan must not partly reverse a reviewed new schema first.
            for migration, backwards in plan:
                check_migration(migration)
            return migrate(executor, targets, plan, *args, **options)

        def guarded(method):
            def operation(executor, state, migration, *args, **options):
                check_migration(migration)
                return method(executor, state, migration, *args, **options)
            return operation

        with tempfile.TemporaryDirectory(prefix='remaining-phases-media-', dir=directory) as media:
            with override_settings(MEDIA_ROOT=media), \
                    patch.object(MigrationExecutor, 'migrate', checked_plan), \
                    patch.object(MigrationExecutor, 'apply_migration', guarded(apply)), \
                    patch.object(MigrationExecutor, 'unapply_migration', guarded(unapply)):
                print(f'Remaining phases isolated private media: {media}', flush=True)
                return DurableTestRunner.run_tests(self, test_labels, **kwargs)
