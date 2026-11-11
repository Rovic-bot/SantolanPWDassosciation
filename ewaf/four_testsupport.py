"""Explicit fictional parameters, never default policy or approval seeds."""
from copy import deepcopy
from django.utils import timezone
from .durable_testsupport import DurableHelpers, fictional_definitions
from .four_policy import CRITERIA, PROFILE, PURPOSE, ELIGIBILITY_KEYS, PA_PERIOD
from .four_criterion_development import ahp
from .four_services import record_configuration
from .configuration_services import configuration_context
from .evidence import digest


class FourHelpers(DurableHelpers):
    def prepare_relevance(self, kind='text'):
        from programs.models import ProgramRequirement
        from programs.forms import snapshot
        from programs.terms import snapshot_terms, terms_digest
        from programs.test_approved_terms import TermsHelpers
        from assistance.services import review_eligibility
        from assistance.tests import review_data
        self.relevance_requirements = []
        for role in ELIGIBILITY_KEYS:
            self.relevance_requirements.append(ProgramRequirement.objects.create(program=self.program,
                label='Fictional ' + role, kind='text', instructions='Explicit fictional assessment evidence'))
        self.relevance_requirement = self.relevance_requirements[0]
        self.application.requirements_snapshot = snapshot(self.program)
        self.application.answers = {str(row.pk): 'Fictional ' + role + ' reviewed with accessible written evidence'
            for row, role in zip(self.relevance_requirements, ELIGIBILITY_KEYS)}
        self.application.save(update_fields=['requirements_snapshot', 'answers'])
        review_eligibility(self.application.pk, user=self.officer, data=review_data(self.application,
            **{f'check_{row.pk}': 'pass' for row in self.relevance_requirements}))
        helper = TermsHelpers()
        helper.program, helper.officer = self.program, self.officer
        helper.reconcile()
        definition = self.policy_definition()
        rubric = {'program_id': str(self.program.pk), 'version': 1,
            'terms_digest': terms_digest(snapshot_terms(self.program)),
            'authority_reference': 'Fictional functional need, consent and accessible alternative test rubric'}
        definition['criteria']['PR']['rubric_definition'] = rubric
        rubric['items'] = [{'id': role, 'requirement_id': row.pk, 'applicability': 'all_applications',
            'outcomes': {'supported': 'Fictional evidence supports the explicitly named requirement'},
            'evidence_mappings': [self.mapping('PR')]}
            for role, row in zip(ELIGIBILITY_KEYS, self.relevance_requirements)]
        self.policy = self.policy_record(definition)

    def relevance_values(self):
        if not hasattr(self, 'relevance_requirements'):
            return super().relevance_values()
        return {'rubric_attested': True, 'rubric_findings': [{'item_id': role, 'outcome': 'supported',
            'explanation': 'Fictional documented ' + role + '; classification alone is insufficient.',
            'review_ids': [self.criterion_reviews['PR'].pk]} for role in ELIGIBILITY_KEYS]}

    def four_proposal(self):
        result = {'purpose': PURPOSE, 'criteria': {key: value for key, value in fictional_definitions()['criteria'].items()
            if key in CRITERIA}, 'eligibility': {role: {'item': role, 'accepted_outcome': 'supported'}
                for role in ELIGIBILITY_KEYS}}
        result['criteria']['PA']['observation_period'] = PA_PERIOD
        return result

    def install_four(self):
        self.scoring_policy = record_configuration(self.program.pk, user=self.officer, expected=self.expected(),
            expected_context=digest(configuration_context(self.program)), judgments=ahp()['pairs'],
            proposed=self.four_proposal(), reason='Explicit fictional-only four-criterion test parameters')
        self.configuration = self.scoring_policy.configuration
        self.validation = self.scoring_policy.validation
        self.contract = {**self.contract, 'profile': PROFILE, 'cutoff': timezone.now().isoformat()}

    def add_four_ready_applicant(self, code='FICTIONAL-FOUR-SECOND', *, income=None, dependents=None):
        from copy import copy
        from members.tests import create_member
        from membership.services import record_event
        from documents.models import MembershipApplicationDocument
        from documents.services import verify_document
        from membership.tests import pdf
        from programs.testsupport import application_fixture
        from assistance.services import review_eligibility
        from assistance.tests import review_data
        helper = copy(self)
        helper.member = create_member(code)
        # Fixture-only construction, before reviews or the generation session.
        # Values still pass the actual evidence-assessment services below.
        if income is not None:
            helper.member.monthly_income = income
        if dependents is not None:
            helper.member.dependents = dependents
        helper.member.save()
        intake = helper.member.application
        intake.prpwd_verified_by = intake.decided_by = self.officer
        intake.save()
        record_event(intake, 'prpwd_verified', 'Fictional manual verification', user=self.officer)
        record_event(intake, 'approved', 'Fictional approved intake', user=self.officer)
        helper.application = application_fixture(self.program, helper.member)
        helper.application.source_snapshot = {'member_id': helper.member.pk, 'member_version': helper.member.version,
            'program_version': self.program.version, 'membership_verified_at': timezone.now().isoformat(),
            'policy_authorized_at': self.program.policy_authorized_at.isoformat()}
        helper.application.requirements_snapshot = self.application.requirements_snapshot
        helper.application.answers = self.application.answers
        helper.application.save(update_fields=['source_snapshot', 'requirements_snapshot', 'answers'])
        review_eligibility(helper.application.pk, user=self.officer, data=review_data(helper.application,
            **{f'check_{row.pk}': 'pass' for row in self.relevance_requirements}))
        helper.criterion_documents, helper.criterion_reviews = {}, {}
        for code, old in self.criterion_documents.items():
            document = MembershipApplicationDocument.objects.create(application=intake, requirement=old.requirement,
                label='Fictional additional evidence', file=pdf(), content_type='application/pdf', size=50)
            helper.criterion_documents[code] = document
            helper.criterion_reviews[code] = verify_document(document.pk, user=self.officer,
                member_version=helper.member.version, verified=True, expires_on=None, reason='Fictional verification')
        helper.document = helper.criterion_documents['ND']
        helper.document_review = helper.criterion_reviews['ND']
        for code in (*CRITERIA, 'PR'):
            helper.assess(code)
        self.contract = {**self.contract, 'cutoff': timezone.now().isoformat()}
        return helper
