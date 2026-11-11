"""Forward/reverse/reapply evidence ONLY on the verified fresh MySQL fixture."""
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from unittest.mock import patch
from io import StringIO

from .durable_services import _assert_history
from .durable_testsupport import DurableHelpers
from .test_generation_foundation import FOUNDATION_MODELS, FoundationHelpers


class GenerationMigrationTests(DurableHelpers, FoundationHelpers, TransactionTestCase):
    def test_eight_table_forward_reverse_reapply_preserves_old_graph_and_rows(self):
        from scripts.durable_test_runner import require_disposable
        self.setup_durable()
        run = self.process(self.request_run())
        from . import durable_services
        with patch('ewaf.durable_services._capture', durable_services._capture_legacy):
            legacy = self.process(self.request_run(request_key='fictional-legacy-preservation'))
        require_disposable()
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        from .decision_models import DevelopmentHumanDecision, DevelopmentHumanDecisionAudit
        from .operational_models import OperationalConfiguration, OperationalRun, OperationalDecision
        # Descendant 0007 is also reversed by migrating to 0005. Its own migration
        # tests prove preservation; only pre-foundation tables exist at this point.
        old_models = [model for model in apps.get_models() if model not in FOUNDATION_MODELS and
                      model not in (DevelopmentHumanDecision, DevelopmentHumanDecisionAudit, OperationalConfiguration, OperationalRun, OperationalDecision)]
        def historical_rows():
            return {model._meta.label: list(model.objects.order_by('pk').values()) for model in old_models}
        # The Terms mutex is already created by old services, so bootstrap doesn't add an old row.
        before = historical_rows()
        tables = {m._meta.db_table for m in FOUNDATION_MODELS}
        try:
            executor.migrate([('ewaf', '0005_durable_development')])
            self.assertFalse(tables & set(connection.introspection.table_names()))
            _assert_history(run)  # Old calculation replay works with no foundation tables.
            _assert_history(legacy)
            self.assertEqual(before, historical_rows())
            from core.management.commands.runlocal import Command
            output = StringIO()
            def read_only(execute, sql, params, many, context):
                self.assertTrue(sql.lstrip().upper().startswith(('SELECT', 'SHOW')), sql)
                return execute(sql, params, many, context)
            with connection.execute_wrapper(read_only):
                Command(stdout=output).check_migrations()
            self.assertIn('remain unapplied as intended', output.getvalue())
            self.assertEqual(before, historical_rows())
            with connection.cursor() as cursor:
                cursor.execute("SELECT app,name,applied FROM django_migrations WHERE NOT (app='ewaf' AND name IN ('0006_source_invalidation_foundation', '0007_development_human_decisions', '0008_operational_four')) ORDER BY app,name")
                recorder = cursor.fetchall()
            executor = MigrationExecutor(connection)
            migration = executor.loader.get_migration('ewaf', '0006_source_invalidation_foundation')
            operations = migration.operations
            self.assertEqual([type(o).__name__ for o in operations[:12]], ['CreateModel'] * 8 + ['AddField'] * 4)
            self.assertEqual({(o.model_name, o.name) for o in operations if type(o).__name__ == 'AddField'},
                {('authoritygeneration', 'last_event'), ('programsourcestate', 'last_invalidation'),
                 ('programsourcestate', 'current_binding'), ('requestsourcebinding', 'expected_current_binding')})
            self.assertTrue(all(type(o).__name__ in ('CreateModel', 'AddField', 'AddIndex', 'AddConstraint') for o in operations))
            names = {m._meta.model_name for m in FOUNDATION_MODELS}
            self.assertTrue(all(getattr(o, 'model_name', getattr(o, 'name', '').lower()) in names for o in operations))
            self.assertIn(('ewaf', '0005_durable_development'), migration.dependencies)
            self.assertIn(('programs', '0005_approved_terms'), migration.dependencies)
            executor.migrate(leaves)
            self.assertEqual(tables & set(connection.introspection.table_names()), tables)
            self.assertTrue(all(not m.objects.exists() for m in FOUNDATION_MODELS))
            self.assertEqual(before, historical_rows())
            self.bootstrap()
            self.advance()
            # Destructive schema reverse is intentionally confined to these fictional new rows.
            MigrationExecutor(connection).migrate([('ewaf', '0005_durable_development')])
            self.assertEqual(before, historical_rows())
            _assert_history(run)
            _assert_history(legacy)
            MigrationExecutor(connection).migrate(leaves)
            self.assertTrue(all(not m.objects.exists() for m in FOUNDATION_MODELS))
            self.assertEqual(before, historical_rows())
            _assert_history(run)
            _assert_history(legacy)
            with connection.cursor() as cursor:
                cursor.execute("SELECT app,name,applied FROM django_migrations WHERE NOT (app='ewaf' AND name IN ('0006_source_invalidation_foundation', '0007_development_human_decisions', '0008_operational_four')) ORDER BY app,name")
                self.assertEqual(recorder, cursor.fetchall())
                cursor.execute('SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')
                engines = dict(cursor.fetchall())
                self.assertTrue(all(engines[t] == 'InnoDB' for t in tables))
        finally:
            MigrationExecutor(connection).migrate(leaves)
