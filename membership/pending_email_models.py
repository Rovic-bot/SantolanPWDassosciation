"""Private pending-review messages, retained independently of approval notices."""
import uuid

from django.conf import settings
from django.db import models

from .approval_email_models import ApprovalEmailRecord, MembershipApprovalEmail


class MembershipPendingEmail(ApprovalEmailRecord):
    mutable_fields = MembershipApprovalEmail.mutable_fields
    STATES = MembershipApprovalEmail.State.choices + [('cancelled', 'Not sent — application changed')]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intake = models.ForeignKey('membership.RegistrationIntake', on_delete=models.PROTECT, related_name='pending_emails')
    revision = models.ForeignKey('membership.RegistrationRevision', on_delete=models.PROTECT, related_name='+')
    expected_version = models.PositiveIntegerField()
    reason = models.CharField(max_length=2000)
    recipient = models.EmailField()
    sender = models.EmailField(blank=True)
    subject = models.CharField(max_length=250)
    body = models.TextField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    requested_by_label = models.CharField(max_length=150)
    state = models.CharField(max_length=12, choices=STATES, default='queued', db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    backend = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ['-created_at', '-pk']
        constraints = [
            models.CheckConstraint(condition=models.Q(state__in=['queued', 'sending', 'sent', 'failed', 'uncertain', 'skipped', 'cancelled']), name='membership_pending_email_state'),
            models.CheckConstraint(condition=~models.Q(recipient=''), name='membership_pending_email_to'),
            models.UniqueConstraint(fields=['intake', 'expected_version'], name='membership_pending_email_version'),
        ]


class MembershipPendingEmailAttempt(ApprovalEmailRecord):
    email = models.ForeignKey(MembershipPendingEmail, on_delete=models.PROTECT, related_name='attempts')
    number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=12, choices=[('accepted', 'Accepted'), ('failed', 'Failed'), ('uncertain', 'Unconfirmed')])
    error_type = models.CharField(max_length=100, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['email', 'number'], name='membership_pending_attempt_unique')]
