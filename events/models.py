import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from core.reference_services import ShortReferenceMixin
from django.utils import timezone
from .participation import EVENT_CATEGORIES


def event_image_path(instance, filename):
    return f'events/{instance.pk}/{uuid.uuid4().hex}.png'


class EventQuerySet(models.QuerySet):
    def public(self):
        return self.filter(status__in=['published', 'cancelled'], published_at__lte=timezone.now())


class Event(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        CANCELLED = 'cancelled', 'Cancelled'
        ARCHIVED = 'archived', 'Archived'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    event_category = models.CharField(max_length=12, choices=EVENT_CATEGORIES, blank=True, default='')
    target_audience = models.TextField(max_length=1000, blank=True, verbose_name='Target Audience')
    who_may_participate = models.TextField(max_length=2000, blank=True, verbose_name='Who May Participate')
    application_program = models.OneToOneField('programs.Program', null=True, blank=True, on_delete=models.PROTECT, related_name='organizational_event',
        help_text='Use this Program Application context for verified-member event applications.')
    description = models.TextField(max_length=20000)
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField()
    location = models.CharField(max_length=500)
    registration_opens_at = models.DateTimeField(null=True, blank=True)
    registration_closes_at = models.DateTimeField(null=True, blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)])
    image = models.FileField(upload_to=event_image_path, blank=True, max_length=250)
    image_alt = models.CharField(max_length=250, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='created_events')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='updated_events')
    version = models.PositiveIntegerField(default=0)
    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ['-starts_at', '-pk']
        default_permissions = ('add', 'change', 'view')
        permissions = [('publish_event', 'Can publish, withdraw, cancel and archive events')]
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=['draft', 'published', 'cancelled', 'archived']), name='event_valid_status'),
            models.CheckConstraint(condition=~models.Q(status__in=['published', 'cancelled']) | models.Q(published_at__isnull=False), name='public_event_has_date'),
            models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='event_end_after_start'),
            models.CheckConstraint(condition=models.Q(registration_closes_at__gt=models.F('registration_opens_at')), name='event_registration_order'),
            models.CheckConstraint(condition=models.Q(capacity__isnull=True) | models.Q(capacity__gte=1), name='event_positive_capacity'),
            models.CheckConstraint(condition=models.Q(event_category__in=['', 'general', 'specific']), name='event_public_category'),
        ]

    def clean(self):
        errors = {}
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            errors['ends_at'] = 'End time must be after the start time.'
        if self.registration_opens_at and self.registration_closes_at and self.registration_closes_at <= self.registration_opens_at:
            errors['registration_closes_at'] = 'Registration must close after it opens.'
        if errors:
            raise ValidationError(errors)

    @property
    def image_description(self):
        return self.image_alt.strip() or f'Event image for {self.title}'

    @property
    def registration_available(self):
        return False  # Historical registrations remain; new public registration is retired.


    def __str__(self):
        return self.title


class EventLog(models.Model):
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='history')
    registration = models.ForeignKey('EventRegistration', null=True, blank=True, on_delete=models.PROTECT, related_name='history')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=40)
    notes = models.TextField(max_length=2000)
    changes = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)
    address = models.GenericIPAddressField(null=True, blank=True)

    @property
    def display_changes(self):
        return [(Event._meta.get_field(name).verbose_name, change) for name, change in self.changes.items()]

    class Meta:
        ordering = ['-occurred_at', '-pk']
        default_permissions = ('view',)


class EventRegistration(ShortReferenceMixin, models.Model):
    class Status(models.TextChoices):
        REGISTERED = 'registered', 'Registered'
        CONFIRMED = 'confirmed', 'Confirmed'
        ATTENDED = 'attended', 'Attended'
        ABSENT = 'absent', 'Absent'
        CANCELLED = 'cancelled', 'Cancelled'

    reference = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='registrations')
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='event_registrations')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REGISTERED, db_index=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['registered_at', 'pk']
        default_permissions = ('view', 'change')
        constraints = [
            models.UniqueConstraint(fields=['event', 'member'], name='one_registration_per_event_member'),
            models.CheckConstraint(condition=models.Q(status__in=['registered', 'confirmed', 'attended', 'absent', 'cancelled']), name='event_registration_valid_status'),
        ]


class EventAttendance(ShortReferenceMixin, models.Model):
    class Status(models.TextChoices):
        ATTENDED = 'attended', 'Attended'
        ABSENT = 'absent', 'Absent'

    reference = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name='attendance')
    attendee_name = models.CharField(max_length=200)
    member = models.ForeignKey('members.Member', null=True, blank=True, on_delete=models.PROTECT,
                               related_name='event_attendance')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ATTENDED, db_index=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['recorded_at', 'pk']
        default_permissions = ('add', 'change', 'view')
        constraints = [models.CheckConstraint(condition=models.Q(status__in=['attended', 'absent']),
                                              name='open_attendance_valid_status')]


class EventAttendanceLog(models.Model):
    attendance = models.ForeignKey(EventAttendance, on_delete=models.PROTECT, related_name='history')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=150)
    action = models.CharField(max_length=40)
    notes = models.TextField(max_length=2000)
    changes = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)
    address = models.GenericIPAddressField(null=True, blank=True)

    @property
    def display_changes(self):
        return [(EventAttendance._meta.get_field(name).verbose_name, change)
                for name, change in self.changes.items()]

    class Meta:
        ordering = ['-occurred_at', '-pk']
        default_permissions = ('view',)


class VerificationWindow(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    started_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveIntegerField(default=0)

    class Meta:
        default_permissions = ()


# Dedicated annual content; scheduled Event and attendance models remain unchanged.
from .observance_models import AnnualObservance, AnnualObservanceRevision, AnnualObservanceLog  # noqa: E402,F401
