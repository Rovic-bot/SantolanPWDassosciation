import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class EligibilityStatus(models.Model):
    class Code(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ELIGIBLE = 'eligible', 'Eligible'
        REVIEW = 'review', 'Review Needed'
        INELIGIBLE = 'ineligible', 'Not Eligible'

    code = models.CharField(max_length=12, primary_key=True, choices=Code.choices)
    label = models.CharField(max_length=80, unique=True)
    is_active = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['code']
        default_permissions = ('view', 'change')
        constraints = [models.CheckConstraint(condition=models.Q(code__in=['pending', 'eligible', 'review', 'ineligible']), name='eligibility_valid_code')]

    def __str__(self):
        return {'pending': 'Pending', 'eligible': 'Eligible', 'review': 'Needs Information', 'ineligible': 'Ineligible'}[self.code]


class AssistanceCase(models.Model):
    class Decision(models.TextChoices):
        PENDING = 'pending', 'Awaiting decision'
        APPROVED = 'approved', 'Selected'
        REJECTED = 'rejected', 'Not Selected'

    application = models.OneToOneField('programs.ProgramApplication', on_delete=models.PROTECT, related_name='assistance_case')
    eligibility = models.ForeignKey(EligibilityStatus, on_delete=models.PROTECT)
    eligibility_label = models.CharField(max_length=80)
    checklist = models.JSONField(default=list)
    review_notes = models.TextField(max_length=2000)
    reviewed_at = models.DateTimeField()
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    member_version = models.PositiveIntegerField()
    program_version = models.PositiveIntegerField()
    decision = models.CharField(max_length=10, choices=Decision.choices, default=Decision.PENDING)
    decision_notes = models.TextField(max_length=2000, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        default_permissions = ('view',)
        permissions = [('review_eligibility', 'Can assess program eligibility'),
                       ('decide_assistance', 'Can approve, reject or return assistance decisions')]
        constraints = [models.CheckConstraint(condition=models.Q(decision__in=['pending', 'approved', 'rejected']), name='assistance_valid_decision')]


class AssistanceReleaseQuerySet(models.QuerySet):
    def successful(self):
        return self.filter(voided_at__isnull=True)


class AssistanceRelease(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT, related_name='assistance_releases')
    # Nullable unique key permits retained voids and only one current successful release.
    active_application = models.OneToOneField('programs.ProgramApplication', null=True, blank=True, on_delete=models.PROTECT, related_name='+', editable=False)
    assistance_type = models.CharField(max_length=120)
    benefit = models.CharField(max_length=1000)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    released_on = models.DateField()
    reference = models.CharField(max_length=200, blank=True)
    notes = models.TextField(max_length=2000)
    approval_snapshot = models.JSONField(default=dict)
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    void_reason = models.TextField(max_length=2000, blank=True)
    objects = AssistanceReleaseQuerySet.as_manager()

    class Meta:
        ordering = ['-released_on', '-recorded_at', '-pk']
        default_permissions = ('view',)
        permissions = [('record_release', 'Can confirm successful assistance releases'),
                       ('void_release', 'Can void incorrect assistance releases')]
        constraints = [
            models.CheckConstraint(condition=models.Q(amount__isnull=True) | models.Q(amount__gte=0), name='release_nonnegative_amount'),
            models.CheckConstraint(condition=models.Q(estimated_value__isnull=True) | models.Q(estimated_value__gte=0), name='release_nonnegative_value'),
            models.CheckConstraint(condition=(models.Q(voided_at__isnull=True, active_application__isnull=False) & models.Q(active_application=models.F('application'))) | models.Q(voided_at__isnull=False, active_application__isnull=True), name='release_active_or_void'),
        ]


class AssistanceLog(models.Model):
    application = models.ForeignKey('programs.ProgramApplication', null=True, blank=True, on_delete=models.PROTECT, related_name='assistance_history')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=150)
    action = models.CharField(max_length=40)
    notes = models.TextField(max_length=2000)
    snapshot = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)
    address = models.GenericIPAddressField(null=True, blank=True)

    @property
    def action_label(self):
        return self.action.replace('_', ' ').capitalize()

    class Meta:
        ordering = ['-occurred_at', '-pk']
        default_permissions = ('view',)


from .referral_models import (ReferralGrant, ReferralTicket, ReferralAttachment,
    ReferralAction, ReferralEmail, ReferralEmailAttempt, ReferralWindow, ReferralSettings, ReferralSettingsEvent)  # noqa: F401,E402
