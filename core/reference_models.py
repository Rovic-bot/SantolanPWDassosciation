from django.core.exceptions import PermissionDenied
from django.db import models

from .reference_services import KINDS, _writing, format_code


class ShortReferenceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionDenied('Issued short references are immutable.')

    def delete(self):
        raise PermissionDenied('Issued short references must not be reused.')

    def bulk_create(self, *args, **kwargs):
        raise PermissionDenied('Use the reference allocation service.')

    def bulk_update(self, *args, **kwargs):
        raise PermissionDenied('Issued short references are immutable.')


class ShortReference(models.Model):
    kind = models.CharField(max_length=16, choices=[(kind, value[0]) for kind, value in KINDS.items()], editable=False)
    object_key = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    objects = ShortReferenceQuerySet.as_manager()

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=['kind', 'object_key'], name='one_short_reference_per_record'),
            models.CheckConstraint(condition=models.Q(kind__in=list(KINDS)), name='short_reference_kind'),
        ]

    @property
    def code(self):
        return format_code(self.kind, self.pk)

    def save(self, *args, **kwargs):
        if not _writing.get() or not self._state.adding:
            raise PermissionDenied('Use the reference allocation service; issued codes cannot change.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied('Issued short references must not be reused.')
