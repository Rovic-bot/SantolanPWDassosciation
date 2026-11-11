"""Annual awareness content, independent of scheduled association Events."""
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .observances import CATEGORIES, ObservanceReference, validate_source_url


def observance_image_path(instance, filename):
    return f'annual-observances/{instance.pk}/{uuid.uuid4().hex}.png'


class ObservanceContent(models.Model):
    title = models.CharField(max_length=200)
    target_audience = models.TextField(max_length=1000, blank=True, verbose_name='Target Audience')
    who_may_participate = models.TextField(max_length=2000, blank=True, verbose_name='Who May Participate')
    month = models.PositiveSmallIntegerField()
    category = models.CharField(max_length=12, choices=list(CATEGORIES.items()), default='disability')
    recurrence_kind = models.CharField(max_length=16, choices=[
        ('whole_month', 'Whole month'), ('fixed_day', 'Fixed day'), ('fixed_range', 'Fixed date range'),
        ('last_monday', 'Last Monday'), ('third_week', 'Third week'), ('third_thursday', 'Third Thursday'),
    ])
    recurrence_rule = models.CharField(max_length=250, editable=False)
    day_start = models.PositiveSmallIntegerField(null=True, blank=True)
    day_end = models.PositiveSmallIntegerField(null=True, blank=True)
    legal_basis = models.CharField(max_length=250)
    source_url = models.URLField(max_length=1000, validators=[validate_source_url])
    description = models.TextField(max_length=2000)
    image = models.FileField(upload_to=observance_image_path, blank=True, max_length=250)
    image_alt = models.CharField(max_length=250, blank=True)

    class Meta:
        abstract = True

    def clean_fields(self, exclude=None):
        # The compact editor also creates Association-authored observances.
        # Neither a legal authority nor an official source is inferred. When
        # either is recorded, the existing complete-reference checks apply.
        excluded = set(exclude or ())
        if not self.legal_basis and not self.source_url:
            excluded.update(('legal_basis', 'source_url'))
        super().clean_fields(exclude=excluded)

    def clean(self):
        super().clean()
        reference = ObservanceReference(require_source=bool(self.legal_basis or self.source_url), **{name: getattr(self, name) for name in (
            'month', 'title', 'recurrence_kind', 'legal_basis', 'source_url', 'description',
            'category', 'day_start', 'day_end')})
        self.recurrence_rule = reference.recurrence_rule
        if self.image and not self.image_alt.strip():
            raise ValidationError({'image_alt': 'Describe the attached photo.'})
        if not self.image and self.image_alt:
            raise ValidationError({'image_alt': 'Attach a photo or clear its description.'})


class AnnualObservanceQuerySet(models.QuerySet):
    def public(self):
        return self.filter(status='published', published_at__lte=timezone.now())


class AnnualObservance(ObservanceContent):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    version = models.PositiveIntegerField(default=1, editable=False)
    published_at = models.DateTimeField(null=True, blank=True, editable=False)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+', editable=False)
    published_by_label = models.CharField(max_length=150, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='+')
    objects = AnnualObservanceQuerySet.as_manager()

    class Meta:
        ordering = ['month', 'title', 'pk']
        default_permissions = ('add', 'change', 'view')
        permissions = [('publish_annualobservance', 'Can publish, withdraw and archive annual observances')]
        indexes = [models.Index(fields=['status', 'month'], name='observance_public_month')]
        constraints = [
            models.CheckConstraint(condition=models.Q(month__range=(1, 12)), name='observance_month'),
            models.CheckConstraint(condition=models.Q(version__gte=1), name='observance_version'),
            models.CheckConstraint(condition=models.Q(category__in=['disability', 'health']), name='observance_category'),
            models.CheckConstraint(condition=models.Q(status__in=['draft', 'published', 'archived']), name='observance_status'),
            models.CheckConstraint(condition=(
                models.Q(status='published', published_at__isnull=False) & ~models.Q(published_by_label='')
                | models.Q(status__in=['draft', 'archived'], published_at__isnull=True,
                           published_by__isnull=True, published_by_label='')), name='observance_publication'),
            models.CheckConstraint(condition=(
                models.Q(recurrence_kind__in=['whole_month', 'last_monday', 'third_week', 'third_thursday'],
                         day_start__isnull=True, day_end__isnull=True)
                | models.Q(recurrence_kind='fixed_day', day_start__isnull=False,
                           day_start__range=(1, 31), day_end__isnull=True)
                | models.Q(recurrence_kind='fixed_range', day_start__isnull=False,
                           day_end__isnull=False, day_start__range=(1, 31), day_end__range=(1, 31),
                           day_end__gt=models.F('day_start'))), name='observance_recurrence'),
        ]

    def __str__(self):
        return self.title


class ImmutableObservanceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Observance history cannot be changed.')

    def delete(self):
        raise ValidationError('Observance history cannot be deleted.')

    def bulk_update(self, *args, **kwargs):
        raise ValidationError('Observance history cannot be changed.')


class ImmutableObservanceRecord(models.Model):
    objects = ImmutableObservanceQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Observance history cannot be changed.')
        # Force INSERT so a supplied historical primary key cannot overwrite history.
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Observance history cannot be deleted.')


class AnnualObservanceRevision(ObservanceContent, ImmutableObservanceRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    observance = models.ForeignKey(AnnualObservance, on_delete=models.PROTECT, related_name='revisions')
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=AnnualObservance.Status.choices)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by_label = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=20)
    reason = models.TextField(max_length=2000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version']
        default_permissions = ('view',)
        constraints = [models.UniqueConstraint(fields=['observance', 'version'], name='observance_revision_version')]


class AnnualObservanceLog(ImmutableObservanceRecord):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    observance = models.ForeignKey(AnnualObservance, on_delete=models.PROTECT, related_name='history')
    revision = models.OneToOneField(AnnualObservanceRevision, on_delete=models.PROTECT, related_name='audit')
    version = models.PositiveIntegerField()
    action = models.CharField(max_length=20)
    reason = models.TextField(max_length=2000)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    occurred_at = models.DateTimeField(auto_now_add=True)
    changes = models.JSONField(default=dict)
    address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-version']
        default_permissions = ('view',)
