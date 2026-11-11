"""Private, retained member update requests and their verification evidence."""
from contextlib import contextmanager
from contextvars import ContextVar
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models

_writing = ContextVar('member_update_writer', default=False)


@contextmanager
def update_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


class UpdateQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Use the member update service.')

    def delete(self):
        raise PermissionDenied('Member update history must be retained.')

    def bulk_create(self, *args, **kwargs):
        raise PermissionDenied('Use the member update service.')

    def bulk_update(self, *args, **kwargs):
        raise PermissionDenied('Use the member update service.')


class UpdateRecord(models.Model):
    objects = UpdateQuerySet.as_manager()
    mutable_fields = frozenset()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not _writing.get():
            raise PermissionDenied('Use the member update service.')
        if not self._state.adding:
            fields = kwargs.get('update_fields')
            if not fields or not set(fields).issubset(self.mutable_fields):
                raise PermissionDenied('Original member update information must be retained.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Member update history must be retained.')


class MemberUpdateWindow(models.Model):
    key = models.CharField(primary_key=True, max_length=64)
    started_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        default_permissions = ()


class MemberUpdateAccess(UpdateRecord):
    mutable_fields = frozenset({'attempts', 'verified_at', 'access_expires_at', 'submitted_at'})
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey('members.Member', null=True, on_delete=models.PROTECT, related_name='+')
    member_version = models.PositiveIntegerField(null=True)
    session_digest = models.CharField(max_length=64)
    code_digest = models.CharField(max_length=64)
    recipient = models.EmailField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True)
    access_expires_at = models.DateTimeField(null=True)
    submitted_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()


class MemberUpdateRequest(UpdateRecord):
    STATES = [('submitted', 'Update needed'), ('invited', 'Update needed'),
              ('needs_verification', 'Needs verification'), ('approved', 'Approved')]
    OPEN_STATES = ('submitted', 'invited', 'needs_verification')
    mutable_fields = frozenset({'state', 'version', 'approved_at', 'approved_by'})
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access = models.OneToOneField(MemberUpdateAccess, on_delete=models.PROTECT, related_name='update_request')
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='update_requests')
    member_version = models.PositiveIntegerField()
    previous_values = models.JSONField()
    proposed_values = models.JSONField()
    changed_fields = models.JSONField()
    state = models.CharField(max_length=24, choices=STATES, default='submitted', db_index=True)
    version = models.PositiveIntegerField(default=0)
    submitted_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')

    class Meta:
        default_permissions = ()
        ordering = ['-submitted_at', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(state__in=['submitted', 'invited', 'needs_verification', 'approved']), name='member_update_state')]


class MemberUpdateAction(UpdateRecord):
    request = models.ForeignKey(MemberUpdateRequest, on_delete=models.PROTECT, related_name='actions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    action = models.CharField(max_length=40)
    reason = models.TextField(max_length=2000)
    before = models.CharField(max_length=24, blank=True)
    after = models.CharField(max_length=24)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ['created_at', 'pk']


class MemberUpdateEmail(UpdateRecord):
    mutable_fields = frozenset({'state', 'attempt_count', 'last_attempt_at', 'accepted_at', 'backend', 'sender'})
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    access = models.OneToOneField(MemberUpdateAccess, null=True, on_delete=models.PROTECT, related_name='email')
    request = models.OneToOneField(MemberUpdateRequest, null=True, on_delete=models.PROTECT, related_name='invitation')
    recipient = models.EmailField()
    sender = models.EmailField(blank=True)
    subject = models.CharField(max_length=250)
    body = models.TextField()
    state = models.CharField(max_length=12, default='queued', choices=[
        ('queued', 'Email queued'), ('sending', 'Sending — confirmation pending'),
        ('sent', 'Email accepted'), ('failed', 'Email could not be sent'),
        ('uncertain', 'Email delivery is unconfirmed'), ('cancelled', 'Email expired or cancelled')])
    attempt_count = models.PositiveIntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True)
    accepted_at = models.DateTimeField(null=True)
    backend = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=(models.Q(access__isnull=False, request__isnull=True) |
            models.Q(access__isnull=True, request__isnull=False)), name='member_update_email_scope')]


class MemberUpdateEmailAttempt(UpdateRecord):
    email = models.ForeignKey(MemberUpdateEmail, on_delete=models.PROTECT, related_name='attempts')
    number = models.PositiveIntegerField()
    outcome = models.CharField(max_length=12, choices=[('accepted', 'Accepted'), ('failed', 'Failed'), ('uncertain', 'Unconfirmed')])
    error_type = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['email', 'number'], name='member_update_email_attempt')]
