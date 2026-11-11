"""Broad ordinary-app suite with explicit historical-migration exclusions."""
import json
from pathlib import Path
from unittest import TestSuite
from django.test.runner import iter_test_cases
from scripts.remaining_phases_test_runner import RemainingPhasesTestRunner

# These classes apply/reverse historical migrations outside this authorization.
# Keep their original code/assertions intact; list every excluded test as Not Run.
EXCLUDED_CLASSES = {
    'core.test_local_startup.LocalStartupDatabaseTests',
    'membership.test_profile_migrations.ProfileMigrationTests',
    'members.test_catalog_migration.CatalogMigrationTests',
    'events.test_observance_workflow.ObservanceMigrationTests',
    'programs.test_approved_terms.ApprovedTermsMigrationTests',
    'programs.test_pdao_approval.PDAOApprovalMigrationTests',
    'ewaf.test_evidence_migrations.EvidencePreservationTests',
    'ewaf.test_configuration_migrations.ConfigurationPreservationTests',
    'ewaf.test_scoring_migrations.ScoringPreservationTests',
    'ewaf.test_durable_migrations.DurableMigrationTests',
    'ewaf.test_generation_migrations.GenerationMigrationTests',
    'ewaf.test_decision_migrations.DecisionMigrationTests',
    'ewaf.test_operational_migrations.OperationalMigrationTests',
}

# These three business-row tests share a class with migration tests but do not
# execute migration files. Include them in the available suite.
INDEPENDENT_METHODS = {
    'test_evidence_operations_preserve_complete_existing_business_rows',
    'test_all_g12_and_business_rows_preserved_by_g14_workflow',
    'test_entire_historical_g12_g14_business_rows_preserved',
}


class RemainingFullTestRunner(RemainingPhasesTestRunner):
    def build_suite(self, test_labels=None, **kwargs):
        suite = super().build_suite(test_labels, **kwargs)
        kept, excluded = [], []
        for test in iter_test_cases(suite):
            class_name = test.__class__.__module__ + '.' + test.__class__.__name__
            (excluded if class_name in EXCLUDED_CLASSES and test._testMethodName not in INDEPENDENT_METHODS else kept).append(test)
        output = Path(__file__).resolve().parents[1] / 'docs/remaining-phases-2026-10-23/phase5/final-suite-inventory.json'
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps({'included': [test.id() for test in kept],
            'not_run_historical_migrations': [test.id() for test in excluded],
            'not_installed': ['program_intake', 'main_testing'],
            'reason': 'No protected/historical migration execution or optional app activation is authorized.'}, indent=2) + '\n', encoding='utf-8')
        print(f'Available ordinary-app suite: {len(kept)} tests; {len(excluded)} historical migration tests explicitly excluded.', flush=True)
        return TestSuite(kept)
