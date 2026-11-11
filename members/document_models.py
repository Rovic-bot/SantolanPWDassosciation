"""Private, retained versions of documents uploaded while updating a member."""
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models

_writing = ContextVar('member_document_writer', default=False)


@contextmanager
def member_document_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


def member_document_path(instance, filename):
    return f'member-documents/{instance.member_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class MemberDocumentQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Member document versions cannot be overwritten.')

    def delete(self):
        raise PermissionDenied('Member document disposal requires a separate approved procedure.')

    def bulk_create(self, *args, **kwargs):
        raise PermissionDenied('Use the member update service.')

    def bulk_update(self, *args, **kwargs):
        raise PermissionDenied('Use the member update service.')


class MemberDocumentUpload(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey('members.Member', on_delete=models.PROTECT, related_name='document_uploads')
    member_version = models.PositiveIntegerField()
    slot = models.CharField(max_length=32, choices=[('photo_2x2', 'One 2×2 photograph'),
        ('civil_document', 'Birth OR Marriage Certificate'), ('voter_certificate', "Voter's Certificate")])
    alternative = models.CharField(max_length=16, blank=True)
    file = models.FileField(upload_to=member_document_path, max_length=250)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=50)
    size = models.PositiveIntegerField()
    digest = models.CharField(max_length=64)
    predecessor = models.ForeignKey('self', null=True, on_delete=models.PROTECT, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    objects = MemberDocumentQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        ordering = ['-member_version', '-uploaded_at', '-pk']
        constraints = [models.UniqueConstraint(fields=['member', 'slot', 'member_version'],
            name='member_document_slot_version')]

    @property
    def application_id(self):
        return self.member.application_id

    def save(self, *args, **kwargs):
        if not _writing.get() or not self._state.adding:
            raise PermissionDenied('Use the member update service to add a document version.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Member document disposal requires a separate approved procedure.')
