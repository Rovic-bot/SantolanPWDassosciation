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
        # Rehearse the original graph in its own database. Downgrading the
        # current test schema also removes later models and irreversible data
        # migrations, which cannot represent the historical upgrade contract.
        from scripts.migration_test_support import assert_additive_upgrade
        executor = MigrationExecutor(connection)
        migration = executor.loader.get_migration('ewaf', '0006_source_invalidation_foundation')
        operations = migration.operations
        self.assertEqual([type(o).__name__ for o in operations[:12]], ['CreateModel'] * 8 + ['AddField'] * 4)
        self.assertEqual({(o.model_name, o.name) for o in operations if type(o).__name__ == 'AddField'},
            {('authoritygeneration', 'last_event'), ('programsourcestate', 'last_invalidation'),
             ('programsourcestate', 'current_binding'), ('requestsourcebinding', 'expected_current_binding')})
        self.assertTrue(all(type(o).__name__ in ('CreateModel', 'AddField', 'AddIndex', 'AddConstraint') for o in operations))
        self.assertIn(('ewaf', '0005_durable_development'), migration.dependencies)
        self.assertIn(('programs', '0005_approved_terms'), migration.dependencies)
        assert_additive_upgrade(self, [('ewaf', '0005_durable_development')],
            [('ewaf', '0006_source_invalidation_foundation')],
            [model._meta.label for model in FOUNDATION_MODELS], reversible=True)
        _assert_history(run)
        _assert_history(legacy)
