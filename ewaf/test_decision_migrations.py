"""Approved additive schema exercised only on the registered disposable MySQL."""
from io import StringIO
from pathlib import Path
import os
from unittest.mock import patch

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TransactionTestCase

from core.management.commands.runlocal import validate_plan
from core.test_local_startup import planned
from .four_testsupport import FourHelpers
from .test_source_writers import SourceHelpers
from . import test_generation_processing as previous_tests, durable_services
from .decision_models import DevelopmentHumanDecision as Decision, DevelopmentHumanDecisionAudit as Audit
from . import decision_services


class DecisionStartupTests(SimpleTestCase):
    def test_exact_reviewed_migration_can_remain_unapplied_but_changed_file_blocks(self):
        plan = [planned('ewaf', '0007_development_human_decisions')]
        self.assertTrue(validate_plan(plan))
        with patch('core.management.commands.runlocal.DECISION_SHA256', '0' * 64), self.assertRaises(CommandError):
            validate_plan(plan)
        with self.assertRaises(CommandError):
            validate_plan([planned('ewaf', '0008_future')])


class DecisionMigrationTests(SourceHelpers, FourHelpers, TransactionTestCase):
    context_new = previous_tests.ProcessingTests.context_new
    accept = previous_tests.ProcessingTests.accept
    process_new = previous_tests.ProcessingTests.process_new

    def test_two_table_forward_reverse_reapply_preserves_all_previous_rows(self):
        from scripts.durable_test_runner import require_disposable
        self.setup_durable()
        five = self.process(self.request_run())
        self.register()
        self.install_four()
        four = self.process_new(self.accept())
        decision_services.record(self.program.pk, user=self.officer, expected=self.token(), run_id=four.pk,
            application_id=self.application.pk, decision='SELECT_DEMO', reason='Fictional migration history test',
            expected_revision=0, expected_previous=None)
        require_disposable()
        from .operational_models import OperationalConfiguration, OperationalRun, OperationalDecision
        old_models = [model for model in apps.get_models() if model not in (Decision, Audit, OperationalConfiguration, OperationalRun, OperationalDecision)]
        def rows():
            return {m._meta.label: list(m.objects.order_by('pk').values()) for m in old_models}
        before = rows()
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        migration = executor.loader.get_migration('ewaf', '0007_development_human_decisions')
        names = {'developmenthumandecision', 'developmenthumandecisionaudit'}
        self.assertEqual(sum(type(op).__name__ == 'CreateModel' for op in migration.operations), 2)
        for op in migration.operations:
            self.assertIn(type(op).__name__, ('CreateModel', 'AddConstraint', 'AddIndex'))
            self.assertIn(getattr(op, 'model_name', getattr(op, 'name', '').lower()), names)
        output = StringIO()
        call_command('sqlmigrate', 'ewaf', '0007', stdout=output)
        self.assertNotIn('INSERT INTO', output.getvalue())
        if os.environ.get('G12_ARTIFACT_DIR'):
            Path(os.environ['G12_ARTIFACT_DIR'], 'decision-schema.sql').write_text(output.getvalue(), encoding='utf-8')
        from scripts.migration_test_support import assert_additive_upgrade
        assert_additive_upgrade(self, [('ewaf', '0006_source_invalidation_foundation')],
            [('ewaf', '0007_development_human_decisions')],
            ['ewaf.DevelopmentHumanDecision', 'ewaf.DevelopmentHumanDecisionAudit'], reversible=True)
        self.assertEqual(rows(), before)
        durable_services._assert_history(five)
        durable_services._assert_history(four)
        with connection.cursor() as cursor:
            for model in (Decision, Audit):
                constraints = connection.introspection.get_constraints(cursor, model._meta.db_table)
                for item in [*model._meta.constraints, *model._meta.indexes]:
                    self.assertIn(item.name, constraints)
                for field in model._meta.fields:
                    if field.is_relation:
                        self.assertTrue(any(c.get('foreign_key') and c['columns'] == [field.column]
                                            for c in constraints.values()), field.name)
            if connection.vendor == 'postgresql':
                cursor.execute("SELECT relname,relpersistence FROM pg_class WHERE relnamespace=current_schema()::regnamespace AND relkind='r'")
                expected_engine = 'p'  # Permanent, WAL-logged transactional tables.
            else:
                cursor.execute('SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')
                expected_engine = 'InnoDB'
            engines = dict(cursor.fetchall())
            self.assertTrue(all(engines[m._meta.db_table] == expected_engine for m in (Decision, Audit)))
