"""Synthetic G12 fixtures; these definitions are never seeded as Association policy."""
from django.contrib.auth import get_user_model
from django.utils import timezone
from assistance.tests import seed_statuses, review_data
from assistance.services import review_eligibility
from documents.models import DocumentType, MembershipDocumentRequirement, MembershipApplicationDocument
from documents.services import verify_document
from membership.tests import pdf
from programs.tests import create_program
from programs.testsupport import application_fixture, private_media
from members.tests import create_member
from .evidence import source_context, digest, approval_context
from .evidence_services import record_policy, record_assessment
from .models import CriterionAssessment, EvidencePolicyRevision


def synthetic_policy():
    return {'criteria': {
        'SI': {'definition': 'Synthetic individual income review', 'source_types': ['monthly_income', 'socioeconomic_assessment', 'government_status'], 'unit': 'PHP/month'},
        'ES': {'definition': 'Synthetic employment review', 'source_types': ['employment_text', 'employment_category'],
               'categories': {'test_category': 'Synthetic documented employment category'}, 'rule_authority': 'Synthetic test authority'},
        'PA': {'definition': 'Synthetic recorded assistance review', 'source_types': ['successful_releases'],
               'pa_scope': 'all_retained_successful_releases', 'rule_authority': 'Synthetic scope for tests only', 'unit': 'records'},
        'ND': {'definition': 'Synthetic dependent count', 'source_types': ['dependent_count'], 'unit': 'persons'},
        'PR': {'definition': 'Synthetic program relevance', 'source_types': ['program_relevance'],
               'categories': {'relevant': 'Requirements supported by current evidence'},
               'rubric': 'Synthetic relevance evidence review', 'rule_authority': 'Synthetic rubric authority'},
    }}


class EvidenceHelpers:
    def setup_evidence(self):
        private_media(self)
        seed_statuses()
        self.officer = get_user_model().objects.create_superuser('synthetic_g12_officer')
        self.program = create_program(ewaf_applicable=True)
        self.member = create_member('SYNTHETIC-G12')
        intake = self.member.application
        intake.prpwd_verified_by = self.officer
        intake.decided_by = self.officer
        intake.save()
        from membership.services import record_event
        record_event(intake, 'prpwd_verified', 'Synthetic manual verification', user=self.officer)
        record_event(intake, 'approved', 'Synthetic approved intake', user=self.officer)
        self.application = application_fixture(self.program, self.member)
        self.application.source_snapshot = {'member_id': self.member.pk, 'member_version': self.member.version,
            'program_version': self.program.version, 'membership_verified_at': timezone.now().isoformat(),
            'policy_authorized_at': self.program.policy_authorized_at.isoformat()}
        self.application.save(update_fields=['source_snapshot'])
        review_eligibility(self.application.pk, user=self.officer, data=review_data(self.application))
        self.application.refresh_from_db()
        self.criterion_documents, self.criterion_reviews = {}, {}
        for code in ('SI', 'ES', 'ND', 'PR'):
            kind = DocumentType.objects.create(name=f'Synthetic {code} evidence')
            requirement = MembershipDocumentRequirement.objects.create(document_type=kind)
            document = MembershipApplicationDocument.objects.create(application=intake, requirement=requirement,
                label=f'Synthetic {code} evidence', file=pdf(), content_type='application/pdf', size=50)
            self.criterion_documents[code] = document
            self.criterion_reviews[code] = verify_document(document.pk, user=self.officer,
                member_version=self.member.version, verified=True, expires_on=None, reason=f'Synthetic {code} review')
        self.document = self.criterion_documents['ND']
        self.document_review = self.criterion_reviews['ND']
        self.policy = self.policy_record()

    def mapping(self, criterion):
        requirement = self.criterion_documents[criterion].requirement
        return {'document_type_id': requirement.document_type_id, 'membership_requirement_id': requirement.pk,
                'basis': f'Synthetic {criterion} source substantiation', 'authority_reference': f'Synthetic {criterion} authority'}

    def policy_definition(self):
        snapshot = synthetic_policy()
        for code in ('SI', 'ES', 'ND'):
            snapshot['criteria'][code]['evidence_mappings'] = {
                source: [self.mapping(code)] for source in snapshot['criteria'][code]['source_types'] if source != 'government_status'}
        return snapshot

    def prepare_relevance(self, kind='text'):
        from programs.models import ProgramRequirement, ProgramDocument
        from programs.forms import snapshot
        from programs.test_approved_terms import TermsHelpers
        from programs.terms import snapshot_terms, terms_digest
        self.relevance_requirement = ProgramRequirement.objects.create(program=self.program,
            label='Synthetic relevance question', kind=kind, instructions='Synthetic documented test requirement',
            reusable_document_type=self.criterion_documents['PR'].requirement.document_type if kind == 'document' else None)
        if kind == 'document':
            source = self.criterion_documents['PR']
            ProgramDocument.objects.create(application=self.application, requirement=self.relevance_requirement,
                label='Synthetic relevance evidence', file=source.file.name, content_type='application/pdf', size=50,
                source_document=source, source_verification=self.criterion_reviews['PR'])
        self.application.requirements_snapshot = snapshot(self.program)
        self.application.answers = {str(self.relevance_requirement.pk): 'Synthetic supported answer'}
        self.application.save(update_fields=['requirements_snapshot', 'answers'])
        review_eligibility(self.application.pk, user=self.officer,
            data=review_data(self.application, **{f'check_{self.relevance_requirement.pk}': 'pass'}))
        helper = TermsHelpers()
        helper.program, helper.officer = self.program, self.officer
        helper.reconcile()
        definition = self.policy_definition()
        definition['criteria']['PR']['rubric_definition'] = {
            'program_id': str(self.program.pk), 'version': 1, 'terms_digest': terms_digest(snapshot_terms(self.program)),
            'authority_reference': 'Synthetic specific rubric authority', 'items': [{
                'id': 'synthetic-requirement', 'requirement_id': self.relevance_requirement.pk,
                'applicability': 'all_applications', 'outcomes': {'supported': 'Synthetic finding supported by reviewed evidence'},
                'evidence_mappings': [self.mapping('PR')]}]}
        self.policy = self.policy_record(definition)

    def relevance_values(self):
        return {'rubric_attested': True, 'rubric_findings': [{'item_id': 'synthetic-requirement',
            'outcome': 'supported', 'explanation': 'Synthetic evidence supports this specific requirement.',
            'review_ids': [self.criterion_reviews['PR'].pk]}]}

    def verify(self, **overrides):
        values = dict(user=self.officer, member_version=self.member.version, verified=True,
                      expires_on=None, reason='Synthetic source review')
        return verify_document(self.document.pk, **{**values, **overrides})

    def context(self):
        self.application.refresh_from_db()
        return source_context(self.application)

    def policy_record(self, snapshot=None, **overrides):
        latest = EvidencePolicyRevision.objects.filter(program=self.program).first()
        self.program.refresh_from_db()
        values = dict(user=self.officer, snapshot=snapshot or self.policy_definition(), authority_reference='Synthetic test definitions',
            expected_revision=latest.revision if latest else 0,
            expected_context=digest({'program_version': self.program.version, 'approval': approval_context(self.program)}),
            reason='Synthetic policy recorded for review, never activated', confirmed=True)
        return record_policy(self.program.pk, **{**values, **overrides})

    def assessment_values(self, criterion='ND', **overrides):
        if criterion == 'PR' and not hasattr(self, 'relevance_requirement'):
            self.prepare_relevance()
        latest = CriterionAssessment.objects.filter(application=self.application, criterion=criterion).first()
        return dict(user=self.officer, criterion=criterion, policy_id=self.policy.pk, state='VERIFIED',
            source_type={'SI': 'monthly_income', 'ES': 'employment_text', 'PA': 'successful_releases',
                         'ND': 'dependent_count', 'PR': 'program_relevance'}[criterion],
            value='relevant' if criterion == 'PR' else None,
            expected_revision=latest.revision if latest else 0, expected_context=digest(self.context()),
            reason='Synthetic evidence explicitly reviewed', confirmed=True,
            supporting_review_ids=[self.document_review.pk] if criterion == 'ND' else
                [self.criterion_reviews[criterion].pk] if criterion in ('SI', 'ES') else [],
            **(self.relevance_values() if criterion == 'PR' else {}), **overrides)

    def assess(self, criterion='ND', **overrides):
        values = self.assessment_values(criterion)
        return record_assessment(self.application.pk, **{**values, **overrides})
