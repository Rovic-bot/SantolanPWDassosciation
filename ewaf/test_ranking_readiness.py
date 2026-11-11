from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from .scoring_testsupport import ScoringHelpers
from .scoring_inputs import READINESS_VIEW
from .ranking_diagnostics import BARRIERS
from .ranking_readiness import ranking_readiness, require_operational_ranking


class RankingReadinessTests(ScoringHelpers, ConfigurationHelpers, EvidenceHelpers, TestCase):
    def setUp(self):
        self.setup_scoring()

    def ready(self, **changes):
        return ranking_readiness(self.application.pk, **{'user': self.officer,
                                 'program_id': self.program.pk, **changes})

    def test_permission_checks_precede_private_reads(self):
        with self.assertNumQueries(0), self.assertRaises(PermissionDenied):
            self.ready(user=AnonymousUser())
        user = get_user_model().objects.create_user('g16_restricted', is_staff=True)
        with self.assertRaises(PermissionDenied):
            self.ready(user=user)
        user.user_permissions.set(Permission.objects.filter(codename__in=[
            p.split('.')[1] for p in (*READINESS_VIEW, 'accounts.access_dashboard')]))
        user = get_user_model().objects.get(pk=user.pk)
        self.assertEqual(self.ready(user=user)['mode'], 'READINESS_ONLY')
        user.user_permissions.remove(Permission.objects.get(content_type__app_label='ewaf', codename='view_criterionassessment'))
        with self.assertRaises(PermissionDenied):
            self.ready(user=get_user_model().objects.get(pk=user.pk))

    def test_nonstaff_and_inactive_users_denied(self):
        for field in ('is_staff', 'is_active'):
            setattr(self.officer, field, False)
            with self.assertRaises(PermissionDenied):
                self.ready()
            setattr(self.officer, field, True)

    def test_cross_program_reference_denied(self):
        from programs.tests import create_program
        other = create_program()
        with self.assertRaises(ValidationError):
            self.ready(program_id=other.pk)

    def test_missing_and_verified_zero_are_score_free(self):
        self.assertIsNone(self.ready()['readiness']['criteria'][3]['assessment'])
        row = self.assess('ND')
        result = self.ready()['readiness']
        self.assertEqual(row.value, 0)
        self.assertTrue(result['criteria'][3]['current'])
        self.assertEqual(result['criteria'][3]['assessment'], row.pk)
        for key in ('value', 'weight', 'score_0_1', 'score_0_100', 'contribution', 'groups', 'rank', 'position_start'):
            self.assertNotIn("'" + key + "':", str(result))

    def test_latest_rejected_disputed_never_falls_back(self):
        self.assess('ND')
        latest = self.assess('ND', state='REJECTED', disputed=True)
        result = self.ready()['readiness']
        self.assertEqual(result['criteria'][3]['assessment'], latest.pk)
        self.assertFalse(result['criteria'][3]['current'])
        self.assertTrue({'CRITERION_REJECTED', 'EVIDENCE_DISPUTED'} <= {r['code'] for r in result['reasons']})

    def test_expired_revoked_and_changed_sources_rechecked(self):
        today = timezone.localdate()
        self.document_review = self.verify(expires_on=today)
        self.assess('ND')
        with patch('django.utils.timezone.localdate', return_value=today + timedelta(days=1)):
            result = self.ready()['readiness']
            self.assertFalse(result['criteria'][3]['current'])
            self.assertIn('EVIDENCE_EXPIRED', {r['code'] for r in result['reasons']})
        self.verify(verified=False)
        self.assertFalse(self.ready()['readiness']['criteria'][3]['current'])
        self.member.version += 1
        self.member.save(update_fields=['version'])
        self.assertFalse(self.ready()['readiness']['eligibility_ready'])

    def test_b1_unrelated_evidence_rejected(self):
        with self.assertRaises(ValidationError):
            self.assess('SI', supporting_review_ids=[self.criterion_reviews['ND'].pk])
        self.assertFalse(self.ready()['readiness']['criteria'][0]['current'])

    def test_b2_missing_structured_findings_or_attestation_rejected(self):
        self.prepare_relevance()
        for changes in ({'rubric_findings': []}, {'rubric_attested': False}):
            with self.assertRaises(ValidationError):
                self.assess('PR', **changes)
        self.assertFalse(self.ready()['readiness']['criteria'][4]['current'])

    def test_b3_exact_reusable_type_required(self):
        self.prepare_relevance(kind='document')
        self.assess('PR')
        self.relevance_requirement.reusable_document_type = self.criterion_documents['ND'].requirement.document_type
        self.relevance_requirement.save(update_fields=['reusable_document_type'])
        result = self.ready()['readiness']
        self.assertFalse(result['eligibility_ready'])
        self.assertFalse(result['criteria'][4]['current'])

    def test_all_verified_still_no_ranking_or_mathematics(self):
        self.prepare_relevance()
        self.draft()
        self.validate()
        self.propose()
        for code in ('SI', 'ES', 'PA', 'ND', 'PR'):
            self.assess(code)
        result = self.ready()
        self.assertTrue(result['readiness']['evidence_complete'])
        self.assertTrue(result['readiness']['eligibility_ready'])
        self.assertTrue(result['readiness']['weight_evidence_complete'])
        self.assertEqual(result['readiness']['mathematical_readiness'], 'UNAVAILABLE_FOR_APPLICANTS')
        self.assertFalse(result['operational_ready'])
        self.assertTrue(set(BARRIERS) <= set(result['ranking_policy']['reasons']))

    def test_adapter_rejects_unexpected_numerical_payload(self):
        forged = self.ready()['readiness']
        forged['score_0_1'] = '0.8'
        with patch('ewaf.ranking_readiness.applicant_readiness', return_value=forged):
            with self.assertRaises(ValidationError):
                self.ready()

    def test_new_ranking_and_existing_operational_guards_unconditional(self):
        from .readiness import require_operational_evidence
        from .configuration_services import require_configuration_authorization
        from .scoring_readiness import require_operational_scoring
        for guard, code in ((require_operational_ranking, 'OPERATIONAL_RANKING_UNAVAILABLE'),
                            (require_operational_evidence, 'PROCESSING_GATE_UNAVAILABLE'),
                            (require_configuration_authorization, 'CONFIGURATION_AUTHORIZATION_UNAVAILABLE'),
                            (require_operational_scoring, 'OPERATIONAL_SCORING_UNAVAILABLE')):
            with self.assertRaises(ValidationError) as error:
                guard(approved=True, user=self.officer, complete=True)
            self.assertEqual(error.exception.code, code)
