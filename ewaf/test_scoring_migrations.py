from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from programs.test_approved_terms import TermsHelpers
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from .scoring_testsupport import ScoringHelpers
from .models import ScoringPolicyRevision, CalculationDiagnosticRun, CalculationDiagnosticItem, CalculationCriterionTrace

G15_MODELS = (ScoringPolicyRevision, CalculationDiagnosticRun, CalculationDiagnosticItem, CalculationCriterionTrace)


class ScoringPreservationTests(ScoringHelpers, ConfigurationHelpers, EvidenceHelpers, TermsHelpers, TransactionTestCase):
    def setUp(self):
        from .test_configuration_migrations import ConfigurationPreservationTests
        ConfigurationPreservationTests.setUp(self)
        self.draft()
        self.validate()
        self.review()
        self.authority()

    def business_rows(self):
        result = {}
        for model in apps.get_models():
            if model._meta.app_label not in {'ewaf', 'programs', 'membership', 'members', 'documents', 'assistance', 'announcements', 'events'} or model in G15_MODELS:
                continue
            rows = model.objects.order_by('pk')
            if model._meta.label_lower == 'programs.programlog':
                rows = rows.exclude(action__startswith='g15_')
            result[model._meta.label_lower] = list(rows.values())
        return result

    def test_entire_historical_g12_g14_business_rows_preserved(self):
        before = self.business_rows()
        self.propose()
        self.capture_diagnostic()
        self.assertEqual(self.business_rows(), before)

    def test_additive_migration_preserves_rows_without_backfill(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        before = self.business_rows()
        try:
            executor.migrate([('ewaf', '0003_configuration_foundation')])
            executor = MigrationExecutor(connection)
            migration = executor.loader.get_migration('ewaf', '0004_scoring_diagnostics')
            self.assertTrue(all(op.__class__.__name__ in ('CreateModel', 'AddField', 'AddConstraint', 'AddIndex') for op in migration.operations))
            executor.migrate(leaves)
            self.assertEqual(self.business_rows(), before)
            for model in G15_MODELS:
                self.assertEqual(model.objects.count(), 0)
            self.assertFalse(self.officer.groups.exists())
        finally:
            MigrationExecutor(connection).migrate(leaves)
