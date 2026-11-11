from ipaddress import ip_address

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from .models import SecurityEvent


def record_event(request, action, user=None):
    address = request.META.get('REMOTE_ADDR') if request else None
    try:
        address = str(ip_address(address))
    except ValueError:
        address = None
    SecurityEvent.objects.create(user=user if user and user.pk else None,
                                 action=action, address=address)


@receiver(user_logged_in)
def signed_in(sender, request, user, **kwargs):
    record_event(request, SecurityEvent.Action.LOGIN, user)


@receiver(user_logged_out)
def signed_out(sender, request, user, **kwargs):
    if user is not None:
        record_event(request, SecurityEvent.Action.LOGOUT, user)


@receiver(user_login_failed)
def sign_in_failed(sender, request, **kwargs):
    action = (SecurityEvent.Action.LOGIN_BLOCKED if getattr(request, 'login_rate_limited', False)
              else SecurityEvent.Action.LOGIN_FAILED)
    # Never persist credentials, attempted usernames, or request bodies.
    record_event(request, action)
