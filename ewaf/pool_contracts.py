"""Non-effective contracts for the schema-deferred full-pool increment.

These findings never confer processing authority, even for a complete proposal.
No numerical applicant payload or persistent result is defined here.
"""
import re

from django.core.exceptions import ValidationError

from .scoring_policy import proposal, proposal_reasons


ENGINE = 'pool-readiness-1'
# Engineering ceiling for a double observation, not an admission/slot policy.
MAX_APPLICATIONS = 128
BARRIERS = (
    'EVALUATION_SCOPE_POLICY_PENDING',
    'EVALUATION_CUTOFF_POLICY_PENDING',
    'REPEAT_EVALUATION_POLICY_PENDING',
    'OFFICER_PROGRAM_SCOPE_PENDING',
    'PROCESSING_AUTHORITY_PENDING',
    'PA_SCOPE_CUTOFF_POLICY_PENDING',
    'CLASSIFICATION_POLICY_PENDING',
    'BUSINESS_TIE_POLICY_PENDING',
    'CRITERION_POLICY_UNAPPROVED',
    'CONFIGURATION_AUTHORIZATION_UNAVAILABLE',
    'PROCESSING_GATE_UNAVAILABLE',
    'OPERATIONAL_SCORING_UNAVAILABLE',
    'OPERATIONAL_RANKING_UNAVAILABLE',
    'DURABLE_POOL_STORAGE_UNAVAILABLE',
)


def scoring_findings(value):
    """Validate a G15 proposal without turning it into an approved policy.

    Delegates bounded parsing, Decimal bounds and criterion validation to G15.
    Values are never returned in diagnostic findings.
    """
    if value is None:
        return [{'code': 'SCORING_POLICY_MISSING', 'source': None}]
    try:
        return proposal_reasons(proposal(value))
    except ValidationError:
        return [{'code': 'SCORING_POLICY_INVALID', 'source': None}]


def require_context_digest(value):
    if type(value) is not str or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValidationError('POOL_CONTEXT_INVALID', code='POOL_CONTEXT_INVALID')


def unavailable():
    """Unconditional: no flag, actor or request argument can enable persistence."""
    raise ValidationError('DURABLE_POOL_STORAGE_UNAVAILABLE', code='DURABLE_POOL_STORAGE_UNAVAILABLE')
