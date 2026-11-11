"""Isolated G14 append-only persistence contract; no G12 behavior changes."""
from contextlib import contextmanager
from contextvars import ContextVar
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.timezone import now
from .evidence import canonical, digest
from .evidence_records import EvidenceQuerySet

_recording = ContextVar('g14_recording', default=False)
AUDIT_NOTE = 'Private G14 preparatory record; no effective configuration authorization.'


@contextmanager
def recording():
    token = _recording.set(True)
    try:
        yield
    finally:
        _recording.reset(token)


def artifact_digest(payload):
    return digest({'domain': 'g14-configuration-artifact-v1', 'payload': payload})


class ConfigurationArtifact(models.Model):
    program = models.ForeignKey('programs.Program', on_delete=models.PROTECT, related_name='+')
    revision = models.PositiveIntegerField()
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    schema_version = models.PositiveSmallIntegerField(default=1, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+', editable=False)
    actor_label = models.CharField(max_length=150, editable=False)
    recorded_at = models.DateTimeField(default=now, editable=False)
    reason = models.TextField(max_length=2000)
    digest = models.CharField(max_length=64, editable=False)
    audit_entry = models.OneToOneField('programs.ProgramLog', on_delete=models.PROTECT, related_name='+', editable=False)
    objects = EvidenceQuerySet.as_manager()

    class Meta:
        abstract = True
        base_manager_name = 'objects'
        default_permissions = ('view',)
        ordering = ['-revision', '-pk']
        constraints = [models.CheckConstraint(condition=models.Q(revision__gte=1), name='g14_%(class)s_positive')]

    def payload(self):
        return canonical({f.attname: getattr(self, f.attname) for f in self._meta.fields
                          if f.name not in ('id', 'digest', 'audit_entry')})

    def clean(self):
        from programs.models import ProgramLog
        if self.schema_version != 1 or self.digest != artifact_digest(self.payload()):
            raise ValidationError('G14 artifact schema/content digest mismatch.')
        if not self.reason.strip():
            raise ValidationError('A reason is required.')
        if self.previous_id:
            if (self.previous.program_id != self.program_id or self.previous.revision != self.revision - 1 or
                    getattr(self.previous, 'configuration_id', None) != getattr(self, 'configuration_id', None)):
                raise ValidationError('Predecessor must be the preceding revision in the same history.')
        elif self.revision != 1:
            raise ValidationError('Later revisions require their predecessor.')
        if hasattr(self, 'configuration_id'):
            if self.configuration.program_id != self.program_id or self.configuration.digest != self.configuration_digest:
                raise ValidationError('Configuration ownership or digest mismatch.')
        if hasattr(self, 'validation_id'):
            if (self.validation.program_id != self.program_id or self.validation.configuration_id != self.configuration_id or
                    self.validation.digest != self.validation_digest):
                raise ValidationError('Validation must match this exact configuration and program.')
        log = ProgramLog.objects.filter(pk=self.audit_entry_id).first()
        expected = {'artifact': {'before': None, 'after': self._meta.model_name},
                    'digest': {'before': None, 'after': self.digest}}
        if not log or (log.program_id, log.application_id, log.actor_id, log.actor_label, log.action, log.notes, log.changes) != (
                self.program_id, None, self.actor_id, self.actor_label, 'g14_' + self._meta.model_name, AUDIT_NOTE, expected):
            raise ValidationError('Mandatory G14 audit association does not match the artifact.')

    def save(self, *args, **kwargs):
        if not _recording.get() or not self._state.adding or self.pk is not None:
            raise ValidationError('Use the append-only G14 recording services.')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('G14 history cannot be deleted.')
