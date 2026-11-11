from django.apps import apps
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase
from django.core.exceptions import ValidationError
from programs.test_approved_terms import TermsHelpers
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from .scoring_testsupport import ScoringHelpers
from .ranking_readiness import ranking_readiness
from .ranking_diagnostics import compare_fixture


class RankingPreservationTests(ScoringHelpers, ConfigurationHelpers, EvidenceHelpers, TermsHelpers, TransactionTestCase):
    def setUp(self):
        from .test_scoring_migrations import ScoringPreservationTests
        ScoringPreservationTests.setUp(self)
        self.propose()
        self.capture_diagnostic()

    def all_rows(self):
        return {model._meta.label_lower: list(model.objects.order_by('pk').values())
                for model in apps.get_models()}

    def test_entire_history_and_audits_unchanged_no_write_queries(self):
        before = self.all_rows()

        def read_only(execute, sql, params, many, context):
            self.assertTrue(sql.lstrip().upper().startswith('SELECT'), sql[:80])
            return execute(sql, params, many, context)

        with connection.execute_wrapper(read_only):
            self.assertTrue(compare_fixture('high-first-v1')['complete'])
            ranking_readiness(self.application.pk, user=self.officer, program_id=self.program.pk)
        self.assertEqual(self.all_rows(), before)

    def test_no_schema_models_or_permissions_added(self):
        leaves = MigrationLoader(connection).graph.leaf_nodes('ewaf')
        self.assertEqual(leaves, [('ewaf', '0008_operational_four')])
        from django.contrib.auth.models import Permission
        self.assertFalse(Permission.objects.filter(codename__icontains='g16').exists())
        self.assertFalse(any(model.__name__.startswith('SyntheticRanking') for model in apps.get_models()))

    def test_retired_workflows_do_not_gain_authority(self):
        from . import services
        for call in (
            lambda: services.save_configuration(user=self.officer, data={}),
            lambda: services.save_input(self.application.pk, user=self.officer, data={}),
            lambda: services.generate_ranking(self.program.pk, user=self.officer, configuration=None, version=1),
            lambda: services.current_ranking(self.program),
            lambda: services.require_ranked(self.application, self.program),
        ):
            with self.assertRaises(ValidationError):
                call()
