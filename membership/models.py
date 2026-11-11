import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from members.models import PersonalRecord
from core.reference_services import ShortReferenceMixin


def validate_registry_url(value):
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or parsed.username or parsed.password or not parsed.hostname:
        raise ValidationError('Use an HTTPS website address without embedded credentials.')


class MembershipSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    registration_open = models.BooleanField(default=False)
    prpwd_url = models.URLField(max_length=500, blank=True, validators=[validate_registry_url],
        help_text='Official PRPWD verification website. Opens a link only; no applicant data is sent automatically.')

    class Meta:
        verbose_name_plural = 'membership settings'
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name='membership_settings_singleton')]

    def clean(self):
        if self.registration_open and not self.prpwd_url:
            raise ValidationError({'prpwd_url': 'Set the official verification link before opening registration.'})

    def __str__(self):
        return 'Membership registration settings'


class MembershipApplication(ShortReferenceMixin, PersonalRecord):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    submission_key = models.UUIDField(unique=True, editable=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    requirements_snapshot = models.JSONField(default=list)
    prpwd_verified = models.BooleanField(null=True, default=None)
    prpwd_verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='verified_membership_applications')
    prpwd_verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(max_length=2000, blank=True)
    verification_url = models.URLField(max_length=500, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='decided_membership_applications')
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(max_length=2000, blank=True)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-submitted_at', '-pk']
        default_permissions = ('view',)
        permissions = [
            ('encode_membershipapplication', 'Can encode onsite membership registrations'),
            ('verify_membershipapplication', 'Can record manual PRPWD verification'),
            ('decide_membershipapplication', 'Can approve or reject membership applications'),
        ]
        constraints = [models.CheckConstraint(condition=models.Q(status__in=['pending', 'approved', 'rejected']),
                                              name='membership_valid_status')]

    def __str__(self):
        return str(self.reference)


class MembershipEvent(models.Model):
    application = models.ForeignKey(MembershipApplication, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=40)
    description = models.CharField(max_length=250)
    occurred_at = models.DateTimeField(auto_now_add=True)
    address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['occurred_at', 'pk']
        default_permissions = ('view',)


class SubmissionWindow(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    started_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        default_permissions = ()


# Additive pending intake; the established membership models above stay unchanged.
from .registration_models import (RegistrationSubmissionContext, RegistrationIntake,
    RegistrationRevision, RegistrationAttachment, RegistrationAction)
from .pdao_models import PDAORegistration, PDAORegistrationEvent, PDAORegistrationRevision
from .approval_email_models import MembershipApprovalEmail, MembershipApprovalEmailAttempt
from .pending_email_models import MembershipPendingEmail, MembershipPendingEmailAttempt
from .pdao_email_models import PDAOReviewEmail, PDAOReviewEmailAttempt
