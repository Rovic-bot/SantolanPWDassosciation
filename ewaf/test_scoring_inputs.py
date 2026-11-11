from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from .scoring_testsupport import ScoringHelpers
from .scoring_inputs import weight_evidence
from .evidence_services import record_assessment


class ScoringInputTests(ScoringHelpers, ConfigurationHelpers, EvidenceHelpers, TestCase):
    def setUp(self):
        self.setup_scoring()

    def codes(self):
        return {row['code'] for row in self.diagnostic()['reasons']}

    def test_current_verified_zero_is_distinct_from_missing(self):
        self.assertIn('CRITERION_MISSING', self.codes())
        row = self.assess('ND')
        result = self.diagnostic()['criteria'][3]
        self.assertEqual(row.value, 0)
        self.assertEqual(result['assessment'], row.pk)
        self.assertTrue(result['current'])

    def test_latest_rejected_and_disputed_never_falls_back(self):
        old = self.assess('ND')
        latest = self.assess('ND', state='REJECTED', disputed=True)
        result = self.diagnostic()
        self.assertEqual(result['criteria'][3]['assessment'], latest.pk)
        self.assertFalse(result['criteria'][3]['current'])
        self.assertNotEqual(old.pk, latest.pk)
        self.assertIn('EVIDENCE_DISPUTED', self.codes())
        self.assertIn('CRITERION_REJECTED', self.codes())

    def test_revoked_supporting_document_and_stale_member(self):
        self.assess('ND')
        self.verify(verified=False)
        self.assertIn('SOURCE_CHANGED', self.codes())
        self.member.version += 1
        self.member.save(update_fields=['version'])
        self.assertFalse(self.diagnostic()['criteria'][3]['current'])

    def test_expiry_without_version_change_and_midnight_token(self):
        today = timezone.localdate()
        self.document_review = self.verify(expires_on=today)
        self.assess('ND')
        token = self.diagnostic()['context_digest']
        with patch('django.utils.timezone.localdate', return_value=today + timedelta(days=1)):
            self.assertIn('EVIDENCE_EXPIRED', self.codes())
            with self.assertRaises(ValidationError):
                self.capture_diagnostic(expected_context=token)

    def test_b1_unrelated_supporting_evidence_cannot_become_current(self):
        with self.assertRaises(ValidationError):
            self.assess('SI', supporting_review_ids=[self.criterion_reviews['ND'].pk])
        self.assertFalse(self.diagnostic()['criteria'][0]['current'])

    def test_b2_generic_relevance_and_no_attestation_blocked(self):
        values = self.assessment_values('PR')
        for changes in ({'rubric_findings': []}, {'rubric_attested': False}):
            with self.assertRaises(ValidationError):
                record_assessment(self.application.pk, **{**values, **changes})
        self.assertFalse(self.diagnostic()['criteria'][4]['current'])

    def test_b3_reusable_type_mismatch_blocks_readiness(self):
        self.prepare_relevance(kind='document')
        self.assess('PR')
        requirement = self.relevance_requirement
        requirement.reusable_document_type = self.criterion_documents['ND'].requirement.document_type
        requirement.save(update_fields=['reusable_document_type'])
        self.assertFalse(self.diagnostic()['eligibility_ready'])
        self.assertFalse(self.diagnostic()['criteria'][4]['current'])

    def test_exact_weight_replay_and_tampering_rejected(self):
        self.assertEqual(set(weight_evidence(self.scoring_policy, user=self.officer)), {'SI', 'ES', 'PA', 'ND', 'PR'})
        self.scoring_policy.validation_digest = '0' * 64
        with self.assertRaises(ValidationError):
            weight_evidence(self.scoring_policy, user=self.officer)

    def test_new_assessment_invalidates_capture_token(self):
        token = self.diagnostic()['context_digest']
        self.assess('ND')
        with self.assertRaises(ValidationError):
            self.capture_diagnostic(expected_context=token)

    def test_all_five_verified_inputs_still_have_no_applicant_mathematics(self):
        self.prepare_relevance()
        self.draft()
        self.validate()
        self.propose()
        for code in ('SI', 'ES', 'PA', 'ND', 'PR'):
            self.assess(code)
        result = self.diagnostic()
        self.assertTrue(result['evidence_complete'])
        self.assertTrue(result['eligibility_ready'])
        self.assertTrue(result['weight_evidence_complete'])
        self.assertEqual(result['mathematical_readiness'], 'UNAVAILABLE_FOR_APPLICANTS')
        self.assertNotIn('score_0_1', result)
        run = self.capture_diagnostic()
        self.assertEqual(run.items.first().traces.count(), 5)
