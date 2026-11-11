"""G15 artifact integrity and append-only storage; no authority promotion."""
from contextlib import contextmanager
from contextvars import ContextVar
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.timezone import now
from .evidence import canonical, digest
from .evidence_records import EvidenceQuerySet

_recording = ContextVar('g15_recording', default=False)
AUDIT_NOTE = 'Private G15 diagnostic artifact; beneficiary processing unavailable.'


@contextmanager
def recording():
    token = _recording.set(True)
    try:
        yield
    finally:
        _recording.reset(token)


def artifact_digest(payload):
    return digest({'domain': 'g15-diagnostic-artifact-v1', 'payload': payload})


class ScoringArtifact(models.Model):
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
        constraints = [models.CheckConstraint(condition=models.Q(revision__gte=1), name='g15_%(class)s_positive')]

    @property
    def audit_application_id(self):
        return None

    def payload(self):
        return canonical({f.attname: getattr(self, f.attname) for f in self._meta.fields
                          if f.name not in ('id', 'digest', 'audit_entry')})

    def clean(self):
        from programs.models import ProgramLog
        if self.schema_version != 1 or self.digest != artifact_digest(self.payload()):
            raise ValidationError('G15 artifact schema/content digest mismatch.')
        if not self.reason.strip():
            raise ValidationError('A recording reason is required.')
        if self.previous_id:
            if self.previous.program_id != self.program_id or self.previous.revision != self.revision - 1:
                raise ValidationError('Predecessor must be the preceding program revision.')
        elif self.revision != 1:
            raise ValidationError('Later revisions require a predecessor.')
        for field in ('policy', 'configuration', 'validation', 'evidence_policy', 'terms_revision'):
            if hasattr(self, field + '_id'):
                row = getattr(self, field)
                retained = getattr(self, field + '_digest')
                if (row and (row.program_id != self.program_id or row.digest != retained)) or (not row and retained):
                    raise ValidationError('Cross-program or mismatched artifact reference.')
        if hasattr(self, 'validation_id') and self.validation_id and self.validation.configuration_id != self.configuration_id:
            raise ValidationError('Validation must reference this exact configuration.')
        expected = {'artifact': {'before': None, 'after': self._meta.model_name},
                    'digest': {'before': None, 'after': self.digest}}
        log = ProgramLog.objects.filter(pk=self.audit_entry_id).first()
        if not log or (log.program_id, log.application_id, log.actor_id, log.actor_label, log.action, log.notes, log.changes) != (
                self.program_id, self.audit_application_id, self.actor_id, self.actor_label,
                'g15_' + self._meta.model_name, AUDIT_NOTE, expected):
            raise ValidationError('Mandatory G15 audit does not match artifact.')

    def save(self, *args, **kwargs):
        if not _recording.get() or not self._state.adding or self.pk is not None:
            raise ValidationError('Use append-only G15 recording services.')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('G15 history cannot be deleted.')
