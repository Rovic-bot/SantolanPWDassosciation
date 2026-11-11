"""DDL evidence exclusively within the freshly initialized disposable database."""
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from .durable_testsupport import DurableHelpers


class DurableMigrationTests(DurableHelpers, TransactionTestCase):
    def test_forward_migration_preserves_fictional_business_rows(self):
        self.setup_durable()
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        models = [m for m in apps.get_models() if not m.__name__.startswith('Durable')]
        before = {m._meta.label: list(m.objects.order_by('pk').values()) for m in models}
        try:
            # Only the new, empty tables are reversed; no MySQL DDL rollback claim.
            executor.migrate([('ewaf', '0004_scoring_diagnostics')])
            executor = MigrationExecutor(connection)
            migration = executor.loader.get_migration('ewaf', '0005_durable_development')
            self.assertEqual(sum(type(op).__name__ == 'CreateModel' for op in migration.operations), 6)
            for operation in migration.operations:
                self.assertIn(type(operation).__name__, ('CreateModel', 'AddField', 'AddConstraint'))
                if hasattr(operation, 'model_name'):
                    self.assertTrue(operation.model_name.startswith('durable'))
            executor.migrate(leaves)
            self.assertEqual({m._meta.label: list(m.objects.order_by('pk').values()) for m in models}, before)
            self.assertFalse(self.officer.user_permissions.exists())
            self.assertFalse(self.officer.groups.exists())
            with connection.cursor() as cursor:
                cursor.execute("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE 'ewaf_durable%%'")
                engines = [row[0] for row in cursor.fetchall()]
            self.assertEqual(engines, ['InnoDB'] * 6)
        finally:
            MigrationExecutor(connection).migrate(leaves)
