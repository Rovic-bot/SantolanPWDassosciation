"""Rehearse the observed local 0004 -> 0008 migration path on fictional MySQL."""
from io import StringIO
from pathlib import Path
import os
from unittest.mock import patch
from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, SimpleTestCase
from .operational_testsupport import OperationalHelpers
from .operational_models import OperationalConfiguration, OperationalRun, OperationalDecision


class OperationalMigrationTests(OperationalHelpers, TransactionTestCase):
    def test_observed_application_schema_path_preserves_all_preexisting_fictional_rows(self):
        from scripts.durable_test_runner import require_disposable
        from .operational_services import available
        self.setup_operational()
        require_disposable()
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        new_models = (OperationalConfiguration, OperationalRun, OperationalDecision)
        new_tables = {m._meta.db_table for m in new_models}
        migration = executor.loader.get_migration('ewaf', '0008_operational_four')
        self.assertEqual(sum(type(op).__name__ == 'CreateModel' for op in migration.operations), 3)
        self.assertTrue(all(type(op).__name__ in ('CreateModel', 'AddConstraint') for op in migration.operations))
        output = StringIO()
        call_command('sqlmigrate', 'ewaf', '0008', stdout=output)
        self.assertNotIn('INSERT INTO', output.getvalue())
        self.assertNotIn('DELETE FROM', output.getvalue())
        if os.environ.get('G12_ARTIFACT_DIR'):
            Path(os.environ['G12_ARTIFACT_DIR'], 'operational-schema.sql').write_text(output.getvalue(), encoding='utf-8')
        try:
            MigrationExecutor(connection).migrate([('ewaf', '0004_scoring_diagnostics')])
            self.assertFalse(available())
            old_tables = set(connection.introspection.table_names())
            old_models = [m for m in apps.get_models() if m._meta.db_table in old_tables]
            def rows():
                return {m._meta.label: list(m.objects.order_by('pk').values()) for m in old_models}
            before = rows()
            from django.urls import reverse
            self.client.force_login(self.officer)
            # Session creation is intentional and included in preservation baseline.
            before = rows()
            self.assertEqual(self.client.get(reverse('ewaf:operational_programs')).status_code, 503)
            for cycle in range(2):
                MigrationExecutor(connection).migrate(leaves)
                self.assertTrue(available())
                self.assertEqual(rows(), before)
                self.assertEqual(new_tables & set(connection.introspection.table_names()), new_tables)
                for model in new_models:
                    self.assertFalse(model.objects.exists())
                MigrationExecutor(connection).migrate([('ewaf', '0004_scoring_diagnostics')])
                self.assertEqual(rows(), before)
            MigrationExecutor(connection).migrate(leaves)
            self.assertEqual(rows(), before)
            with connection.cursor() as cursor:
                for model in new_models:
                    constraints = connection.introspection.get_constraints(cursor, model._meta.db_table)
                    for item in model._meta.constraints:
                        self.assertIn(item.name, constraints)
                    for field in model._meta.fields:
                        if field.is_relation:
                            self.assertTrue(any(c.get('foreign_key') and c['columns'] == [field.column] for c in constraints.values()))
        finally:
            MigrationExecutor(connection).migrate(leaves)


class OperationalStartupTests(SimpleTestCase):
    def test_exact_unapplied_additive_schema_is_deferred_and_changed_schema_blocks(self):
        from core.management.commands.runlocal import validate_plan
        from core.test_local_startup import planned
        plan = [planned('ewaf', '0008_operational_four')]
        self.assertTrue(validate_plan(plan))
        with patch('core.management.commands.runlocal.OPERATIONAL_SHA256', '0' * 64), self.assertRaises(CommandError):
            validate_plan(plan)
