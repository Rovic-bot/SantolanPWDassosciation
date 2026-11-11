"""Explicit fictional policies/records; used only by test modules."""
from django.utils import timezone
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from .scoring_testsupport import ScoringHelpers
from .normalization import CRITERIA
from .durable_services import inspect_development_context, request_development_calculation, process_development_request


def fictional_definitions():
    definitions = {}
    for code, source, kind, unit, upper, encoding in (
            ('SI', 'monthly_income', 'decimal', 'PHP/month', '100', None),
            ('ES', 'employment_text', 'text', 'text', '1', {'Test employment description': '1'}),
            ('PA', 'successful_releases', 'integer', 'records', '10', None),
            ('ND', 'dependent_count', 'integer', 'persons', '10', None),
            ('PR', 'program_relevance', 'category', 'category', '1', {'relevant': '1'})):
        definitions[code] = {'measure': 'Fictional test measure ' + code, 'source_type': source,
            'value_type': kind, 'unit': unit, 'encoding': encoding, 'direction': 'benefit',
            'bounds': {'method': 'fixed', 'lower': '0', 'upper': upper},
            'observation_period': 'Fictional current source observation; PA all retained successful releases',
            'edge_cases': 'Block missing, disputed, expired, stale or out-of-range input'}
    return {'criteria': definitions}


class DurableHelpers(ScoringHelpers, ConfigurationHelpers, EvidenceHelpers):
    def policy_definition(self):
        snapshot = super().policy_definition()
        snapshot['criteria']['ES']['unit'] = 'text'
        snapshot['criteria']['PR']['unit'] = 'category'
        return snapshot

    def setup_durable(self):
        self.setup_evidence()
        self.prepare_relevance()
        self.draft()
        self.validate()
        self.scoring_policy = self.propose(proposed=fictional_definitions())
        for code in CRITERIA:
            self.assess(code)
        self.contract = {'purpose': 'FICTIONAL_DISPOSABLE_TEST', 'version': 1,
            'scope': 'submitted_at_or_before_cutoff', 'cutoff': timezone.now().isoformat(),
            'pending': 'block', 'comparison': 'descending_exact_ties', 'repeat_rule': 'explicit_test_request'}

    def context(self):
        # EvidenceHelpers.context is used during fixture assessment creation.
        return super().context()

    def inspect_pool(self, **kwargs):
        return inspect_development_context(self.program.pk,
            **{'user': self.officer, 'contract': self.contract, **kwargs})

    def request_run(self, **kwargs):
        values = {'user': self.officer, 'request_key': 'fictional-request-1', 'contract': self.contract,
                  'reason': 'Fictional isolated evaluation', 'expected_context': self.inspect_pool()['context_digest']}
        return request_development_calculation(self.program.pk, **{**values, **kwargs})

    def process(self, request, **kwargs):
        return process_development_request(request.pk, **{'program_id': self.program.pk, 'user': self.officer, **kwargs})

    def add_ready_applicant(self):
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
        helper.member = create_member('SYN-DURABLE-SECOND')
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
        review_eligibility(helper.application.pk, user=self.officer,
            data=review_data(helper.application, **{f'check_{self.relevance_requirement.pk}': 'pass'}))
        helper.criterion_documents, helper.criterion_reviews = {}, {}
        for code, old in self.criterion_documents.items():
            document = MembershipApplicationDocument.objects.create(application=intake, requirement=old.requirement,
                label='Fictional additional evidence', file=pdf(), content_type='application/pdf', size=50)
            helper.criterion_documents[code] = document
            helper.criterion_reviews[code] = verify_document(document.pk, user=self.officer,
                member_version=helper.member.version, verified=True, expires_on=None, reason='Fictional verification')
        helper.document = helper.criterion_documents['ND']
        helper.document_review = helper.criterion_reviews['ND']
        for code in CRITERIA:
            helper.assess(code)
        self.contract = {**self.contract, 'cutoff': timezone.now().isoformat()}
        return helper
