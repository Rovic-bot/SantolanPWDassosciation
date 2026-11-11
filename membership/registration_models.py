"""Additive pending Association intake. No official-member or EWAF writes."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from core.reference_services import ShortReferenceMixin

_writing = ContextVar('association_registration_writer', default=False)


@contextmanager
def registration_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


class RegistrationQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Use the registration service.')

    def delete(self):
        raise PermissionDenied('Registration disposal requires a separate approved procedure.')

    def bulk_create(self, *args, **kwargs):
        raise PermissionDenied('Use the registration service.')

    def bulk_update(self, *args, **kwargs):
        raise PermissionDenied('Use the registration service.')


class RegistrationRecord(models.Model):
    objects = RegistrationQuerySet.as_manager()
    append_only = False

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not _writing.get() or (self.append_only and not self._state.adding):
            raise PermissionDenied('Use an append-only registration service operation.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Registration disposal requires a separate approved procedure.')


class RegistrationSubmissionContext(RegistrationRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    binding_digest = models.CharField(max_length=64, editable=False)
    policy_digest = models.CharField(max_length=64, editable=False)
    channel = models.CharField(max_length=16, choices=[('online', 'Online'), ('printed', 'Printed'), ('walk_in', 'Walk-in')])
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.CheckConstraint(condition=models.Q(channel__in=['online', 'printed', 'walk_in']), name='reg_context_channel'),
            models.CheckConstraint(condition=(models.Q(channel='online', actor__isnull=True) |
                models.Q(channel__in=['printed', 'walk_in'], actor__isnull=False)), name='reg_context_actor'),
            models.CheckConstraint(condition=models.Q(expires_at__gt=models.F('issued_at')), name='reg_context_expiry'),
        ]


class RegistrationIntake(ShortReferenceMixin, RegistrationRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=16, default='association', editable=False)
    reference = models.CharField(max_length=40, unique=True, editable=False)
    context = models.OneToOneField(RegistrationSubmissionContext, on_delete=models.PROTECT, related_name='intake')
    request_key = models.UUIDField(unique=True, editable=False)
    payload_digest = models.CharField(max_length=64, editable=False)
    channel = models.CharField(max_length=16, choices=[('online', 'Online'), ('printed', 'Printed'), ('walk_in', 'Walk-in')])
    state = models.CharField(max_length=32, default='received', choices=[
        ('received', 'Received'), ('under_review', 'Under review'), ('needs_information', 'Needs information'),
        ('ready_for_onsite', 'Ready for onsite verification'), ('onsite_review', 'Onsite findings recorded'),
        ('membership_review', 'Membership review')])
    version = models.PositiveIntegerField(default=0)
    current_revision = models.PositiveIntegerField(default=1)
    policy_snapshot = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    membership_application = models.OneToOneField('membership.MembershipApplication', null=True, blank=True,
        on_delete=models.PROTECT, related_name='registration_intake')

    class Meta:
        ordering = ['-received_at', '-pk']
        default_permissions = ('view',)
        permissions = [
            ('encode_registrationintake', 'Can encode pending Association intake'),
            ('review_registrationintake', 'Can review pending Association intake'),
            ('correct_registrationintake', 'Can append pending Association corrections'),
            ('onsite_registrationintake', 'Can record authorized Association onsite findings'),
            ('view_registration_documents', 'Can retrieve private Association intake attachments'),
        ]
        indexes = [models.Index(fields=['category', 'state', 'received_at'], name='reg_inbox_state_date')]
        constraints = [
            models.CheckConstraint(condition=models.Q(category='association'), name='reg_association_only'),
            models.CheckConstraint(condition=(models.Q(membership_application__isnull=False, state='membership_review') |
                (models.Q(membership_application__isnull=True) & ~models.Q(state='membership_review'))), name='reg_handoff_link_state'),
            models.CheckConstraint(condition=models.Q(channel__in=['online', 'printed', 'walk_in']), name='reg_intake_channel'),
            models.CheckConstraint(condition=models.Q(state__in=['received', 'under_review', 'needs_information',
                'ready_for_onsite', 'onsite_review', 'membership_review']), name='reg_pending_states'),
            models.CheckConstraint(condition=models.Q(current_revision__gte=1), name='reg_revision_positive'),
        ]


class RegistrationRevision(RegistrationRecord):
    append_only = True
    intake = models.ForeignKey(RegistrationIntake, on_delete=models.PROTECT, related_name='revisions')
    number = models.PositiveIntegerField()
    predecessor = models.ForeignKey('self', null=True, on_delete=models.PROTECT, related_name='+')
    schema_version = models.PositiveSmallIntegerField(default=1)
    data = models.JSONField()
    policy_snapshot = models.JSONField()
    retained_attachment_ids = models.JSONField(default=list)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    actor_label = models.CharField(max_length=150, blank=True)
    context = models.ForeignKey(RegistrationSubmissionContext, null=True, on_delete=models.PROTECT, related_name='+')
    reason = models.CharField(max_length=2000, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ['number']
        constraints = [models.UniqueConstraint(fields=['intake', 'number'], name='reg_unique_revision'),
            models.CheckConstraint(condition=models.Q(number__gte=1), name='reg_revision_number_positive')]


def registration_file_path(instance, filename):
    return f'registration/{instance.revision.intake_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class RegistrationAttachment(RegistrationRecord):
    append_only = True
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    revision = models.ForeignKey(RegistrationRevision, on_delete=models.PROTECT, related_name='attachments')
    slot = models.CharField(max_length=32)
    alternative = models.CharField(max_length=32, blank=True)
    file = models.FileField(upload_to=registration_file_path, max_length=250)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    digest = models.CharField(max_length=64)
    predecessor = models.ForeignKey('self', null=True, on_delete=models.PROTECT, related_name='+')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['revision', 'slot'], name='reg_unique_upload_slot')]


class RegistrationAction(RegistrationRecord):
    append_only = True
    intake = models.ForeignKey(RegistrationIntake, on_delete=models.PROTECT, related_name='actions')
    action = models.CharField(max_length=48)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    actor_label = models.CharField(max_length=150, blank=True)
    context = models.ForeignKey(RegistrationSubmissionContext, null=True, on_delete=models.PROTECT, related_name='+')
    revision = models.ForeignKey(RegistrationRevision, on_delete=models.PROTECT, related_name='+')
    version_before = models.PositiveIntegerField()
    version_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=2000, blank=True)
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ['occurred_at', 'pk']
