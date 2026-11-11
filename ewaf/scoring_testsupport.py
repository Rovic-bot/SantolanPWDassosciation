"""Synthetic fixtures only; no imported Association scoring policy."""
from .normalization import CRITERIA
from .evidence import digest
from .scoring_inputs import policy_context, applicant_readiness
from .scoring_services import record_scoring_policy, record_applicant_diagnostic


class ScoringHelpers:
    def setup_scoring(self):
        self.setup_evidence()
        self.draft()
        self.validate()
        self.scoring_policy = self.propose()

    def proposal_values(self):
        return {'user': self.officer, 'proposed': {'criteria': {key: {} for key in CRITERIA}},
                'configuration_id': self.configuration.pk, 'validation_id': self.validation.pk,
                'evidence_policy_id': self.policy.pk, 'expected_context': digest(policy_context(self.program)),
                'reason': 'Synthetic pending scoring proposal', 'confirmed': True}

    def propose(self, **changes):
        return record_scoring_policy(self.program.pk, **{**self.proposal_values(), **changes})

    def diagnostic(self, **changes):
        return applicant_readiness(self.application.pk, **{'user': self.officer, **changes})

    def capture_values(self):
        return {'user': self.officer, 'program_id': self.program.pk, 'expected_context': self.diagnostic()['context_digest'],
                'reason': 'Synthetic readiness retention', 'confirmed': True}

    def capture_diagnostic(self, **changes):
        return record_applicant_diagnostic(self.application.pk, **{**self.capture_values(), **changes})
