from django.contrib.auth.models import User
from django.db import models


class Administrator(User):
    """Permission namespace over existing users; no replacement user table."""

    class Meta:
        proxy = True
        default_permissions = ()
        permissions = [('access_dashboard', 'Can access administration dashboard')]


class LoginWindow(models.Model):
    """Shared, fixed-window login counters. Keys contain only HMAC digests."""

    key = models.CharField(max_length=64, primary_key=True)
    started_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        default_permissions = ()
