"""Immutable shared policies and private acceptance of registered scoring inputs."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .evidence_records import EvidenceArtifact, EvidenceQuerySet, _recording


class VaultRevision(models.Model):
    revision = models.PositiveIntegerField(primary_key=True)
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=[('DRAFT', 'Draft'), ('LOCKED', 'Approved and locked')])
    policy = models.JSONField(blank=True)
    judgments = models.JSONField(blank=True)
    validation = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    actor_label = models.CharField(max_length=150)
    recorded_at = models.DateTimeField(default=timezone.now)
    reason = models.TextField(max_length=2000)
    digest = models.CharField(max_length=64)
    audit_entry = models.OneToOneField('admin.LogEntry', on_delete=models.PROTECT)
    objects = EvidenceQuerySet.as_manager()

    class Meta:
        ordering = ['-revision']
        default_permissions = ()
        base_manager_name = 'objects'

    def payload(self):
        from .evidence import canonical
        return canonical({field.attname: getattr(self, field.attname) for field in self._meta.fields
                          if field.name not in ('digest', 'audit_entry')})

    def clean(self):
        from .evidence import digest
        from .vault_policy import validate
        from django.contrib.contenttypes.models import ContentType
        if self.digest != digest(self.payload()) or not self.reason.strip():
            raise ValidationError('The vault revision content or explanation is invalid.')
        if self.previous_id != (self.revision - 1 or None):
            raise ValidationError('The vault predecessor does not match this revision.')
        audit = self.audit_entry
        if (audit.user_id != self.actor_id or audit.object_id != str(self.revision)
                or audit.content_type_id != ContentType.objects.get_for_model(type(self)).pk
                or audit.action_flag != 1 or audit.change_message != self.digest):
            raise ValidationError('The vault audit does not match the retained revision.')
        if self.status == 'LOCKED':
            validate(self.policy, self.judgments)
            from .vault_weights import is_direct, replay
            from .weight_input import replay_ahp
            expected = (replay(self.policy['weight_input'], self.judgments) if is_direct(self.policy)
                        else replay_ahp(self.judgments, self.policy.get('weight_input')))
            if self.validation != expected:
                raise ValidationError('The vault weights do not replay correctly.')

    def save(self, *args, **kwargs):
        if not _recording.get() or not self._state.adding:
            raise ValidationError('Use the audited vault service to record a new version.')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Vault history cannot be deleted.')


class RegisteredInputReview(EvidenceArtifact):
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT)
    configuration = models.ForeignKey('ewaf.OperationalConfiguration', on_delete=models.PROTECT)
    source = models.JSONField()
    supporting_reviews = models.JSONField()
    observation_start = models.DateField()
    observation_end = models.DateField()

    class Meta:
        ordering = ['-pk']
        default_permissions = ()

    def clean(self):
        super().clean()
        if (self.application.program_id != self.program_id or self.configuration.program_id != self.program_id
                or not self.configuration.vault_revision_id or self.observation_start > self.observation_end):
            raise ValidationError('The registered-input review has inconsistent ownership or dates.')
