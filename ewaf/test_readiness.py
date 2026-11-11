from copy import deepcopy
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from assistance.models import AssistanceCase, AssistanceLog
from assistance.services import review_eligibility
from assistance.tests import review_data
from documents.services import verify_document
from programs.models import ProgramApplication, ProgramRequirement, ProgramDocument, PhotoVerification
from programs.testsupport import verified_photo
from .evidence_testsupport import EvidenceHelpers
from .readiness import assess_readiness


class ReadinessTests(EvidenceHelpers, TestCase):
    def setUp(self):
        self.setup_evidence()

    def result(self):
        return assess_readiness(self.application.pk, user=self.officer)

    def codes(self, group='eligibility'):
        return {item['code'] for item in self.result()['reasons'][group]}

    def test_current_eligibility_uses_review_not_original_member_version(self):
        original = deepcopy(self.application.source_snapshot)
        self.member.version += 1
        self.member.save()
        self.assertIn('ELIGIBILITY_STALE', self.codes())
        self.assertIn('IDENTITY_REVIEW_REQUIRED', self.codes())
        self.application.refresh_from_db()
        verified_photo(self.application)
        review_eligibility(self.application.pk, user=self.officer, data=review_data(self.application))
        self.assertTrue(self.result()['eligibility_readiness'])
        self.application.refresh_from_db()
        self.assertEqual(self.application.source_snapshot, original)

    def test_historical_verification_session_age_is_not_a_current_gate(self):
        snapshot = self.application.source_snapshot
        snapshot['membership_verified_at'] = (timezone.now() - timezone.timedelta(days=90)).isoformat()
        ProgramApplication.objects.filter(pk=self.application.pk).update(source_snapshot=snapshot)
        self.assertTrue(self.result()['eligibility_readiness'])

    def test_missing_or_forged_submission_provenance_requires_review(self):
        for source in ({}, {'member_id': 999}):
            ProgramApplication.objects.filter(pk=self.application.pk).update(source_snapshot=source)
            self.assertIn('SUBMISSION_PROVENANCE_REVIEW_REQUIRED', self.codes())

    def test_inactive_or_inconsistent_membership(self):
        self.member.is_active = False
        self.member.save()
        self.assertIn('MEMBER_INACTIVE', self.codes())
        intake = self.member.application
        intake.prpwd_verified = False
        intake.save()
        self.assertIn('MEMBERSHIP_PROVENANCE_REVIEW_REQUIRED', self.codes())

    def test_missing_disability_classification_requires_review(self):
        self.member.disability_type = None
        self.member.save()
        self.assertIn('QUALIFICATION_REVIEW_REQUIRED', self.codes())

    def test_inactive_disability_qualification_cannot_pass(self):
        # Simulate corrupted legacy reference state without invoking protected
        # reference mutation services; read-side diagnostics must still fail.
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('UPDATE members_disabilitytype SET is_active = 0 WHERE id = %s', [self.member.disability_type_id])
        self.assertIn('QUALIFICATION_FAILED', self.codes())

    def test_profile_value_drift_detected_even_without_version_change(self):
        self.assess()
        self.member.dependents += 1
        self.member.save(update_fields=['dependents'])
        self.assertIn('SOURCE_CHANGED', self.codes('criteria'))

    def test_missing_membership_audit_provenance_requires_review(self):
        self.member.application.events.filter(action='approved').update(actor=None)
        self.assertIn('MEMBERSHIP_PROVENANCE_REVIEW_REQUIRED', self.codes())

    def test_new_photo_review_and_replaced_photo_block(self):
        self.assess()
        PhotoVerification.objects.create(photo=self.application.current_photo, outcome='REJECTED',
            reason='Synthetic newer rejection', reviewer=self.officer, reviewer_label=self.officer.username,
            member_version=self.member.version)
        self.assertIn('IDENTITY_REVIEW_REQUIRED', self.codes())
        self.assertIn('SOURCE_CHANGED', self.codes('criteria'))

    def test_deleted_private_bytes_are_not_verified_evidence(self):
        self.application.current_photo.file.delete(save=False)
        self.assertIn('IDENTITY_REVIEW_REQUIRED', self.codes())

    def test_changed_document_bytes_or_review_invalidates_assessment(self):
        self.assess()
        with self.document.file.open('wb') as stream:
            stream.write(b'Synthetic replaced bytes')
        self.assertIn('SOURCE_CHANGED', self.codes('criteria'))

    def test_checklist_must_contain_every_expected_key(self):
        case = self.application.assistance_case
        case.checklist = [item for item in case.checklist if item['key'] != 'other_requirements']
        case.save()
        self.assertIn('CHECKLIST_INCOMPLETE', self.codes())

    def test_required_document_row_absence_is_detected(self):
        ProgramApplication.objects.filter(pk=self.application.pk).update(requirements_snapshot=[
            {'id': 9999, 'label': 'Synthetic missing proof', 'kind': 'document', 'is_required': True}])
        self.assertIn('REQUIRED_EVIDENCE_MISSING', self.codes())
        self.assertIn('CHECKLIST_INCOMPLETE', self.codes())

    def test_missing_answer_and_duplicate_checklist_keys(self):
        ProgramApplication.objects.filter(pk=self.application.pk).update(requirements_snapshot=[
            {'id': 9999, 'label': 'Synthetic answer', 'kind': 'text', 'is_required': True}])
        case = self.application.assistance_case
        case.checklist += [case.checklist[0]]
        case.save()
        self.assertIn('REQUIRED_EVIDENCE_MISSING', self.codes())
        self.assertIn('CHECKLIST_INCOMPLETE', self.codes())

    def test_eligibility_requires_matching_review_log(self):
        AssistanceLog.objects.filter(application=self.application, action='eligibility_reviewed').update(snapshot={})
        self.assertIn('ELIGIBILITY_STALE', self.codes())

    def test_favorable_relevance_never_overrides_ineligibility(self):
        self.assess('PR')
        AssistanceCase.objects.filter(application=self.application).update(eligibility_id='ineligible')
        self.assertIn('ELIGIBILITY_INELIGIBLE', self.codes())
        self.assertFalse(self.result()['operational_ready'])

    def test_final_application_is_diagnostic_only(self):
        from django.core.exceptions import ValidationError
        ProgramApplication.objects.filter(pk=self.application.pk).update(status='COMPLETED')
        self.assertIn('APPLICATION_NOT_CANDIDATE', self.codes())
        with self.assertRaises(ValidationError):
            self.assess()

    def test_new_policy_obsoletes_old_findings(self):
        self.assess()
        self.policy_record()
        self.assertIn('CRITERION_POLICY_CHANGED', self.codes('criteria'))

    def test_expiry_without_any_database_update(self):
        from .evidence_testsupport import synthetic_policy
        policy = self.policy_definition()
        policy['criteria']['ND'].update(observation_rule='Synthetic observation', rule_authority='Synthetic', freshness_days=1)
        self.policy = self.policy_record(policy)
        self.assess(observation_start=timezone.localdate())
        with patch('ewaf.readiness.timezone.localdate', return_value=timezone.localdate() + timezone.timedelta(days=2)):
            self.assertIn('EVIDENCE_EXPIRED', self.codes('criteria'))

    def test_supporting_document_expiry_without_row_change(self):
        self.document_review = self.verify(expires_on=timezone.localdate())
        self.assess()
        with patch('ewaf.readiness.timezone.localdate', return_value=timezone.localdate() + timezone.timedelta(days=1)):
            self.assertIn('EVIDENCE_EXPIRED', self.codes('criteria'))

    def required_reused_document(self):
        requirement = ProgramRequirement.objects.create(program=self.program, label='Synthetic required proof',
            kind='document', reusable_document_type=self.document.requirement.document_type)
        self.application.requirements_snapshot = [{'id': requirement.pk, 'label': requirement.label,
            'kind': 'document', 'is_required': True,
            'reusable_document_type_id': requirement.reusable_document_type_id}]
        self.application.save(update_fields=['requirements_snapshot'])
        document = ProgramDocument.objects.create(application=self.application, requirement=requirement,
            label='Synthetic required proof', file=self.document.file.name, content_type='application/pdf', size=50,
            source_document=self.document, source_verification=self.document_review)
        review_eligibility(self.application.pk, user=self.officer,
            data=review_data(self.application, **{f'check_{requirement.pk}': 'pass'}))
        return document

    def test_required_reused_document_current_and_revoked(self):
        self.required_reused_document()
        self.assertTrue(self.result()['eligibility_readiness'])
        self.verify(verified=False)
        self.assertIn('SOURCE_CHANGED', self.codes())

    def test_required_document_expiry_is_independent_of_assessment_expiry(self):
        self.document_review = self.verify(expires_on=timezone.localdate())
        self.required_reused_document()
        with patch('ewaf.readiness.timezone.localdate', return_value=timezone.localdate() + timezone.timedelta(days=1)):
            self.assertIn('EVIDENCE_EXPIRED', self.codes())

    def test_forged_cross_program_requirement_reference_detected(self):
        from programs.tests import create_program
        document = self.required_reused_document()
        other = create_program()
        ProgramRequirement.objects.filter(pk=document.requirement_id).update(program=other)
        self.assertIn('EVIDENCE_REFERENCE_INVALID', self.codes())

    def test_approval_context_changes_without_program_version_are_detected(self):
        from programs.binding_services import capture_terms
        from programs.terms import terms_digest, snapshot_terms
        self.assess()
        capture_terms(self.program.pk, user=self.officer, version=0, program_version=self.program.version,
            digest=terms_digest(snapshot_terms(self.program)), reason='Synthetic authority capture', confirmed=True)
        self.assertIn('SOURCE_CHANGED', self.codes('criteria'))
        self.assertIn('POLICY_TERMS_CHANGED', self.codes('governance'))
        self.program.refresh_from_db()
        self.assertEqual(self.program.version, 0)

    def test_missing_future_processing_gate_is_independent(self):
        result = self.result()
        self.assertTrue(result['eligibility_readiness'])
        self.assertEqual(result['reasons']['processing'], [{'code': 'PROCESSING_GATE_UNAVAILABLE', 'source': None}])
        self.assertFalse(result['processing_authorization_readiness'])
