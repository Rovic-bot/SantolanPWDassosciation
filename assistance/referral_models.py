"""Private member-service tickets, independent of program assistance and releases."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from core.reference_services import ShortReferenceMixin

_writing = ContextVar('referral_writer', default=False)


@contextmanager
def referral_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


class ReferralQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Use the referral service.')

    def delete(self):
        raise PermissionDenied('Ticket disposal requires an authorized retention procedure.')

    def bulk_create(self, *args, **kwargs):
        raise PermissionDenied('Use the referral service.')

    def bulk_update(self, *args, **kwargs):
        raise PermissionDenied('Use the referral service.')


class ReferralRecord(models.Model):
    objects = ReferralQuerySet.as_manager()
    append_only = False
    mutable_fields = frozenset()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not _writing.get() or (self.append_only and not self._state.adding):
            raise PermissionDenied('Use the audited referral service.')
        if not self._state.adding:
            fields = kwargs.get('update_fields')
            if not fields or not set(fields).issubset(self.mutable_fields):
                raise PermissionDenied('Submitted details and issued references are immutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Ticket disposal requires an authorized retention procedure.')


class ReferralGrant(ReferralRecord):
    mutable_fields = frozenset({'revoked_at'})
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='+')
    binding_digest = models.CharField(max_length=64)
    source_digest = models.CharField(max_length=64)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        default_permissions = ()


class ReferralSettings(ReferralRecord):
    mutable_fields = frozenset({'sender_email', 'version', 'gmail_password_encrypted'})
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    sender_email = models.EmailField()
    version = models.PositiveIntegerField(default=0)
    gmail_password_encrypted = models.TextField(blank=True, default='', editable=False)

    class Meta:
        default_permissions = ()
        permissions = [('configure_referrals', 'Can configure the Association referral email address')]
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='referral_settings_singleton')]


class ReferralSettingsEvent(ReferralRecord):
    append_only = True
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    before = models.EmailField(blank=True)
    after = models.EmailField()
    version = models.PositiveIntegerField(unique=True)
    reason = models.TextField(max_length=2000)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']
        default_permissions = ()


class ReferralTicket(ShortReferenceMixin, ReferralRecord):
    mutable_fields = frozenset({'status', 'version'})
    class Status(models.TextChoices):
        RECEIVED = 'received', 'Received'
        REVIEW = 'in_review', 'In review'
        INFORMATION = 'needs_information', 'Needs information'
        REFERRED = 'referred', 'Referred'
        CLOSED = 'closed', 'Closed'

    class Kind(models.TextChoices):
        FINANCIAL = 'financial', 'Financial'
        EDUCATIONAL = 'educational', 'Educational'
        MEDICAL = 'medical', 'Medical'
        OTHER = 'other', 'Other assistance or referral'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=40, unique=True, editable=False)
    grant = models.OneToOneField(ReferralGrant, on_delete=models.PROTECT, related_name='ticket')
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='referral_tickets')
    full_name = models.CharField(max_length=200)
    address = models.TextField(max_length=1000)
    contact_number = models.CharField(max_length=30)
    email = models.EmailField()
    # Earlier tickets retain an empty subject; new requests require it in the form.
    subject = models.CharField(max_length=200, blank=True, default='')
    assistance_type = models.CharField(max_length=16, choices=Kind.choices)
    concern = models.TextField(max_length=6000)
    acknowledgement = models.BooleanField(default=False)
    submission_digest = models.CharField(max_length=64, editable=False)
    member_snapshot = models.JSONField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    version = models.PositiveIntegerField(default=0)
    received_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-received_at', '-pk']
        default_permissions = ('view',)
        permissions = [('review_referralticket', 'Can review assistance and referral tickets'),
            ('view_referral_documents', 'Can view private referral evidence'),
            ('send_referral_email', 'Can send referral updates and retry acknowledgment email')]
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=['received', 'in_review', 'needs_information', 'referred', 'closed']), name='referral_valid_status'),
            models.CheckConstraint(condition=models.Q(assistance_type__in=['financial', 'educational', 'medical', 'other']), name='referral_valid_kind'),
            models.CheckConstraint(condition=models.Q(acknowledgement=True), name='referral_acknowledged'),
        ]


def referral_path(instance, filename):
    return f'private/referrals/{instance.ticket_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class ReferralAttachment(ReferralRecord):
    append_only = True
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(ReferralTicket, on_delete=models.PROTECT, related_name='attachments')
    file = models.FileField(upload_to=referral_path, max_length=255)
    label = models.CharField(max_length=200)
    content_type = models.CharField(max_length=80)
    size = models.PositiveIntegerField()
    sha256 = models.CharField(max_length=64)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()


class ReferralAction(ReferralRecord):
    append_only = True
    ticket = models.ForeignKey(ReferralTicket, on_delete=models.PROTECT, related_name='actions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=32)
    status_before = models.CharField(max_length=20, blank=True)
    status_after = models.CharField(max_length=20)
    version = models.PositiveIntegerField()
    channel = models.CharField(max_length=12, choices=[('online', 'Online'), ('email', 'Email'), ('onsite', 'Onsite'), ('internal', 'Internal')])
    notes = models.TextField(max_length=2000)
    member_message = models.TextField(max_length=4000, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['recorded_at', 'pk']
        default_permissions = ()


class ReferralEmail(ReferralRecord):
    mutable_fields = frozenset({'state', 'attempt_count', 'last_attempt_at', 'accepted_at', 'backend'})
    class State(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        SENDING = 'sending', 'Sending — confirmation pending'
        SENT = 'sent', 'Accepted by email service'
        FAILED = 'failed', 'Attempt failed — review before retry'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(ReferralTicket, on_delete=models.PROTECT, related_name='emails')
    action = models.OneToOneField(ReferralAction, on_delete=models.PROTECT, related_name='email')
    recipient = models.EmailField()
    sender = models.EmailField()
    subject = models.CharField(max_length=200)
    body = models.TextField()
    state = models.CharField(max_length=12, choices=State.choices, default=State.QUEUED, db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    backend = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-pk']
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=models.Q(state__in=['queued', 'sending', 'sent', 'failed']), name='referral_email_state')]


class ReferralEmailAttempt(ReferralRecord):
    append_only = True
    email = models.ForeignKey(ReferralEmail, on_delete=models.PROTECT, related_name='attempts')
    number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=12, choices=[('accepted', 'Accepted'), ('failed', 'Failed')])
    # No SMTP response bodies: those can contain addresses and secrets.
    error_type = models.CharField(max_length=100, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['number']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['email', 'number'], name='referral_email_attempt_unique')]


class ReferralWindow(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    started_at = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        default_permissions = ()
