"""Synthetic G14 helpers; never production policy or seed data."""
from .evidence import digest
from .ahp_validation import CRITERIA, PAIRS
from .configuration_services import (configuration_context, record_configuration, record_validation,
                                     record_review, record_authority_evidence)


def equal_judgments():
    return {'criteria': list(CRITERIA), 'mode': 'pairs', 'values': {key: '1' for key in PAIRS}}


class ConfigurationHelpers:
    def context_token(self):
        self.program.refresh_from_db()
        return digest(configuration_context(self.program))

    def common(self):
        return {'user': self.officer, 'expected_context': self.context_token(),
                'reason': 'Synthetic G14 preparatory finding', 'confirmed': True}

    def draft(self, **changes):
        values = {**self.common(), 'judgments': equal_judgments(), 'policy_id': self.policy.pk}
        self.configuration = record_configuration(self.program.pk, **{**values, **changes})
        return self.configuration

    def validate(self, **changes):
        values = {**self.common(), 'configuration_id': self.configuration.pk}
        self.validation = record_validation(self.program.pk, **{**values, **changes})
        return self.validation

    def review(self, **changes):
        values = {**self.common(), 'configuration_id': self.configuration.pk, 'validation_id': self.validation.pk,
                  'finding': 'REVIEWED', 'correction_requests': ''}
        return record_review(self.program.pk, **{**values, **changes})

    def authority(self, **changes):
        values = {**self.common(), 'configuration_id': self.configuration.pk, 'validation_id': self.validation.pk,
                  'authority_reference': 'Synthetic documentary reference', 'stated_scope': 'Synthetic AHP judgments only',
                  'attested': True}
        return record_authority_evidence(self.program.pk, **{**values, **changes})
