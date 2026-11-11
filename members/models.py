from django.core.validators import MinValueValidator
from django.conf import settings
from django.db import models
from django.utils import timezone
from . import profile


class DisabilityType(models.Model):
    """Association-managed classifications; never inferred from legacy free text."""
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(default=True)
    from programs.terms import ProtectedReferenceQuerySet
    objects = ProtectedReferenceQuerySet.as_manager()

    def clean(self):
        super().clean()
        from ewaf.reference_invalidation import require_reference_writer
        require_reference_writer()
        from programs.terms import guard_reference, terms_lock
        with terms_lock():
            guard_reference(self)

    def save(self, *args, **kwargs):
        from ewaf.reference_invalidation import require_reference_writer
        require_reference_writer()
        from programs.terms import guard_reference, terms_lock
        with terms_lock():
            guard_reference(self)
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return type(self).objects.filter(pk=self.pk).delete()

    class Meta:
        ordering = ['name', 'pk']
        default_permissions = ('add', 'change', 'view')

    def __str__(self):
        return self.name


class PersonalRecord(models.Model):
    municipality = models.CharField(max_length=120, blank=True)
    barangay = models.CharField(max_length=120, blank=True)
    house_number = models.CharField(max_length=80, blank=True)
    street = models.CharField(max_length=200, blank=True)
    purok_zone = models.CharField('purok / zone', max_length=120, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    no_middle_name = models.BooleanField(default=False)
    last_name = models.CharField(max_length=100, blank=True)
    suffix = models.CharField(max_length=10, choices=profile.SUFFIXES, blank=True)
    suffix_other = models.CharField('custom suffix', max_length=30, blank=True)
    sex = models.CharField(max_length=10, choices=profile.SEX, blank=True)
    civil_status = models.CharField(max_length=15, choices=profile.CIVIL_STATUS, blank=True)
    disability_cause = models.CharField('cause of disability', max_length=15, choices=profile.CAUSE, blank=True)
    disability_visibility = models.CharField(max_length=15, choices=profile.VISIBILITY, blank=True)
    education = models.CharField('educational attainment', max_length=20, choices=profile.EDUCATION, blank=True)
    employment_status = models.CharField(max_length=20, choices=profile.EMPLOYMENT, blank=True)
    income_category = models.CharField(max_length=25, choices=profile.INCOME, blank=True)
    income_category_label = models.CharField(max_length=100, blank=True)
    disability_types = models.ManyToManyField(DisabilityType, blank=True, related_name='+')
    full_name = models.CharField(max_length=200)
    birthdate = models.DateField()
    address = models.TextField(max_length=1000)
    contact_number = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    control_number = models.CharField(max_length=100)
    disability_information = models.TextField(max_length=2000)
    disability_type = models.ForeignKey(DisabilityType, null=True, blank=True,
                                       on_delete=models.PROTECT, related_name='+')
    employment_information = models.CharField(max_length=200)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                         validators=[MinValueValidator(0)])
    dependents = models.PositiveSmallIntegerField(null=True, blank=True)
    household_monthly_income = models.DecimalField(max_digits=12, decimal_places=2,
        null=True, blank=True, validators=[MinValueValidator(0)])
    household_members = models.PositiveSmallIntegerField('number of household members',
        null=True, blank=True, validators=[MinValueValidator(1)])
    registration_profile = models.JSONField(default=dict, blank=True)

    class Meta:
        abstract = True

    @property
    def disability_ids(self):
        values = list(self.disability_types.order_by('pk').values_list('pk', flat=True)) if self.pk else []
        return values or ([self.disability_type_id] if self.disability_type_id else [])

    @property
    def disability_labels(self):
        return ', '.join(DisabilityType.objects.filter(pk__in=self.disability_ids).values_list('name', flat=True))


class Member(PersonalRecord):
    application = models.OneToOneField('membership.MembershipApplication',
                                      on_delete=models.PROTECT, related_name='member')
    control_number = models.CharField(max_length=100, unique=True)
    joined_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['full_name', 'pk']
        default_permissions = ('view', 'change')
        permissions = [('change_member_status', 'Can activate, deactivate, and archive members')]
        constraints = [models.CheckConstraint(condition=models.Q(archived_at__isnull=True) | models.Q(is_active=False),
                                               name='archived_member_is_inactive')]

    @property
    def status(self):
        return 'archived' if self.archived_at else ('active' if self.is_active else 'inactive')

    def __str__(self):
        return self.full_name


class MemberEvent(models.Model):
    member = models.ForeignKey(Member, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=150)
    action = models.CharField(max_length=40)
    notes = models.TextField(max_length=2000)
    changes = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)
    address = models.GenericIPAddressField(null=True, blank=True)

    @property
    def display_changes(self):
        fields = {field.name: field.verbose_name for field in Member._meta.fields}
        return [(fields.get(name, name.replace('_', ' ').title()),
                 change) for name, change in self.changes.items()]

    class Meta:
        ordering = ['-occurred_at', '-pk']
        default_permissions = ('view',)


from .review_models import InformationReview, InformationReviewAction  # noqa: E402,F401
from .document_models import MemberDocumentUpload  # noqa: E402,F401
from .update_models import (MemberUpdateWindow, MemberUpdateAccess, MemberUpdateRequest, MemberUpdateAction,
                           MemberUpdateEmail, MemberUpdateEmailAttempt)  # noqa: E402,F401
