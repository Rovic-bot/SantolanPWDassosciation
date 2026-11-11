"""Supported-path append-only guards for G12 artifacts, not privileged SQL protection."""
from contextvars import ContextVar
from contextlib import contextmanager
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.utils.timezone import now

_recording = ContextVar('g12_recording', default=False)


@contextmanager
def recording():
    token = _recording.set(True)
    try:
        yield
    finally:
        _recording.reset(token)


class EvidenceQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError('Evidence history is append-only. Record a new review.')

    def delete(self):
        raise ValidationError('Evidence history cannot be deleted.')

    def bulk_update(self, objs, fields, **kwargs):
        raise ValidationError('Evidence history cannot be replaced.')

    def bulk_create(self, objs, **kwargs):
        raise ValidationError('Use the audited evidence recording service.')


class EvidenceArtifact(models.Model):
    program = models.ForeignKey('programs.Program', on_delete=models.PROTECT, related_name='+')
    schema_version = models.PositiveSmallIntegerField(default=1, editable=False)
    digest = models.CharField(max_length=64, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+', editable=False)
    actor_label = models.CharField(max_length=150, editable=False)
    recorded_at = models.DateTimeField(default=now, editable=False)
    reason = models.TextField(max_length=2000)
    audit_entry = models.OneToOneField('programs.ProgramLog', on_delete=models.PROTECT, related_name='+', editable=False)
    objects = EvidenceQuerySet.as_manager()

    class Meta:
        abstract = True
        base_manager_name = 'objects'

    def payload(self):
        from .evidence import canonical
        return canonical({field.attname: getattr(self, field.attname) for field in self._meta.fields
                          if field.name not in {'id', 'digest', 'audit_entry'}})

    def clean(self):
        from .evidence import digest
        from programs.models import ProgramLog
        if self.schema_version != 1 or digest(self.payload()) != self.digest:
            raise ValidationError('Evidence schema or content digest does not match.')
        audit = ProgramLog.objects.filter(pk=self.audit_entry_id).first()
        application_id = getattr(self, 'application_id', None)
        expected = {'artifact': {'before': None, 'after': self._meta.model_name},
                    'digest': {'before': None, 'after': self.digest}}
        if not audit or (audit.program_id, audit.application_id, audit.actor_id, audit.actor_label,
                         audit.action, audit.changes, audit.notes) != (
                self.program_id, application_id, self.actor_id, self.actor_label,
                'g12_' + self._meta.model_name, expected, 'Private G12 evidence record retained; restricted review permission required.'):
            raise ValidationError('The mandatory audit must match this artifact, program, application, actor and digest.')
        if not self.reason.strip():
            raise ValidationError('A review explanation is required.')

    def save(self, *args, **kwargs):
        if not _recording.get() or not self._state.adding or self.pk is not None:
            raise ValidationError('Use the audited append-only evidence service.')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Evidence history cannot be deleted.')
