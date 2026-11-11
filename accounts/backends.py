import unicodedata
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied
from django.db import OperationalError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import LoginWindow


def window_key(kind, value):
    return salted_hmac(f'accounts.login.{kind}', value, algorithm='sha256').hexdigest()


def reserve_login_attempt(username, address):
    # Fold case/accents conservatively: MySQL usernames may compare that way.
    normalized = ''.join(char for char in unicodedata.normalize('NFKD', username.casefold())
                         if not unicodedata.combining(char)).strip()
    limits = {
        window_key('username', normalized): settings.LOGIN_USERNAME_LIMIT,
        window_key('address', address): settings.LOGIN_ADDRESS_LIMIT,
    }
    for _ in range(3):
        try:
            return reserve_windows(limits)
        except LoginWindow.DoesNotExist:
            # An expired counter may have been purged just before it was locked.
            continue
        except OperationalError as error:
            if error.args[0] not in (1205, 1213):
                raise
    # Fail closed if contention persists; never bypass the limit.
    return False


def reserve_windows(limits, window_seconds=None, window_model=LoginWindow):
    # Commit new rows before locking: concurrent duplicate inserts otherwise
    # retain shared index locks and can deadlock while upgrading to write locks.
    for key in sorted(limits):
        window_model.objects.get_or_create(key=key, defaults={'started_at': timezone.now()})
    with transaction.atomic():
        windows = []
        # Stable lock order prevents opposing account/address lock order.
        for key in sorted(limits):
            windows.append(window_model.objects.select_for_update().get(pk=key))
        now = timezone.now()
        for window in windows:
            if window.started_at <= now - timedelta(seconds=window_seconds or settings.LOGIN_WINDOW_SECONDS):
                window.started_at = now
                window.attempts = 0
        if any(window.attempts >= limits[window.pk] for window in windows):
            return False
        for window in windows:
            window.attempts += 1
            window.save(update_fields=['started_at', 'attempts'])
    return True


class StaffBackend(ModelBackend):
    """One authentication policy for both portal and Django admin logins."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        # Ignore forwarded headers. Deployment must configure a trusted proxy.
        address = request.META.get('REMOTE_ADDR', '') if request else 'local'
        if not reserve_login_attempt(username, address):
            if request is not None:
                request.login_rate_limited = True
            raise PermissionDenied
        return super().authenticate(request, username=username, password=password, **kwargs)

    def user_can_authenticate(self, user):
        return super().user_can_authenticate(user) and user.is_staff
