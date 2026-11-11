"""Real MySQL transactions exercise shared-member serialization across programs."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from threading import Barrier, Event
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from django.utils import timezone
from assistance.services import review_eligibility, decide_assistance, record_release, void_release
from assistance.tests import review_data, decision_data, release_data
from programs.tests import create_program
from programs.testsupport import application_fixture
from members.services import change_status
from .evidence_testsupport import EvidenceHelpers
from .evidence_services import record_assessment
from .models import CriterionAssessment
from .readiness import assess_readiness


def worker(action):
    close_old_connections()
    try:
        try:
            return action()
        except ValidationError:
            return False
    finally:
        connections.close_all()


class EvidenceConcurrencyTests(EvidenceHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_evidence()

    def race(self, first, second):
        barrier = Barrier(2)
        def start(action):
            barrier.wait(timeout=10)
            return action()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, lambda action=action: start(action)) for action in (first, second)]
            return [future.result(timeout=30) for future in futures]

    def test_two_reviews_same_displayed_revision_only_one_commits(self):
        values = self.assessment_values()
        results = self.race(lambda: record_assessment(self.application.pk, **values),
                            lambda: record_assessment(self.application.pk, **values))
        self.assertEqual(sum(result is not False for result in results), 1)
        self.assertEqual(CriterionAssessment.objects.count(), 1)

    def assert_changed_race(self, mutation):
        values = self.assessment_values()
        results = self.race(lambda: record_assessment(self.application.pk, **values), mutation)
        self.assertIsNot(results[1], False)
        if results[0] is not False:
            finding = assess_readiness(self.application.pk, user=self.officer)['criteria'][3]
            self.assertFalse(finding['current'])

    def test_member_status_correction_race(self):
        self.assert_changed_race(lambda: change_status(self.member.pk, user=self.officer,
            version=self.member.version, status='inactive', notes='Synthetic race'))

    def test_document_revocation_race_without_member_version_change(self):
        self.assert_changed_race(lambda: self.verify(verified=False))

    def test_eligibility_review_race(self):
        data = review_data(self.application)
        self.assert_changed_race(lambda: review_eligibility(self.application.pk, user=self.officer, data=data))

    def test_terms_capture_race_without_program_version_change(self):
        from programs.binding_services import capture_terms
        from programs.terms import terms_digest, snapshot_terms
        self.assert_changed_race(lambda: capture_terms(self.program.pk, user=self.officer, version=0,
            program_version=self.program.version, digest=terms_digest(snapshot_terms(self.program)),
            reason='Synthetic terms capture', confirmed=True))

    def other_selected_application(self):
        program = create_program(registration_closes_at=timezone.now() - timezone.timedelta(minutes=1))
        application = application_fixture(program, self.member)
        review_eligibility(application.pk, user=self.officer, data=review_data(application))
        decide_assistance(application.pk, user=self.officer, data=decision_data(application))
        application.refresh_from_db()
        return application

    def assert_pa_writer_serialization(self, mutation, action_name):
        """Hold a release/void transaction after its write, before commit. Capture
        must block on the same Member row and reject its old source digest."""
        from assistance.services import record_log as actual_log
        entered, resume, capture_started = Event(), Event(), Event()
        values = self.assessment_values('PA')
        def held_log(application, user, action, *args, **kwargs):
            result = actual_log(application, user, action, *args, **kwargs)
            if action == action_name:
                entered.set()
                if not resume.wait(timeout=15):
                    raise RuntimeError('Synthetic writer coordination timeout')
            return result
        def capture():
            capture_started.set()
            return record_assessment(self.application.pk, **values)
        with patch('assistance.services.record_log', side_effect=held_log), ThreadPoolExecutor(max_workers=2) as pool:
            writing = pool.submit(worker, mutation)
            try:
                self.assertTrue(entered.wait(timeout=10))
                capturing = pool.submit(worker, capture)
                self.assertTrue(capture_started.wait(timeout=10))
                with self.assertRaises(FutureTimeout):
                    capturing.result(timeout=.25)
            finally:
                resume.set()
            self.assertIsNot(writing.result(timeout=15), False)
            self.assertIs(capturing.result(timeout=15), False)
        self.assertFalse(CriterionAssessment.objects.filter(criterion='PA').exists())

    def test_new_cross_program_release_serializes_empty_pa_capture(self):
        other = self.other_selected_application()
        data = release_data(other)
        self.assert_pa_writer_serialization(lambda: record_release(other.pk, user=self.officer, data=data), 'assistance_released')

    def test_cross_program_void_serializes_pa_capture(self):
        other = self.other_selected_application()
        release = record_release(other.pk, user=self.officer, data=release_data(other))
        other.refresh_from_db()
        data = {'version': other.version, 'notes': 'Synthetic correction void', 'confirm': True}
        self.assert_pa_writer_serialization(lambda: void_release(other.pk, release.pk, user=self.officer, data=data), 'release_voided')

    def test_later_release_invalidates_previously_current_pa_capture(self):
        first = self.assess('PA')
        other = self.other_selected_application()
        record_release(other.pk, user=self.officer, data=release_data(other))
        finding = assess_readiness(self.application.pk, user=self.officer)['criteria'][2]
        self.assertEqual(finding['assessment'], first.pk)
        self.assertFalse(finding['current'])

    def test_unreleased_void_and_replacement_count_only_successful_receipts(self):
        other = self.other_selected_application()
        self.assertEqual(self.assess('PA').value, 0)
        release = record_release(other.pk, user=self.officer, data=release_data(other))
        self.assertEqual(self.assess('PA').value, 1)
        other.refresh_from_db()
        void_release(other.pk, release.pk, user=self.officer,
            data={'version': other.version, 'notes': 'Synthetic void', 'confirm': True})
        self.assertEqual(self.assess('PA').value, 0)
        review_eligibility(other.pk, user=self.officer, data=review_data(other))
        decide_assistance(other.pk, user=self.officer, data=decision_data(other))
        replacement = record_release(other.pk, user=self.officer, data=release_data(other))
        finding = self.assess('PA')
        self.assertEqual(finding.value, 1)
        self.assertEqual([row['id'] for row in finding.source_manifest['context']['pa']['successful']], [str(replacement.pk)])
