from pathlib import Path
import uuid

from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class DocumentType(models.Model):
    name = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=500, blank=True)
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

    def __str__(self):
        return self.name


class MembershipDocumentRequirement(models.Model):
    capture_key = models.CharField(max_length=30, null=True, blank=True, unique=True, editable=False,
        help_text='Stable onsite upload slot. Existing Association requirements remain separate.')
    document_type = models.OneToOneField(DocumentType, on_delete=models.PROTECT)
    is_active = models.BooleanField(default=True)
    is_required = models.BooleanField(default=True)
    instructions = models.CharField(max_length=500, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['position', 'pk']

    def __str__(self):
        return str(self.document_type)

    def clean(self):
        if self.is_active and type(self).objects.filter(is_active=True).exclude(pk=self.pk).count() >= settings.DATA_UPLOAD_MAX_NUMBER_FILES:
            raise ValidationError('The active requirement count exceeds the configured upload limit. Deactivate another requirement first.')


def private_document_path(instance, filename):
    return f'membership/{instance.application.reference}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class MembershipApplicationDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey('membership.MembershipApplication', on_delete=models.PROTECT,
                                   related_name='documents')
    requirement = models.ForeignKey(MembershipDocumentRequirement, on_delete=models.PROTECT)
    label = models.CharField(max_length=120)
    file = models.FileField(upload_to=private_document_path, max_length=250)
    content_type = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ('view',)
        constraints = [models.UniqueConstraint(fields=['application', 'requirement'],
                                              name='one_document_per_application_requirement')]


class DocumentVerification(models.Model):
    document = models.ForeignKey(MembershipApplicationDocument, on_delete=models.PROTECT, related_name='verifications')
    verified = models.BooleanField()
    expires_on = models.DateField(null=True, blank=True)
    member_version = models.PositiveIntegerField()
    file_digest = models.CharField(max_length=64)
    reason = models.TextField(max_length=2000)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    reviewer_label = models.CharField(max_length=150)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ('view',)
        permissions = [('verify_document', 'Can verify official member documents for reuse')]
        ordering = ['-reviewed_at', '-pk']
