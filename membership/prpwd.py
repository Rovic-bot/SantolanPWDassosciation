"""Manual registry lookup; opening the external page never verifies a member."""
from django.core.exceptions import ValidationError

from .models import MembershipSettings, validate_registry_url


def registry_url():
    policy = MembershipSettings.objects.filter(pk=1).first()
    if not policy or not policy.prpwd_url:
        return ''
    try:
        validate_registry_url(policy.prpwd_url)
    except ValidationError:
        return ''
    return policy.prpwd_url
