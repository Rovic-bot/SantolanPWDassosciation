"""Exact additive migration rehearsal; no historical schema execution."""
from io import StringIO
from django.core.management import call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.test import TransactionTestCase
from scripts.durable_test_runner import require_disposable
from scripts.revised_ewaf_test_runner import TARGET


class RevisedSchemaTests(TransactionTestCase):
    def test_only_two_new_tables_reverse_forward_with_existing_rows_preserved(self):
        require_disposable()
        from ewaf.revised.models import RevisedPreviewRun, RevisedPreviewReview
        from members.tests import create_member
        from members.models import Member
        member = create_member('SYNTHETIC-REVISED-SCHEMA')
        before = Member.objects.filter(pk=member.pk).values().get()
        loader = MigrationLoader(None)
        migration = loader.disk_migrations[TARGET]
        self.assertEqual([type(op).__name__ for op in migration.operations], ['CreateModel', 'CreateModel'] + ['AddConstraint'] * 6)
        self.assertIn(('ewaf', '0010_shared_configuration_vault'), migration.dependencies)
        self.assertIn(('admin', '0003_logentry_add_action_flag_choices'), migration.dependencies)
        recorder = MigrationRecorder(connection)
        recorder.ensure_schema()
        recorder.migration_qs.all().delete()
        # Explicit model-synchronized fixture history, not a deployed DB inventory.
        for key in loader.disk_migrations:
            recorder.record_applied(*key)
        baseline = set(recorder.applied_migrations())
        before_tables = set(connection.introspection.table_names())
        parents = [('ewaf', '0010_shared_configuration_vault')]
        plan = MigrationExecutor(connection).migration_plan(parents)
        self.assertEqual([(m.app_label, m.name, reverse) for m, reverse in plan], [(*TARGET, True)])
        call_command('migrate', *parents[0], interactive=False, verbosity=0, stdout=StringIO())
        self.assertEqual(set(connection.introspection.table_names()), before_tables - {
            RevisedPreviewRun._meta.db_table, RevisedPreviewReview._meta.db_table})
        self.assertEqual(set(recorder.applied_migrations()), baseline - {TARGET})
        plan = MigrationExecutor(connection).migration_plan([TARGET])
        self.assertEqual([(m.app_label, m.name, reverse) for m, reverse in plan], [(*TARGET, False)])
        call_command('migrate', *TARGET, interactive=False, verbosity=0, stdout=StringIO())
        self.assertEqual(set(connection.introspection.table_names()), before_tables)
        self.assertEqual(set(recorder.applied_migrations()), baseline)
        self.assertEqual(Member.objects.filter(pk=member.pk).values().get(), before)
        self.assertFalse(RevisedPreviewRun.objects.exists())
        self.assertFalse(RevisedPreviewReview.objects.exists())
        print('Only ewaf.0011 reversed/reapplied; synthetic model-derived history; existing member preserved.', flush=True)
