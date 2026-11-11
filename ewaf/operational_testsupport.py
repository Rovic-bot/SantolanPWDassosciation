"""Fictional fixtures only. No production defaults or authority are supplied."""
from datetime import timedelta
from unittest.mock import patch
from django.utils import timezone
from .four_testsupport import FourHelpers
from .four_criterion_development import ahp
from . import operational_services as service


class OperationalHelpers(FourHelpers):
    def setup_operational(self, additional=0):
        self.fixture_time = timezone.now() - timedelta(days=2)
        with patch('django.utils.timezone.now', return_value=self.fixture_time):
            self.setup_durable()
            helpers = []
            for i in range(additional):
                helpers.append(self.add_four_ready_applicant('FICTIONAL-OP-' + str(i), income=str(i % 10 * 10), dependents=i % 8))
            self.helpers = [self, *helpers]
        self.program.refresh_from_db()
        self.proposal = self.four_proposal()
        self.proposal.pop('purpose')
        self.proposal.update(authority_reference='Fictional test authority; NOT Association approval',
            authorized_scope='This fictional assistance program only', approval_date=str(timezone.localdate() - timedelta(days=3)),
            effective_from=(timezone.now() - timedelta(days=2)).isoformat(), effective_until=(timezone.now() + timedelta(days=7)).isoformat(),
            selection_rule='reasoned_human_within_slots', tie_rule='reasoned_human',
            tie_procedure='Fictional test policy: an authorized human explains the choice for every exact tie.',
            classification_mode='none', classifications=None, edge_cases='block',
            pa_scope='all_programs', pa_period='all_retained', pa_start=None, pa_end=None)

    def lock_policy(self, **changes):
        self.proposal.update(changes)
        self.operational_configuration = service.record_configuration(self.program.pk, user=self.officer,
            expected=service.configuration_token(self.program), proposed=self.proposal, judgments=ahp()['pairs'],
            status='LOCKED', reason='Fictional explicit approved policy test', attested=True)
        return self.operational_configuration

    def calculate(self, **overrides):
        from uuid import uuid4
        return service.generate(self.program.pk, **{'user': self.officer,
            'expected': service.context(self.program.pk, user=self.officer),
            'reason': 'Fictional complete eligible pool', 'request_key': uuid4(), **overrides})

    def choose(self, run, **overrides):
        return service.record_decision(self.program.pk, **{'user': self.officer, 'run_id': run.pk,
            'application_id': self.application.pk, 'expected_revision': 0, 'outcome': 'SELECTED',
            'reason': 'Fictional human review of functional need and approved program capacity.',
            'tie_reason': 'Fictional application of explicitly authorized human tie procedure.', **overrides})
