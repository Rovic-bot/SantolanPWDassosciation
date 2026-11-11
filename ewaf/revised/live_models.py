"""Additive policy and accepted-input history for the dataset method."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from ewaf.evidence_records import EvidenceArtifact, EvidenceQuerySet, _recording
from ewaf.evidence import canonical, digest
from .engine import METHOD
from ewaf import dataset_methods as methods


class SharedDatasetPolicy(models.Model):
    revision = models.PositiveIntegerField(unique=True)
    previous = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='successor')
    method = models.CharField(max_length=60, default=METHOD, editable=False)
    status = models.CharField(max_length=12, choices=[('DRAFT', 'Draft'), ('APPROVED', 'Approved')])
    content = models.JSONField()
    weight_configuration = models.ForeignKey('ewaf.VaultRevision', null=True, blank=True, on_delete=models.PROTECT)
    weight_snapshot = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    recorded_at = models.DateTimeField(default=timezone.now)
    reason = models.TextField(max_length=2000)
    digest = models.CharField(max_length=64)
    audit_entry = models.OneToOneField('admin.LogEntry', on_delete=models.PROTECT, related_name='+')
    objects = EvidenceQuerySet.as_manager()

    class Meta:
        app_label = 'ewaf'
        ordering = ['-revision']
        default_permissions = ()
        base_manager_name = 'objects'
        constraints = [models.CheckConstraint(condition=models.Q(status__in=['DRAFT', 'APPROVED']), name='ewaf_dataset_policy_status')]

    def payload(self):
        return canonical({field.attname: getattr(self, field.attname) for field in self._meta.fields
                          if field.name not in ('id', 'digest', 'audit_entry')})

    def __str__(self):
        return f'Policy version {self.revision} — {methods.LABELS.get(self.method, self.method)} — {self.status} — weight Vault {self.weight_configuration_id or "unspecified"}'

    def clean(self):
        from django.contrib.contenttypes.models import ContentType
        from .contracts import structural, findings, weight_snapshot
        if (self.method not in methods.SIGNATURES or self.content.get('method') != self.method
                or self.digest != digest(self.payload()) or not self.reason.strip()):
            raise ValidationError('The policy content or provenance does not match its digest.')
        structural(self.content)
        if (self.previous_id and self.revision != self.previous.revision + 1
                or not self.previous_id and self.revision != 1):
            raise ValidationError('Retain the preceding policy revision.')
        audit = self.audit_entry
        if (audit.user_id, audit.content_type_id, audit.object_id, audit.action_flag, audit.change_message) != (
                self.actor_id, ContentType.objects.get_for_model(type(self)).pk, self.digest, 1, self.digest):
            raise ValidationError('The mandatory policy approval/draft audit does not match.')
        if bool(self.weight_configuration_id) != bool(self.weight_snapshot):
            raise ValidationError('The weight snapshot must retain its exact locked weight record.')
        if self.weight_configuration_id and self.weight_snapshot != weight_snapshot(self.weight_configuration, self.method):
            raise ValidationError('The exact retained weight version or provenance changed.')
        if self.status == 'APPROVED':
            errors = findings(self.content, self.weight_snapshot or None, live=False)
            if errors:
                raise ValidationError(errors)
            if (not self.previous_id or self.previous.status != 'DRAFT'
                    or self.previous.content != self.content
                    or self.previous.weight_snapshot != self.weight_snapshot):
                raise ValidationError('Approval must retain the exact reviewed draft and weight reference.')

    def save(self, *args, **kwargs):
        if not _recording.get() or not self._state.adding or self.pk is not None:
            raise ValidationError('Use the audited versioned-policy service.')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Policy history cannot be deleted.')


class DatasetInputReview(EvidenceArtifact):
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT)
    configuration = models.ForeignKey('ewaf.OperationalConfiguration', on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    previous = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='successor')
    state = models.CharField(max_length=16, choices=[('ACCEPTED', 'Accepted'), ('NEEDS_REVIEW', 'Needs review'), ('DISPUTED', 'Disputed')])
    findings = models.JSONField(blank=True)
    inputs = models.JSONField(default=dict, blank=True)
    supporting_reviews = models.JSONField(default=dict, blank=True)
    source = models.JSONField()

    class Meta:
        app_label = 'ewaf'
        ordering = ['-revision']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['application', 'revision'], name='ewaf_dataset_input_revision'),
                       models.CheckConstraint(condition=models.Q(state__in=['ACCEPTED', 'NEEDS_REVIEW', 'DISPUTED']), name='ewaf_dataset_input_state')]

    def clean(self):
        super().clean()
        if (self.application.program_id != self.program_id or self.configuration.program_id != self.program_id
                or not self.configuration.dataset_policy_id):
            raise ValidationError('Accepted evidence must bind this program and its dataset policy version.')
        if (self.previous_id and (self.previous.application_id != self.application_id or self.revision != self.previous.revision + 1)
                or not self.previous_id and self.revision != 1):
            raise ValidationError('Retain the previous input review.')
        if self.state == 'ACCEPTED':
            from .live_evidence import derive_inputs
            if self.inputs != derive_inputs(self.findings, self.configuration, self.source):
                raise ValidationError('Accepted numerical inputs do not replay from the findings and release ledger.')
            from . import member_record_evidence
            if member_record_evidence.enabled(self.configuration.policy):
                if self.supporting_reviews != member_record_evidence.supporting(self.source, self.configuration):
                    raise ValidationError('Accepted inputs must retain the reviewed member-record provenance.')
            elif set(self.supporting_reviews) != set(methods.criteria(self.configuration.policy)) or any(not r for r in self.supporting_reviews.values()):
                raise ValidationError('Accepted inputs require verified supporting evidence for every criterion.')
        elif self.inputs:
            raise ValidationError('An unresolved review cannot manufacture accepted numerical inputs.')
