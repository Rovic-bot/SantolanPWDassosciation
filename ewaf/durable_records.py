"""Append-only private development artifacts. No privileged-SQL guarantee."""
from contextlib import contextmanager
from contextvars import ContextVar
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.timezone import now
from .evidence import canonical, digest
from .evidence_records import EvidenceQuerySet

_recording = ContextVar('durable_recording', default=False)
AUDIT_NOTE = 'Private EWAF development artifact; operational consumption prohibited.'


@contextmanager
def recording():
    token = _recording.set(True)
    try:
        yield
    finally:
        _recording.reset(token)


class DurableArtifact(models.Model):
    program = models.ForeignKey('programs.Program', on_delete=models.PROTECT, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    reason = models.TextField(max_length=2000)
    recorded_at = models.DateTimeField(default=now, editable=False)
    digest = models.CharField(max_length=64, editable=False)
    audit_entry = models.OneToOneField('programs.ProgramLog', on_delete=models.PROTECT, related_name='+')
    objects = EvidenceQuerySet.as_manager()

    class Meta:
        abstract = True
        base_manager_name = 'objects'
        default_permissions = ('view',)

    def payload(self):
        return canonical({f.attname: getattr(self, f.attname) for f in self._meta.fields
                          if f.name not in ('id', 'digest', 'audit_entry')})

    def clean(self):
        from programs.models import ProgramLog
        if not self.reason.strip() or digest(self.payload()) != self.digest:
            raise ValidationError('Invalid immutable artifact content.')
        for field in ('request', 'attempt', 'run', 'previous', 'policy', 'application', 'result', 'assessment'):
            if getattr(self, field + '_id', None):
                row = getattr(self, field)
                if row.program_id != self.program_id:
                    raise ValidationError('Cross-program artifact relationship.')
        log = ProgramLog.objects.get(pk=self.audit_entry_id)
        if (log.program_id, log.actor_id, log.actor_label, log.action, log.notes, log.changes) != (
                self.program_id, self.actor_id, self.actor_label, 'durable_' + self._meta.model_name,
                AUDIT_NOTE, {'digest': {'before': None, 'after': self.digest}}):
            raise ValidationError('Required protected audit mismatch.')

    def save(self, *args, **kwargs):
        if not _recording.get() or not self._state.adding or self.pk is not None:
            raise ValidationError('Use append-only durable services.')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Historical calculations cannot be deleted.')
