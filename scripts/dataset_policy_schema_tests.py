"""Rehearse only additive 0012 on verified disposable model-synchronized MySQL."""
from io import StringIO
from django.core.management import call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from scripts.durable_test_runner import require_disposable
from scripts.dataset_policy_test_runner import TARGET
from ewaf.operational_testsupport import OperationalHelpers


class DatasetPolicySchemaTests(OperationalHelpers, TransactionTestCase):
    def test_additive_reverse_forward_preserves_legacy_configuration_calculation_and_audits(self):
        require_disposable()
        self.setup_operational()
        configuration = self.lock_policy()
        run = self.calculate()
        before_config, before_run = configuration.payload(), run.payload()
        from ewaf.revised.live_models import SharedDatasetPolicy, DatasetInputReview
        from programs.models import ProgramLog
        audits = list(ProgramLog.objects.order_by('pk').values())
        loader = MigrationLoader(None)
        migration = loader.disk_migrations[TARGET]
        self.assertEqual([type(op).__name__ for op in migration.operations],
            ['AddField', 'CreateModel', 'AddField', 'CreateModel', 'AddConstraint'])
        self.assertIn(('ewaf', '0011_revised_dataset_preview'), migration.dependencies)
        recorder = MigrationRecorder(connection)
        recorder.ensure_schema()
        recorder.migration_qs.all().delete()
        # Explicit synthetic model-sync history, not a deployed migration inventory.
        for key in loader.disk_migrations:
            recorder.record_applied(*key)
        baseline = set(recorder.applied_migrations())
        tables = set(connection.introspection.table_names())
        parent = ('ewaf', '0011_revised_dataset_preview')
        plan = MigrationExecutor(connection).migration_plan([parent])
        self.assertEqual([(m.app_label, m.name, reverse) for m, reverse in plan], [(*TARGET, True)])
        call_command('migrate', *parent, interactive=False, verbosity=0, stdout=StringIO())
        self.assertEqual(set(connection.introspection.table_names()), tables - {
            SharedDatasetPolicy._meta.db_table, DatasetInputReview._meta.db_table})
        self.assertEqual(set(recorder.applied_migrations()), baseline - {TARGET})
        call_command('migrate', *TARGET, interactive=False, verbosity=0, stdout=StringIO())
        self.assertEqual(set(connection.introspection.table_names()), tables)
        self.assertEqual(set(recorder.applied_migrations()), baseline)
        configuration.refresh_from_db()
        run.refresh_from_db()
        configuration.clean()
        run.clean()
        self.assertEqual(configuration.payload(), before_config)
        self.assertEqual(run.payload(), before_run)
        self.assertEqual(list(ProgramLog.objects.order_by('pk').values()), audits)
        self.assertFalse(SharedDatasetPolicy.objects.exists())
        self.assertFalse(DatasetInputReview.objects.exists())
        print('Only ewaf.0012 reversed/reapplied in disposable MySQL; legacy payloads, results and audits unchanged; no policy approvals seeded.', flush=True)
