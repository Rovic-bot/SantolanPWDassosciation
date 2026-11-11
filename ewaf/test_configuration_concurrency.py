from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase
from django.db import close_old_connections, connections
from django.core.exceptions import ValidationError
from .evidence_testsupport import EvidenceHelpers
from .configuration_testsupport import ConfigurationHelpers, equal_judgments
from .configuration_services import record_configuration, record_review
from .configuration_readiness import configuration_diagnostics
from .models import ConfigurationRevision, ConfigurationReview


class ConfigurationConcurrencyTests(ConfigurationHelpers, EvidenceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_evidence()

    def race(self, first, second):
        barrier = Barrier(2)
        def worker(action):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return action()
                except ValidationError:
                    return False
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, action) for action in (first, second)]
            return [future.result(timeout=30) for future in futures]

    def test_two_drafts_same_context_only_one_commits(self):
        values = {**self.common(), 'judgments': equal_judgments(), 'policy_id': self.policy.pk}
        results = self.race(lambda: record_configuration(self.program.pk, **values),
                            lambda: record_configuration(self.program.pk, **values))
        self.assertEqual(sum(row is not False for row in results), 1)
        self.assertEqual(ConfigurationRevision.objects.count(), 1)

    def test_two_reviews_same_context_only_one_commits(self):
        self.draft()
        self.validate()
        values = {**self.common(), 'configuration_id': self.configuration.pk, 'validation_id': self.validation.pk,
                  'finding': 'REVIEWED', 'correction_requests': ''}
        results = self.race(lambda: record_review(self.program.pk, **values), lambda: record_review(self.program.pk, **values))
        self.assertEqual(sum(row is not False for row in results), 1)
        self.assertEqual(ConfigurationReview.objects.count(), 1)

    def test_policy_race_rejects_stale_draft_or_marks_captured_draft_stale(self):
        values = {**self.common(), 'judgments': equal_judgments(), 'policy_id': self.policy.pk}
        results = self.race(lambda: record_configuration(self.program.pk, **values), self.policy_record)
        self.assertIsNot(results[1], False)
        if results[0] is not False:
            result = configuration_diagnostics(self.program.pk, user=self.officer)
            self.assertIn('CONFIGURATION_STALE', {row['code'] for row in result['reasons']})

    def test_terms_race_is_serialized_without_changing_program_version(self):
        from programs.binding_services import capture_terms
        from programs.terms import snapshot_terms, terms_digest
        values = {**self.common(), 'judgments': equal_judgments(), 'policy_id': self.policy.pk}
        results = self.race(lambda: record_configuration(self.program.pk, **values),
            lambda: capture_terms(self.program.pk, user=self.officer, version=0, program_version=self.program.version,
                digest=terms_digest(snapshot_terms(self.program)), reason='Synthetic terms race', confirmed=True))
        self.assertIsNot(results[1], False)
        if results[0] is not False:
            result = configuration_diagnostics(self.program.pk, user=self.officer)
            self.assertIn('CONFIGURATION_STALE', {row['code'] for row in result['reasons']})
        self.program.refresh_from_db()
        self.assertEqual(self.program.version, 0)
