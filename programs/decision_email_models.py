"""Private, durable notifications for administrator eligibility decisions."""
from contextlib import contextmanager
from contextvars import ContextVar
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models

_writing = ContextVar('decision_email_writer', default=False)


@contextmanager
def decision_email_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


class DecisionEmailQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Use the decision email service.')

    def delete(self):
        raise PermissionDenied('Notification history must be retained.')

    def bulk_create(self, *args, **kwargs):
        raise PermissionDenied('Use the decision email service.')

    def bulk_update(self, *args, **kwargs):
        raise PermissionDenied('Use the decision email service.')


class DecisionEmailRecord(models.Model):
    objects = DecisionEmailQuerySet.as_manager()
    mutable_fields = frozenset()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not _writing.get():
            raise PermissionDenied('Use the decision email service.')
        if not self._state.adding:
            fields = kwargs.get('update_fields')
            if not fields or not set(fields).issubset(self.mutable_fields):
                raise PermissionDenied('Notification contents and attempts are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Notification history must be retained.')


class ApplicationDecisionEmail(DecisionEmailRecord):
    mutable_fields = frozenset({'state', 'attempt_count', 'last_attempt_at', 'accepted_at', 'backend', 'sender', 'skip_reason'})

    class State(models.TextChoices):
        QUEUED = 'queued', 'Email queued'
        SENDING = 'sending', 'Sending email — confirmation pending'
        SENT = 'sent', 'Accepted by email service'
        FAILED = 'failed', 'Email could not be sent'
        SKIPPED = 'skipped', 'No email sent'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT, related_name='decision_emails')
    application_version = models.PositiveIntegerField()
    outcome = models.CharField(max_length=12, choices=[('eligible', 'Eligible'), ('review', 'Needs Information'), ('ineligible', 'Ineligible')])
    remarks = models.TextField(max_length=2000, blank=True)
    recipient = models.EmailField(blank=True)
    recipient_source = models.CharField(max_length=12, choices=[('application', 'Application form'), ('registration', 'Onsite registration'), ('', 'No address')], blank=True)
    skip_reason = models.CharField(max_length=12, choices=[('', 'Not skipped'), ('missing', 'No email provided'), ('invalid', 'Email is invalid'), ('superseded', 'Application changed')], blank=True)
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
        ordering = ['-created_at', '-pk']
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=['application', 'application_version'], name='decision_email_version_unique'),
            models.CheckConstraint(condition=models.Q(state__in=['queued', 'sending', 'sent', 'failed', 'skipped']), name='decision_email_valid_state'),
            models.CheckConstraint(condition=models.Q(outcome__in=['eligible', 'review', 'ineligible']), name='decision_email_valid_outcome'),
            models.CheckConstraint(condition=models.Q(state='skipped') | ~models.Q(recipient=''), name='decision_email_has_recipient'),
        ]


class ApplicationDecisionEmailAttempt(DecisionEmailRecord):
    email = models.ForeignKey(ApplicationDecisionEmail, on_delete=models.PROTECT, related_name='attempts')
    number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=12, choices=[('accepted', 'Accepted'), ('failed', 'Failed')])
    # Never retain SMTP response bodies, credentials, or provider diagnostics.
    error_type = models.CharField(max_length=100, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['number']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['email', 'number'], name='decision_email_attempt_unique')]
