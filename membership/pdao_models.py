"""Private PDAO intake, claimed IDs and optional Association registration links."""
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone
from core.reference_services import ShortReferenceMixin

from .registration_models import RegistrationRecord


class PDAORegistration(ShortReferenceMixin, RegistrationRecord):
    class Status(models.TextChoices):
        RECEIVED = 'received', 'Received'
        NEEDS_INFO = 'needs_info', 'Needs information'
        READY = 'ready', 'Ready to forward'
        FORWARDED = 'forwarded', 'Forwarded to PDAO'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submission_key = models.UUIDField(unique=True, editable=False)
    data = models.JSONField(editable=False)
    payload_digest = models.CharField(max_length=64, editable=False)
    privacy_version = models.CharField(max_length=50, editable=False)
    binding_digest = models.CharField(max_length=64, editable=False)
    receipt_expires_at = models.DateTimeField(editable=False)
    receipt_revoked_at = models.DateTimeField(null=True, editable=False)
    received_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.RECEIVED)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-received_at', 'pk']
        default_permissions = ('add', 'view')
        permissions = [
            ('print_pdaoregistration', 'Can print private PDAO registrations'),
            ('forward_pdaoregistration', 'Can prepare and record manual PDAO forwarding'),
            ('correct_pdaoregistration', 'Can correct PDAO details during review'),
        ]
        constraints = [models.CheckConstraint(condition=models.Q(status__in=['received', 'needs_info', 'ready', 'forwarded']),
                                              name='pdao_registration_status')]

    @property
    def reference(self):
        return f'PDAO-{self.pk}'

    @property
    def current_data(self):
        if hasattr(self, '_review_data'):
            return self._review_data
        return self.revisions.order_by('-version').values_list('data', flat=True).first() or self.data

    def save(self, *args, **kwargs):
        if not self._state.adding and (not kwargs.get('update_fields') or
                set(kwargs['update_fields']) - {'status', 'version', 'receipt_revoked_at'}):
            raise PermissionDenied('The original PDAO submission is immutable.')
        return super().save(*args, **kwargs)


class PDAORegistrationEvent(RegistrationRecord):
    append_only = True
    registration = models.ForeignKey(PDAORegistration, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=32, choices=[
        ('submitted', 'Application submitted'), ('details_viewed', 'Application reviewed'),
        ('print_viewed', 'Printable form opened'), ('ready', 'Marked ready to forward'),
        ('forwarded', 'Forwarding to PDAO recorded'), ('corrected', 'Reviewed details saved'),
        ('onsite_submitted', 'Onsite PDAO application recorded'),
        ('needs_info', 'More information requested'),
        ('email_retry', 'Review email retried'),
        ('claim_notice_queued', 'PWD ID claim notice requested'),
        ('id_claimed', 'PWD ID claimed'),
        ('membership_started', 'Association membership application started'),
    ])
    details = models.JSONField(default=dict, editable=False)
    occurred_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField()

    class Meta:
        ordering = ['occurred_at', 'pk']
        default_permissions = ()


class PDAORegistrationRevision(RegistrationRecord):
    append_only = True
    registration = models.ForeignKey(PDAORegistration, on_delete=models.PROTECT, related_name='revisions')
    version = models.PositiveIntegerField()
    data = models.JSONField(editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['registration', 'version'], name='pdao_review_version')]


class PDAOIDClaim(RegistrationRecord):
    registration = models.OneToOneField(PDAORegistration, on_delete=models.PROTECT,
        primary_key=True, related_name='id_claim')
    pwd_number = models.CharField(max_length=80)
    claimed_at = models.DateTimeField(default=timezone.now, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    membership_intake = models.OneToOneField('membership.RegistrationIntake', null=True, blank=True,
        on_delete=models.PROTECT, related_name='pdao_claim')
    membership_started_at = models.DateTimeField(null=True, blank=True, editable=False)
    membership_started_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.PROTECT, related_name='+')

    class Meta:
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=(
            models.Q(membership_intake__isnull=True, membership_started_at__isnull=True, membership_started_by__isnull=True)
            | models.Q(membership_intake__isnull=False, membership_started_at__isnull=False, membership_started_by__isnull=False)),
            name='pdao_membership_link_complete')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            fields = {'membership_intake', 'membership_started_at', 'membership_started_by'}
            if (set(kwargs.get('update_fields') or ()) != fields
                    or type(self).objects.filter(pk=self.pk, membership_intake__isnull=False).exists()):
                raise PermissionDenied('Claim records and completed membership links must be preserved.')
        return super().save(*args, **kwargs)
