from copy import deepcopy
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from membership.tests import grant
from programs.models import ProgramLog, ProgramTermsLock
from .evidence import CRITERIA, VIEW, digest, reviewed_value
from .evidence_testsupport import EvidenceHelpers, synthetic_policy
from .evidence_services import record_assessment, record_readiness
from .models import CriterionAssessment, EvidencePolicyRevision, EligibilityReadinessSnapshot
from .readiness import assess_readiness, require_operational_evidence


class EvidenceTests(EvidenceHelpers, TestCase):
    def setUp(self):
        self.setup_evidence()

    def test_five_findings_keep_order_values_provenance_and_no_approval(self):
        self.prepare_relevance()
        for criterion in CRITERIA:
            row = self.assess(criterion)
            self.assertEqual(row.actor, self.officer)
            self.assertEqual(row.source_digest, digest(row.source_manifest))
            self.assertEqual(row.digest, digest(row.payload()))
            self.assertEqual(row.audit_entry.application, self.application)
        result = assess_readiness(self.application.pk, user=self.officer)
        self.assertTrue(result['criterion_completeness'])
        self.assertTrue(result['eligibility_readiness'])
        self.assertFalse(result['governance_readiness'])
        self.assertFalse(result['operational_ready'])
        self.assertEqual([row['criterion'] for row in result['criteria']], list(CRITERIA))

    def test_zero_is_explicit_and_missing_assessment_is_not_zero(self):
        self.member.dependents = 0
        self.member.save()
        row = self.assess()
        self.assertEqual(row.value, 0)
        result = assess_readiness(self.application.pk, user=self.officer)
        self.assertEqual(result['criteria'][0]['state'], 'MISSING')
        self.assertTrue(result['criteria'][3]['current'])

    def test_declaration_does_not_verify_profile_or_4ps(self):
        row = self.assess('SI', state='DECLARED', supporting_review_ids=[])
        self.assertEqual(row.state, 'DECLARED')
        self.assertFalse(assess_readiness(self.application.pk, user=self.officer)['criterion_completeness'])
        with self.assertRaises(ValidationError):
            self.assess('SI', source_type='government_status', value='4Ps')

    def test_verification_requires_supporting_review(self):
        for criterion in ('SI', 'ES', 'ND'):
            with self.subTest(criterion=criterion), self.assertRaises(ValidationError):
                self.assess(criterion, supporting_review_ids=[])

    def test_rejection_and_dispute_never_fall_back(self):
        first = self.assess()
        second = self.assess(state='REJECTED', disputed=True)
        self.assertEqual(second.previous, first)
        row = assess_readiness(self.application.pk, user=self.officer)['criteria'][3]
        self.assertEqual(row['assessment'], second.pk)
        self.assertFalse(row['current'])
        self.assertEqual(CriterionAssessment.objects.get(pk=first.pk).state, 'VERIFIED')

    def test_disputed_verified_finding_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.assess(disputed=True)

    def test_stale_revision_and_context_rejected(self):
        values = self.assessment_values()
        self.assess()
        with self.assertRaises(ValidationError):
            record_assessment(self.application.pk, **values)
        with self.assertRaises(ValidationError):
            self.assess(expected_context='forged digest')

    def test_latest_supporting_review_identity_checked_without_member_bump(self):
        values = self.assessment_values()
        self.verify(verified=False)
        self.member.refresh_from_db()
        self.assertEqual(self.member.version, 0)
        with self.assertRaises(ValidationError):
            record_assessment(self.application.pk, **values)
        with self.assertRaises(ValidationError):
            self.assess()

    def test_expired_supporting_review_rejected(self):
        from documents.models import DocumentVerification
        DocumentVerification.objects.filter(pk=self.document_review.pk).update(expires_on=timezone.localdate() - timezone.timedelta(days=1))
        with self.assertRaises(ValidationError):
            self.assess()

    def test_unrelated_policy_and_document_reviews_rejected(self):
        from members.tests import create_member
        from documents.models import DocumentVerification
        other = create_member('OTHER-G12')
        self.document.application = other.application
        self.document.save()
        with self.assertRaises(ValidationError):
            self.assess()
        with self.assertRaises(ValidationError):
            self.assess(policy_id=999999)

    def test_no_forged_actor_timestamp_or_digest_parameters(self):
        for key in ('actor', 'reviewer', 'recorded_at', 'source_digest', 'approved'):
            with self.subTest(key=key), self.assertRaises(TypeError):
                record_assessment(self.application.pk, **{**self.assessment_values(), key: 'forged'})

    def test_mismatched_audit_association_detected(self):
        row = self.assess()
        row.audit_entry = self.policy.audit_entry
        with self.assertRaises(ValidationError):
            row.full_clean()

    def test_tampered_audit_is_not_a_current_verified_finding(self):
        row = self.assess()
        ProgramLog.objects.filter(pk=row.audit_entry_id).update(application=None)
        codes = {reason['code'] for reason in assess_readiness(self.application.pk, user=self.officer)['reasons']['criteria']}
        self.assertIn('ARTIFACT_INTEGRITY_FAILED', codes)

    def test_general_program_audit_does_not_duplicate_private_findings(self):
        row = self.assess(reason='Synthetic confidential economic explanation')
        self.assertNotIn('confidential', row.audit_entry.notes)
        self.assertNotIn('confidential', str(row.audit_entry.changes))

    def test_append_only_supported_paths(self):
        row = self.assess()
        for artifact in (row, self.policy):
            model = type(artifact)
            for action in (lambda: artifact.save(), lambda: artifact.delete(),
                           lambda: model.objects.filter(pk=artifact.pk).update(reason='overwrite'),
                           lambda: model.objects.all().delete(),
                           lambda: model.objects.bulk_update([artifact], ['reason']),
                           lambda: model.objects.bulk_create([artifact], update_conflicts=True, update_fields=['reason']),
                           lambda: model.objects.create(**{f.attname: getattr(artifact, f.attname) for f in artifact._meta.fields})):
                with self.assertRaises(ValidationError):
                    action()

    def test_audit_failure_rolls_back_all_artifacts(self):
        before = ProgramLog.objects.count()
        with patch('ewaf.evidence_services.ProgramLog.objects.create', side_effect=RuntimeError('audit failure')):
            with self.assertRaises(RuntimeError):
                self.assess()
        self.assertEqual(CriterionAssessment.objects.count(), 0)
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_artifact_failure_rolls_back_audit(self):
        before = ProgramLog.objects.count()
        with patch('ewaf.models.CriterionAssessment.save', side_effect=RuntimeError('insert failure')):
            with self.assertRaises(RuntimeError):
                self.assess()
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_policy_failure_and_revisions_preserve_program(self):
        from programs.models import Program
        before = Program.objects.values().get(pk=self.program.pk)
        second = self.policy_record()
        self.assertEqual(second.revision, 2)
        self.assertEqual(Program.objects.values().get(pk=self.program.pk), before)
        with self.assertRaises(ValidationError):
            self.assess()
        with patch('ewaf.models.EvidencePolicyRevision.save', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                self.policy_record()
        self.assertEqual(EvidencePolicyRevision.objects.count(), 2)

    def test_policy_rejects_scoring_defaults_or_numerical_categories(self):
        for edit in ('weights', 'approved', 'categories'):
            definition = self.policy_definition()
            if edit == 'categories':
                definition['criteria']['ES']['categories'] = {'employed': 5}
            else:
                definition[edit] = True
            with self.subTest(edit=edit), self.assertRaises(ValidationError):
                self.policy_record(definition)

    def test_unknown_category_and_invalid_numbers_rejected(self):
        for value in ('NaN', 'Infinity', '-1', '0.00001'):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.assess('SI', source_type='socioeconomic_assessment', value=value)
        with self.assertRaises(ValidationError):
            self.assess('ES', source_type='employment_category', value='unapproved')
        for value in ('-1', '1.5', True):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                reviewed_value(self.application, 'ND', 'dependent_count', value, self.policy.snapshot['criteria']['ND'])

    def test_employment_original_text_preserved_with_category(self):
        row = self.assess('ES', source_type='employment_category', value='test_category')
        self.assertEqual(row.source_manifest['original_value'], self.member.employment_information)
        self.assertEqual(row.value_type, 'category')

    def test_unknown_pa_scope_only_allows_pending_diagnostics(self):
        policy = self.policy_definition()
        del policy['criteria']['PA']['pa_scope']
        self.policy = self.policy_record(policy)
        with self.assertRaises(ValidationError):
            self.assess('PA')
        self.assertEqual(self.assess('PA', state='NEEDS_REVIEW').value, 0)

    def test_observation_and_freshness_require_documented_authority(self):
        with self.assertRaises(ValidationError):
            self.assess(observation_start=timezone.localdate())
        definition = self.policy_definition()
        definition['criteria']['ND'].update(observation_rule='Synthetic date basis', freshness_days=5,
                                            rule_authority='Synthetic test authority')
        self.policy = self.policy_record(definition)
        row = self.assess(observation_start=timezone.localdate())
        self.assertEqual(row.expires_on, timezone.localdate() + timezone.timedelta(days=5))

    def test_diagnostic_snapshot_and_operational_gate(self):
        result = assess_readiness(self.application.pk, user=self.officer)
        values = dict(user=self.officer, expected_context=result['context_digest'],
            expected_assessments={row['criterion']: row['assessment'] for row in result['criteria']},
            reason='Synthetic diagnostic retained', confirmed=True)
        snapshot = record_readiness(self.application.pk, **values)
        self.assertFalse(snapshot.result['operational_ready'])
        with self.assertRaisesMessage(ValidationError, 'PROCESSING_GATE_UNAVAILABLE'):
            require_operational_evidence(snapshot)
        self.assess()
        with self.assertRaises(ValidationError):
            record_readiness(self.application.pk, **values)

    def test_snapshot_failure_rolls_back_audit(self):
        result = assess_readiness(self.application.pk, user=self.officer)
        before = ProgramLog.objects.count()
        with patch('ewaf.models.EligibilityReadinessSnapshot.save', side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):
                record_readiness(self.application.pk, user=self.officer, expected_context=result['context_digest'],
                    expected_assessments={row['criterion']: row['assessment'] for row in result['criteria']}, reason='Synthetic', confirmed=True)
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_private_views_get_is_read_only_and_existing_program_history_renders(self):
        self.assess()
        ProgramTermsLock.objects.all().delete()
        self.client.force_login(self.officer)
        before = (ProgramLog.objects.count(), ProgramTermsLock.objects.count(), CriterionAssessment.objects.count(), EligibilityReadinessSnapshot.objects.count())
        routes = [reverse('ewaf:evidence_queue'), reverse('ewaf:evidence_readiness', args=[self.application.pk]),
            reverse('ewaf:evidence_history', args=[self.application.pk]),
            reverse('ewaf:evidence_review', args=[self.application.pk, 'ND']),
            reverse('ewaf:evidence_policy', args=[self.program.pk]), reverse('programs:manage_detail', args=[self.program.pk])]
        for route in routes:
            with self.subTest(route=route):
                response = self.client.get(route)
                self.assertEqual(response.status_code, 200)
                self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(before, (ProgramLog.objects.count(), ProgramTermsLock.objects.count(), CriterionAssessment.objects.count(), EligibilityReadinessSnapshot.objects.count()))

    def test_permissions_no_automatic_staff_grants_and_service_enforcement(self):
        viewer = get_user_model().objects.create_user('g12_viewer', is_staff=True)
        self.assertFalse(viewer.has_perm('ewaf.review_criterionassessment'))
        for user in (viewer, AnonymousUser()):
            with self.assertRaises(PermissionDenied):
                self.assess(user=user)
        grant(viewer, 'accounts.access_dashboard', *VIEW)
        viewer = get_user_model().objects.get(pk=viewer.pk)
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(reverse('ewaf:evidence_readiness', args=[self.application.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('ewaf:evidence_review', args=[self.application.pk, 'ND'])).status_code, 403)
        self.assertEqual(self.client.post(reverse('ewaf:evidence_readiness', args=[self.application.pk]), {}).status_code, 403)

    def test_csrf_and_anonymous_access(self):
        route = reverse('ewaf:evidence_review', args=[self.application.pk, 'ND'])
        self.assertEqual(Client().get(route).status_code, 302)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.officer)
        self.assertEqual(client.post(route, {}).status_code, 403)
        self.assertEqual(client.put(route, {}).status_code, 403)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.put(route, {}).status_code, 405)

    def test_inactive_and_nonstaff_cannot_access_evidence_even_with_permissions(self):
        for name, active, staff in [('inactive', False, True), ('nonstaff', True, False)]:
            user = get_user_model().objects.create_user('g12_' + name, is_active=active, is_staff=staff)
            grant(user, 'accounts.access_dashboard', *VIEW, 'ewaf.review_criterionassessment')
            with self.assertRaises(PermissionDenied):
                self.assess(user=user)

    def test_post_forged_metadata_cannot_replace_server_actor_or_digest(self):
        self.client.force_login(self.officer)
        values = self.assessment_values()
        values.pop('user')
        values.pop('criterion')
        values.update(value='', supporting_review_ids=str(self.document_review.pk),
                      reviewer='999999', actor='999999', source_digest='forged', approved='true')
        response = self.client.post(reverse('ewaf:evidence_review', args=[self.application.pk, 'ND']), values)
        self.assertEqual(response.status_code, 302)
        row = CriterionAssessment.objects.get()
        self.assertEqual(row.actor, self.officer)
        self.assertEqual(row.source_digest, digest(row.source_manifest))

    def test_retired_services_stay_disabled(self):
        from .services import save_configuration, save_input, generate_ranking, current_ranking, require_ranked
        for action in (lambda: save_configuration(user=self.officer, data={}),
                       lambda: save_input(self.application.pk, user=self.officer, data={}),
                       lambda: generate_ranking(self.program.pk, user=self.officer, configuration=None, version=0),
                       lambda: current_ranking(self.program), lambda: require_ranked(self.application, self.program)):
            with self.assertRaises(ValidationError):
                action()
