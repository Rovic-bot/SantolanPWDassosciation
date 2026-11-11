"""Score-free G16 adapter. No connection to synthetic numerical fixtures."""
from django.core.exceptions import ValidationError
from .scoring_inputs import applicant_readiness, validate_readiness_payload
from .ranking_policy import policy_completeness


def ranking_readiness(application_id, *, user, program_id=None):
    result = applicant_readiness(application_id, user=user, program_id=program_id)
    validate_readiness_payload(result)
    # G15's strict score-free schema is retained intact, including all barriers.
    return {'schema_version': 1, 'mode': 'READINESS_ONLY', 'readiness': result,
            'ranking_policy': policy_completeness(), 'effective_authorization': False,
            'operational_ready': False, 'reason': 'OPERATIONAL_RANKING_UNAVAILABLE'}


def require_operational_ranking(*args, **kwargs):
    raise ValidationError('OPERATIONAL_RANKING_UNAVAILABLE', code='OPERATIONAL_RANKING_UNAVAILABLE')
