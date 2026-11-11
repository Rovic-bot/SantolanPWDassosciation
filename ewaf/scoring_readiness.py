"""No G15 operational consumer is available."""
from django.core.exceptions import ValidationError


def require_operational_scoring(*args, **kwargs):
    raise ValidationError('OPERATIONAL_SCORING_UNAVAILABLE', code='OPERATIONAL_SCORING_UNAVAILABLE')
