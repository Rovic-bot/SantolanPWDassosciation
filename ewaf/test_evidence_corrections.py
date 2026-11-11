"""Independent review B1/B2/B3 regressions, using synthetic policy only."""
from copy import deepcopy
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from documents.models import DocumentVerification, MembershipApplicationDocument
from programs.models import ProgramApplication, ProgramDocument, ProgramRequirement, ProgramLog
from programs.tests import create_program
from .evidence import digest
from .evidence_services import record_assessment
from .evidence_testsupport import EvidenceHelpers
from .models import CriterionAssessment
from .readiness import assess_readiness


class CriterionMappingTests(EvidenceHelpers, TestCase):
    def setUp(self):
        self.setup_evidence()

    def test_current_irrelevant_document_cannot_verify_si_es_or_nd(self):
        for code in ('SI', 'ES', 'ND'):
            with self.subTest(criterion=code), self.assertRaisesMessage(ValidationError, 'CRITERION_EVIDENCE_UNSUPPORTED'):
                self.assess(code, supporting_review_ids=[self.criterion_reviews['PR'].pk])
        self.assertEqual(CriterionAssessment.objects.count(), 0)

    def test_mixed_valid_and_irrelevant_evidence_does_not_pass(self):
        with self.assertRaisesMessage(ValidationError, 'CRITERION_EVIDENCE_UNSUPPORTED'):
            self.assess(supporting_review_ids=[self.document_review.pk, self.criterion_reviews['ES'].pk])

    def test_unrecorded_mapping_allows_pending_but_not_verified(self):
        definition = self.policy_definition()
        del definition['criteria']['ND']['evidence_mappings']
        self.policy = self.policy_record(definition)
        with self.assertRaisesMessage(ValidationError, 'EVIDENCE_MAPPING_PENDING'):
            self.assess()
        self.assertEqual(self.assess(state='NEEDS_REVIEW').state, 'NEEDS_REVIEW')
        self.assertEqual(self.assess(state='DECLARED', supporting_review_ids=[]).state, 'DECLARED')

    def test_mapping_without_authority_or_with_forged_approval_is_rejected(self):
        for edit in ('missing_authority', 'client_approved'):
            definition = self.policy_definition()
            mapping = definition['criteria']['ND']['evidence_mappings']['dependent_count'][0]
            if edit == 'missing_authority':
                mapping['authority_reference'] = ''
            else:
                mapping['approved'] = True
            with self.subTest(edit=edit), self.assertRaises(ValidationError):
                self.policy_record(definition)

    def test_forged_document_type_requirement_relationship_rejected(self):
        definition = self.policy_definition()
        definition['criteria']['ND']['evidence_mappings']['dependent_count'][0]['document_type_id'] = self.mapping('SI')['document_type_id']
        before = ProgramLog.objects.count()
        with self.assertRaisesMessage(ValidationError, 'EVIDENCE_MAPPING_INVALID'):
            self.policy_record(definition)
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_alternative_si_requires_its_own_explicit_evidence_mapping(self):
        definition = self.policy_definition()
        del definition['criteria']['SI']['evidence_mappings']['socioeconomic_assessment']
        self.policy = self.policy_record(definition)
        with self.assertRaisesMessage(ValidationError, 'EVIDENCE_MAPPING_PENDING'):
            self.assess('SI', source_type='socioeconomic_assessment', value='12.5')
        self.assertEqual(self.assess('SI', source_type='socioeconomic_assessment', value='12.5', state='NEEDS_REVIEW').value, '12.5')

    def test_type_requirement_and_mapping_provenance_retained(self):
        row = self.assess()
        self.assertEqual(row.supporting_reviews[0]['document'], str(self.document.pk))
        self.assertEqual(row.supporting_reviews[0]['membership_requirement'], self.document.requirement_id)
        self.assertEqual(row.supporting_reviews[0]['document_type'], self.document.requirement.document_type_id)
        self.assertEqual(row.source_manifest['evidence_mappings'][0]['mapping_digest'], digest(self.mapping('ND')))

    def test_relevance_document_findings_require_exact_program_source(self):
        self.prepare_relevance(kind='document')
        row = self.assess('PR')
        document = self.application.documents.get(requirement=self.relevance_requirement)
        self.assertEqual(row.source_manifest['relevance']['items'][0]['source']['document'], str(document.pk))
        ProgramDocument.objects.filter(pk=document.pk).update(source_verification=self.document_review)
        with self.assertRaisesMessage(ValidationError, 'PR_EVIDENCE_INVALID'):
            self.assess('PR')


class RelevanceFindingTests(EvidenceHelpers, TestCase):
    def setUp(self):
        self.setup_evidence()
        self.prepare_relevance()

    def test_favorable_category_and_generic_description_are_insufficient(self):
        self.policy = self.policy_record(self.policy_definition())
        with self.assertRaisesMessage(ValidationError, 'PR_RUBRIC_PENDING'):
            self.assess('PR', rubric_findings=None)
        self.assertEqual(self.assess('PR', state='NEEDS_REVIEW', rubric_findings=None).state, 'NEEDS_REVIEW')

    def test_missing_duplicate_or_unknown_items_rejected(self):
        original = self.relevance_values()['rubric_findings']
        for findings in (None, [], original + original, [{**original[0], 'item_id': 'forged'}]):
            with self.subTest(findings=findings), self.assertRaises(ValidationError):
                self.assess('PR', rubric_findings=findings)

    def test_explicit_officer_attestation_required(self):
        with self.assertRaisesMessage(ValidationError, 'PR_ATTESTATION_REQUIRED'):
            self.assess('PR', rubric_attested=False)

    def test_other_program_rubric_rejected_when_recorded(self):
        definition = deepcopy(self.policy.snapshot)
        definition['criteria']['PR']['rubric_definition']['program_id'] = str(create_program().pk)
        with self.assertRaisesMessage(ValidationError, 'PR_RUBRIC_PENDING'):
            self.policy_record(definition)

    def test_other_program_requirement_rejected(self):
        definition = deepcopy(self.policy.snapshot)
        other = ProgramRequirement.objects.create(program=create_program(), kind='text', label='Other synthetic requirement')
        definition['criteria']['PR']['rubric_definition']['items'][0]['requirement_id'] = other.pk
        with self.assertRaisesMessage(ValidationError, 'PR_RUBRIC_PENDING'):
            self.policy_record(definition)

    def test_forged_irrelevant_or_missing_item_review_rejected(self):
        for ids in ([9999999], [self.document_review.pk], []):
            findings = self.relevance_values()['rubric_findings']
            findings[0]['review_ids'] = ids
            with self.subTest(ids=ids), self.assertRaises(ValidationError):
                self.assess('PR', rubric_findings=findings)

    def test_blank_explanation_or_unknown_outcome_rejected(self):
        for change in ({'explanation': ''}, {'outcome': 'arbitrary_favorable'}):
            findings = self.relevance_values()['rubric_findings']
            findings[0].update(change)
            with self.subTest(change=change), self.assertRaises(ValidationError):
                self.assess('PR', rubric_findings=findings)

    def test_stale_answer_submission_rejected(self):
        values = self.assessment_values('PR')
        ProgramApplication.objects.filter(pk=self.application.pk).update(answers={str(self.relevance_requirement.pk): 'Changed'})
        with self.assertRaisesMessage(ValidationError, 'SOURCE_CHANGED'):
            record_assessment(self.application.pk, **values)

    def test_stale_requirement_and_unbound_terms_cannot_verify(self):
        ProgramRequirement.objects.filter(pk=self.relevance_requirement.pk).update(instructions='Changed synthetic terms')
        with self.assertRaisesMessage(ValidationError, 'PR_REQUIREMENTS_STALE'):
            self.assess('PR')

    def test_no_current_approval_binding_keeps_relevance_pending(self):
        from programs.models import ProgramApprovalControl
        ProgramApprovalControl.objects.filter(program=self.program).update(active_binding=None)
        with self.assertRaisesMessage(ValidationError, 'PR_REQUIREMENTS_STALE'):
            self.assess('PR')

    def test_missing_answer_cannot_be_substituted_by_favorable_category(self):
        ProgramApplication.objects.filter(pk=self.application.pk).update(answers={})
        with self.assertRaisesMessage(ValidationError, 'PR_EVIDENCE_INVALID'):
            self.assess('PR')

    def test_complete_item_findings_retain_minimal_provenance_and_expire(self):
        row = self.assess('PR')
        relevance = row.source_manifest['relevance']
        self.assertTrue(relevance['attested'])
        self.assertEqual(relevance['rubric_version'], 1)
        self.assertEqual(relevance['items'][0]['source']['answer_digest'], digest('Synthetic supported answer'))
        self.assertNotIn('Synthetic supported answer', str(relevance))
        self.assertTrue(assess_readiness(self.application.pk, user=self.officer)['criteria'][4]['current'])
        DocumentVerification.objects.filter(pk=self.criterion_reviews['PR'].pk).update(expires_on=timezone.localdate() - timezone.timedelta(days=1))
        self.assertFalse(assess_readiness(self.application.pk, user=self.officer)['criteria'][4]['current'])


class ReusableTypeTests(EvidenceHelpers, TestCase):
    def required_reused_document(self):
        from .test_readiness import ReadinessTests
        return ReadinessTests.required_reused_document(self)

    def setUp(self):
        self.setup_evidence()

    def codes(self):
        return {item['code'] for item in assess_readiness(self.application.pk, user=self.officer)['reasons']['eligibility']}

    def test_wrong_type_despite_same_member_current_verification_and_bytes(self):
        document = self.required_reused_document()
        other = self.criterion_documents['SI']
        ProgramDocument.objects.filter(pk=document.pk).update(source_document=other,
            source_verification=self.criterion_reviews['SI'], file=other.file.name)
        self.assertIn('REUSABLE_TYPE_MISMATCH', self.codes())

    def test_mutated_current_requirement_type_does_not_override_submission(self):
        document = self.required_reused_document()
        ProgramRequirement.objects.filter(pk=document.requirement_id).update(reusable_document_type_id=self.mapping('SI')['document_type_id'])
        self.assertIn('REUSABLE_TYPE_MISMATCH', self.codes())

    def test_missing_historical_type_is_pending_and_never_backfilled(self):
        self.required_reused_document()
        snapshot = deepcopy(self.application.requirements_snapshot)
        del snapshot[0]['reusable_document_type_id']
        ProgramApplication.objects.filter(pk=self.application.pk).update(requirements_snapshot=snapshot)
        self.assertIn('REUSABLE_TYPE_DEFINITION_PENDING', self.codes())
        self.application.refresh_from_db()
        self.assertEqual(self.application.requirements_snapshot, snapshot)

    def test_verification_from_different_source_document_rejected(self):
        document = self.required_reused_document()
        ProgramDocument.objects.filter(pk=document.pk).update(source_verification=self.criterion_reviews['SI'])
        self.assertIn('SOURCE_CHANGED', self.codes())

    def test_changed_source_bytes_detected_even_if_program_copy_is_unchanged(self):
        document = self.required_reused_document()
        from membership.tests import pdf
        document.file.save('synthetic-distinct-copy.pdf', pdf(), save=True)
        with self.document.file.open('wb') as stream:
            stream.write(b'Synthetic tampered original')
        self.assertIn('SOURCE_CHANGED', self.codes())

    def test_changed_source_membership_requirement_is_detected(self):
        self.required_reused_document()
        replacement = self.criterion_documents['SI']
        # Remove the unused same-intake row first to preserve its unique constraint.
        from members.tests import create_member
        MembershipApplicationDocument.objects.filter(pk=replacement.pk).update(application=create_member('SYNTHETIC-TYPE').application)
        MembershipApplicationDocument.objects.filter(pk=self.document.pk).update(requirement=replacement.requirement)
        self.assertIn('REUSABLE_TYPE_MISMATCH', self.codes())
