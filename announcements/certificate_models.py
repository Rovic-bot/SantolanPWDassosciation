"""Private publication certificate outbox and append-only delivery attempts."""
from contextlib import contextmanager
from contextvars import ContextVar
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models

_writing = ContextVar('certificate_writer', default=False)


@contextmanager
def certificate_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


class CertificateQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Use the certificate service.')

    def delete(self):
        raise PermissionDenied('Certificate history must be retained.')

    def bulk_create(self, *args, **kwargs):
        raise PermissionDenied('Use the certificate service.')

    def bulk_update(self, *args, **kwargs):
        raise PermissionDenied('Use the certificate service.')


class CertificateRecord(models.Model):
    objects = CertificateQuerySet.as_manager()
    mutable_fields = frozenset()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not _writing.get():
            raise PermissionDenied('Use the certificate service.')
        if not self._state.adding:
            fields = kwargs.get('update_fields')
            if not fields or not set(fields).issubset(self.mutable_fields):
                raise PermissionDenied('Certificate contents and attempts are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Certificate history must be retained.')


class SelectionCertificateEmail(CertificateRecord):
    mutable_fields = frozenset({'state', 'reason', 'sender', 'reply_to', 'recipient',
        'recipient_source', 'attempt_count', 'first_attempt_at', 'last_attempt_at',
        'accepted_at', 'provider_id', 'acceptance_unknown'})

    class State(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        BLOCKED = 'blocked', 'Waiting for setup or correction'
        SENDING = 'sending', 'Sending'
        SENT = 'sent', 'Accepted by email service'
        FAILED = 'failed', 'Delivery failed'
        UNCERTAIN = 'uncertain', 'Delivery needs checking'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField('programs.ProgramApplication', on_delete=models.PROTECT,
        related_name='selection_certificate')
    revision = models.ForeignKey('announcements.ProgramResultRevision', on_delete=models.PROTECT,
        related_name='certificate_emails')
    member_name = models.CharField(max_length=250)
    program_name = models.CharField(max_length=200)
    issued_on = models.DateField()
    document = models.BinaryField(editable=False)
    document_sha256 = models.CharField(max_length=64)
    recipient = models.EmailField(blank=True)
    recipient_source = models.CharField(max_length=12, blank=True)
    provider = models.CharField(max_length=12, default='resend',
        choices=[('resend', 'Resend'), ('gmail', 'Gmail')])
    sender = models.EmailField(blank=True)
    reply_to = models.EmailField(blank=True)
    subject = models.CharField(max_length=250)
    body = models.TextField()
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
        on_delete=models.SET_NULL, related_name='+')
    requested_by_label = models.CharField(max_length=150)
    state = models.CharField(max_length=12, choices=State.choices, default=State.QUEUED, db_index=True)
    reason = models.CharField(max_length=32, blank=True)
    attempt_count = models.PositiveIntegerField(default=0)
    first_attempt_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    acceptance_unknown = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    provider_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']
        default_permissions = ()
        constraints = [models.CheckConstraint(
            condition=models.Q(state__in=['queued', 'blocked', 'sending', 'sent', 'failed', 'uncertain']),
            name='certificate_email_valid_state')]


class SelectionCertificateAttempt(CertificateRecord):
    email = models.ForeignKey(SelectionCertificateEmail, on_delete=models.PROTECT, related_name='attempts')
    number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=12)
    error_code = models.CharField(max_length=32, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['number']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['email', 'number'], name='certificate_attempt_unique')]
