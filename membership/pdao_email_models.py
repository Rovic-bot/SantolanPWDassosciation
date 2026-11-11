"""Immutable PDAO applicant notices, including staff-confirmed ID collection."""
import uuid

from django.conf import settings
from django.db import models

from .approval_email_models import ApprovalEmailRecord, MembershipApprovalEmail


class PDAOReviewEmail(ApprovalEmailRecord):
    mutable_fields = MembershipApprovalEmail.mutable_fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registration = models.ForeignKey('membership.PDAORegistration', on_delete=models.PROTECT, related_name='review_emails')
    expected_version = models.PositiveIntegerField()
    outcome = models.CharField(max_length=12, choices=[('ready', 'Office verification invitation'),
        ('needs_info', 'Information request'), ('claim_ready', 'PWD ID ready for collection')])
    recipient = models.EmailField()
    sender = models.EmailField(blank=True)
    subject = models.CharField(max_length=250)
    body = models.TextField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    requested_by_label = models.CharField(max_length=150)
    state = models.CharField(max_length=12, choices=MembershipApprovalEmail.State.choices + [
        ('cancelled', 'Not sent — application changed')], default='queued', db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    backend = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ['-created_at', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['registration', 'expected_version'], name='pdao_review_email_version'),
            models.CheckConstraint(condition=models.Q(outcome__in=['ready', 'needs_info', 'claim_ready']), name='pdao_review_email_outcome'),
            models.CheckConstraint(condition=models.Q(state__in=['queued', 'sending', 'sent', 'failed', 'uncertain', 'cancelled']), name='pdao_review_email_state'),
            models.CheckConstraint(condition=~models.Q(recipient=''), name='pdao_review_email_recipient'),
        ]


class PDAOReviewEmailAttempt(ApprovalEmailRecord):
    email = models.ForeignKey(PDAOReviewEmail, on_delete=models.PROTECT, related_name='attempts')
    number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=12, choices=[('accepted', 'Accepted'), ('failed', 'Failed'), ('uncertain', 'Unconfirmed')])
    error_type = models.CharField(max_length=100, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['email', 'number'], name='pdao_review_email_attempt')]
