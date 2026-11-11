from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from programs.test_approved_terms import TermsHelpers
from .models import ConfigurationRevision, ConfigurationValidation, ConfigurationReview, ConfigurationAuthorizationEvidence


class ConfigurationPreservationTests(ConfigurationHelpers, EvidenceHelpers, TermsHelpers, TransactionTestCase):
    def setUp(self):
        # Reuse the complete synthetic G12 historical fixture, including terms,
        # bindings, release/void history, result revisions and old calculations.
        from .test_evidence_migrations import EvidencePreservationTests
        EvidencePreservationTests.setUp(self)
        self.policy = self.policy_record()
        self.assess()
        from .evidence_services import record_readiness
        from .readiness import assess_readiness
        diagnostic = assess_readiness(self.application.pk, user=self.officer)
        record_readiness(self.application.pk, user=self.officer, expected_context=diagnostic['context_digest'],
            expected_assessments={row['criterion']: row['assessment'] for row in diagnostic['criteria']},
            reason='Synthetic G12 preserved readiness', confirmed=True)

    def business_rows(self):
        result = {}
        excluded = (ConfigurationRevision, ConfigurationValidation, ConfigurationReview, ConfigurationAuthorizationEvidence)
        for model in apps.get_models():
            if model._meta.app_label not in {'ewaf', 'programs', 'membership', 'members', 'documents', 'assistance', 'announcements', 'events'} or model in excluded:
                continue
            rows = model.objects.order_by('pk')
            if model._meta.label_lower == 'programs.programlog':
                rows = rows.exclude(action__startswith='g14_')
            result[model._meta.label_lower] = list(rows.values())
        return result

    def test_all_g12_and_business_rows_preserved_by_g14_workflow(self):
        before = self.business_rows()
        self.draft()
        self.validate()
        self.review()
        self.authority()
        self.assertEqual(self.business_rows(), before)

    def test_additive_migration_no_backfill_or_inferred_authority(self):
        executor = MigrationExecutor(connection)
        leaves = executor.loader.graph.leaf_nodes()
        before = self.business_rows()
        try:
            executor.migrate([('ewaf', '0002_verified_evidence')])
            executor = MigrationExecutor(connection)
            migration = executor.loader.get_migration('ewaf', '0003_configuration_foundation')
            self.assertTrue(all(op.__class__.__name__ in ('CreateModel', 'AddConstraint', 'AddIndex') for op in migration.operations))
            executor.migrate(leaves)
            self.assertEqual(self.business_rows(), before)
            for model in (ConfigurationRevision, ConfigurationValidation, ConfigurationReview, ConfigurationAuthorizationEvidence):
                self.assertEqual(model.objects.count(), 0)
            self.assertFalse(self.officer.groups.exists())
        finally:
            MigrationExecutor(connection).migrate(leaves)
