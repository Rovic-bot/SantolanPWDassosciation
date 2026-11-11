from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from threading import Event
from unittest.mock import patch
from django.test import TransactionTestCase
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from .scoring_testsupport import ScoringHelpers
from .scoring_services import record_scoring_policy, record_applicant_diagnostic
from .models import ScoringPolicyRevision, CalculationDiagnosticRun


class ScoringConcurrencyTests(ScoringHelpers, ConfigurationHelpers, EvidenceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_scoring()

    def race(self, first, second):
        from .test_configuration_concurrency import ConfigurationConcurrencyTests
        return ConfigurationConcurrencyTests.race(self, first, second)

    def test_two_proposals_same_context_only_one_commits(self):
        values = self.proposal_values()
        results = self.race(lambda: record_scoring_policy(self.program.pk, **values),
                            lambda: record_scoring_policy(self.program.pk, **values))
        self.assertEqual(sum(row is not False for row in results), 1)
        self.assertEqual(ScoringPolicyRevision.objects.count(), 2)

    def test_two_captures_get_sequential_complete_histories(self):
        values = self.capture_values()
        results = self.race(lambda: record_applicant_diagnostic(self.application.pk, **values),
                            lambda: record_applicant_diagnostic(self.application.pk, **values))
        self.assertTrue(all(row is not False for row in results))
        self.assertEqual(list(CalculationDiagnosticRun.objects.values_list('revision', flat=True)), [2, 1])
        from .scoring_services import validate_run
        for row in results:
            validate_run(row)

    def test_new_validation_rejects_capture_or_marks_it_outdated(self):
        values = self.capture_values()
        results = self.race(lambda: record_applicant_diagnostic(self.application.pk, **values), self.validate)
        self.assertIsNot(results[1], False)
        if results[0] is not False:
            self.assertNotEqual(results[0].context_digest, self.diagnostic()['context_digest'])

    def test_new_assessment_rejects_capture_or_marks_it_outdated(self):
        values = self.capture_values()
        results = self.race(lambda: record_applicant_diagnostic(self.application.pk, **values), self.assess)
        self.assertIsNot(results[1], False)
        if results[0] is not False:
            self.assertNotEqual(results[0].context_digest, self.diagnostic()['context_digest'])

    def other_selected_application(self):
        from .test_evidence_concurrency import EvidenceConcurrencyTests
        return EvidenceConcurrencyTests.other_selected_application(self)

    def assert_receipt_serialization(self, mutation, action_name):
        from assistance.services import record_log as actual_log
        from .test_evidence_concurrency import worker
        entered, resume, started = Event(), Event(), Event()
        values = self.capture_values()
        def held_log(application, user, action, *args, **kwargs):
            result = actual_log(application, user, action, *args, **kwargs)
            if action == action_name:
                entered.set()
                if not resume.wait(timeout=15):
                    raise RuntimeError('Synthetic writer timeout')
            return result
        def capture():
            started.set()
            return record_applicant_diagnostic(self.application.pk, **values)
        with patch('assistance.services.record_log', side_effect=held_log), ThreadPoolExecutor(max_workers=2) as pool:
            writing = pool.submit(worker, mutation)
            try:
                self.assertTrue(entered.wait(timeout=10))
                capturing = pool.submit(worker, capture)
                self.assertTrue(started.wait(timeout=10))
                with self.assertRaises(FutureTimeout):
                    capturing.result(timeout=.25)
            finally:
                resume.set()
            self.assertIsNot(writing.result(timeout=15), False)
            self.assertIs(capturing.result(timeout=15), False)
        self.assertFalse(CalculationDiagnosticRun.objects.exists())

    def test_cross_program_release_blocks_competing_capture(self):
        from assistance.services import record_release
        from assistance.tests import release_data
        other = self.other_selected_application()
        self.assert_receipt_serialization(lambda: record_release(other.pk, user=self.officer, data=release_data(other)), 'assistance_released')

    def test_cross_program_void_blocks_competing_capture(self):
        from assistance.services import record_release, void_release
        from assistance.tests import release_data
        other = self.other_selected_application()
        release = record_release(other.pk, user=self.officer, data=release_data(other))
        other.refresh_from_db()
        self.assert_receipt_serialization(lambda: void_release(other.pk, release.pk, user=self.officer,
            data={'version': other.version, 'notes': 'Synthetic G15 void', 'confirm': True}), 'release_voided')
