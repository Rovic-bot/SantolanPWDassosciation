import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


def announcement_image_path(instance, filename):
    return f'announcements/{instance.pk}/{uuid.uuid4().hex}.png'


class AnnouncementQuerySet(models.QuerySet):
    def published(self):
        from .results import results_current
        candidates = self.filter(status='published', published_at__lte=timezone.now())
        # Every public consumer uses this gate, including homepage, lists and images.
        valid = [item.pk for item in candidates.filter(program__isnull=False,
                 result_revision__isnull=False).select_related('program', 'result_revision')
                 if results_current(item)]
        from .notices import announced_public_programs
        return candidates.filter(
            models.Q(program__isnull=True, linked_program__isnull=True)
            | models.Q(program__isnull=True, linked_program__in=announced_public_programs())
            | models.Q(pk__in=valid, linked_program__isnull=True))

    def in_category(self, category):
        if category == 'general':
            return self.filter(program__isnull=True, linked_program__isnull=True)
        if category == 'programs':
            return self.filter(program__isnull=True, linked_program__isnull=False)
        if category == 'results':
            return self.filter(program__isnull=False, linked_program__isnull=True)
        return self


class Announcement(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'
        ARCHIVED = 'archived', 'Archived'
        DELETED = 'deleted', 'Deleted'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    content = models.TextField(max_length=20000)
    source_office = models.CharField(max_length=200, blank=True)
    linked_program = models.ForeignKey('programs.Program', null=True, blank=True,
        on_delete=models.PROTECT, related_name='information_announcements')
    image = models.FileField(upload_to=announcement_image_path, blank=True, max_length=250)
    image_alt = models.CharField(max_length=250, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name='created_announcements')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL,
                                   related_name='updated_announcements')
    version = models.PositiveIntegerField(default=0)
    program = models.OneToOneField('programs.Program', null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='applicant_announcement')
    applicant_rows = models.JSONField(default=list, blank=True)
    result_revision = models.ForeignKey('ProgramResultRevision', null=True, blank=True,
        on_delete=models.PROTECT, related_name='+', editable=False)
    objects = AnnouncementQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at', '-pk']
        permissions = [('publish_announcement', 'Can publish and withdraw announcements')]
        constraints = [
            models.CheckConstraint(condition=models.Q(status__in=['draft', 'published', 'archived', 'deleted']),
                                   name='announcement_valid_status'),
            models.CheckConstraint(condition=~models.Q(status='published') | models.Q(published_at__isnull=False),
                                   name='published_announcement_has_date'),
            models.CheckConstraint(condition=models.Q(program__isnull=True) | models.Q(linked_program__isnull=True),
                                   name='announcement_single_program_link'),
        ]

    @property
    def category(self):
        return 'results' if self.program_id else 'programs' if self.linked_program_id else 'general'

    @property
    def category_label(self):
        return dict(NOTICE_CATEGORIES)[self.category]

    @property
    def display_title(self):
        return self.linked_program.name if self.linked_program_id else self.title

    def __str__(self):
        return self.title


NOTICE_CATEGORIES = (('general', 'General'), ('programs', 'Programs'), ('results', 'Program Results'))


class AnnouncementEvent(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    actor_label = models.CharField(max_length=150)
    action = models.CharField(max_length=30)
    description = models.CharField(max_length=500)
    occurred_at = models.DateTimeField(auto_now_add=True)
    address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-occurred_at', '-pk']
        default_permissions = ('view',)


class ProgramResultRevision(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.PROTECT, related_name='result_revisions')
    number = models.PositiveIntegerField()
    public_payload = models.JSONField(editable=False)
    previous_announcement = models.JSONField(default=dict, editable=False)
    source_digest = models.CharField(max_length=64, editable=False)
    reason = models.TextField(max_length=2000)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    creator_label = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-number']
        default_permissions = ('view',)
        constraints = [models.UniqueConstraint(fields=['announcement', 'number'], name='unique_result_revision')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            from django.core.exceptions import ValidationError
            raise ValidationError('Result revisions are immutable. Prepare a new reviewed revision.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('Result history must be preserved.')


from .certificate_models import SelectionCertificateEmail, SelectionCertificateAttempt  # noqa: E402,F401
