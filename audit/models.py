from django.conf import settings
from django.db import models


class SecurityEvent(models.Model):
    class Action(models.TextChoices):
        LOGIN = 'login', 'Signed in'
        LOGIN_FAILED = 'login_failed', 'Sign-in failed'
        LOGIN_BLOCKED = 'login_blocked', 'Sign-in rate limited'
        LOGOUT = 'logout', 'Signed out'
        PASSWORD_CHANGED = 'password_changed', 'Changed own password'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                             on_delete=models.SET_NULL)
    action = models.CharField(max_length=20, choices=Action.choices)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-occurred_at', '-pk']
        default_permissions = ('view',)

    def __str__(self):
        return f'{self.get_action_display()} at {self.occurred_at}'
