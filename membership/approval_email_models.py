"""Private, immutable message snapshots for online membership approvals."""
from contextlib import contextmanager
from contextvars import ContextVar
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models

_writing = ContextVar('membership_approval_email_writer', default=False)


@contextmanager
def approval_email_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


class ApprovalEmailQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Use the membership approval email service.')

    def delete(self):
        raise PermissionDenied('Notification history must be retained.')

    def bulk_create(self, *args, **kwargs):
        raise PermissionDenied('Use the membership approval email service.')

    def bulk_update(self, *args, **kwargs):
        raise PermissionDenied('Use the membership approval email service.')


class ApprovalEmailRecord(models.Model):
    objects = ApprovalEmailQuerySet.as_manager()
    mutable_fields = frozenset()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not _writing.get():
            raise PermissionDenied('Use the membership approval email service.')
        if not self._state.adding:
            fields = kwargs.get('update_fields')
            if not fields or not set(fields).issubset(self.mutable_fields):
                raise PermissionDenied('Notification contents and attempts are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Notification history must be retained.')


class MembershipApprovalEmail(ApprovalEmailRecord):
    mutable_fields = frozenset({'state', 'attempt_count', 'last_attempt_at', 'accepted_at', 'backend', 'sender'})

    class State(models.TextChoices):
        QUEUED = 'queued', 'Email queued'
        SENDING = 'sending', 'Sending email — confirmation pending'
        SENT = 'sent', 'Accepted by Gmail'
        FAILED = 'failed', 'Email could not be sent'
        UNCERTAIN = 'uncertain', 'Email delivery is unconfirmed'
        SKIPPED = 'skipped', 'No email sent — no valid email address'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intake = models.OneToOneField('membership.RegistrationIntake', on_delete=models.PROTECT, related_name='approval_email')
    revision = models.ForeignKey('membership.RegistrationRevision', on_delete=models.PROTECT, related_name='+')
    recipient = models.EmailField(blank=True)
    sender = models.EmailField(blank=True)
    subject = models.CharField(max_length=250)
    body = models.TextField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    requested_by_label = models.CharField(max_length=150)
    state = models.CharField(max_length=12, choices=State.choices, default=State.QUEUED, db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    backend = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=models.Q(state__in=['queued', 'sending', 'sent', 'failed', 'uncertain', 'skipped']), name='membership_email_valid_state'),
            models.CheckConstraint(condition=models.Q(state='skipped') | ~models.Q(recipient=''), name='membership_email_recipient'),
        ]


class MembershipApprovalEmailAttempt(ApprovalEmailRecord):
    email = models.ForeignKey(MembershipApprovalEmail, on_delete=models.PROTECT, related_name='attempts')
    number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=12, choices=[('accepted', 'Accepted'), ('failed', 'Failed'), ('uncertain', 'Unconfirmed')])
    # Provider response bodies and credentials are never retained here.
    error_type = models.CharField(max_length=100, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['number']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['email', 'number'], name='membership_email_attempt_unique')]
