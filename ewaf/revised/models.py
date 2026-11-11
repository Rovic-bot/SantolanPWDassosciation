"""Separate append-only synthetic runs and reviews; never operational records."""
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models
from django.utils.timezone import now
from ewaf.evidence_records import EvidenceQuerySet, _recording
from .engine import (METHOD, Configuration, FrozenPool, canonical, calculate, CalculationError)


class PreviewArtifact(models.Model):
    """Reuse append-only guards and the Vault's private admin-audit channel.

    ProgramLog is deliberately not used: it is an input to legacy freshness.
    Synthetic preview actions must never invalidate an unrelated operational run.
    """
    program = models.ForeignKey('programs.Program', on_delete=models.PROTECT, related_name='+')
    schema_version = models.PositiveSmallIntegerField(default=1, editable=False)
    digest = models.CharField(max_length=64, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+', editable=False)
    actor_label = models.CharField(max_length=150, editable=False)
    recorded_at = models.DateTimeField(default=now, editable=False)
    reason = models.TextField(max_length=2000)
    audit_entry = models.OneToOneField('admin.LogEntry', on_delete=models.PROTECT, related_name='+', editable=False)
    objects = EvidenceQuerySet.as_manager()

    class Meta:
        abstract = True
        base_manager_name = 'objects'

    def payload(self):
        from ewaf.evidence import canonical as evidence_canonical
        return evidence_canonical({field.attname: getattr(self, field.attname) for field in self._meta.fields
            if field.name not in {'id', 'digest', 'audit_entry'}})

    def clean(self):
        from django.contrib.admin.models import LogEntry, ADDITION
        from django.contrib.contenttypes.models import ContentType
        from ewaf.evidence import digest
        if self.schema_version != 1 or digest(self.payload()) != self.digest or not self.reason.strip():
            raise ValidationError('Preview content, schema or explanation is invalid.')
        audit = LogEntry.objects.filter(pk=self.audit_entry_id).first()
        if not audit or (audit.user_id, audit.content_type_id, audit.object_id, audit.action_flag, audit.change_message) != (
                self.actor_id, ContentType.objects.get_for_model(type(self)).pk, self.digest, ADDITION, self.digest):
            raise ValidationError('Mandatory private audit does not match this exact preview artifact.')

    def save(self, *args, **kwargs):
        if not _recording.get() or not self._state.adding or self.pk is not None:
            raise ValidationError('Use the audited append-only preview service.')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Preview history cannot be deleted.')


class RevisedPreviewRun(PreviewArtifact):
    method = models.CharField(max_length=60, default=METHOD, editable=False)
    revision = models.PositiveIntegerField()
    previous = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='successor')
    mode = models.CharField(max_length=24, choices=[('DOCUMENT_EXAMPLE', 'Document example'), ('DRAFT_SENSITIVITY', 'Draft sensitivity')])
    configuration = models.JSONField()
    pool = models.JSONField()
    result = models.JSONField()
    source_context = models.JSONField()
    request_key = models.UUIDField()
    request_digest = models.CharField(max_length=64)
    capacity_example = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        app_label = 'ewaf'
        ordering = ['-revision']
        default_permissions = ()
        permissions = [('view_revisedpreview', 'View private revised EWAF demonstrations and history'),
                       ('calculate_revisedpreview', 'Calculate and retain synthetic revised EWAF previews'),
                       ('review_revisedpreview', 'Review synthetic revised EWAF previews'),
                       ('export_revisedpreview', 'Export private synthetic revised EWAF previews')]
        constraints = [models.UniqueConstraint(fields=['program', 'revision'], name='ewaf_rpv_run_revision'),
                       models.UniqueConstraint(fields=['program', 'request_key'], name='ewaf_rpv_run_request'),
                       models.CheckConstraint(condition=models.Q(method=METHOD), name='ewaf_rpv_method'),
                       models.CheckConstraint(condition=models.Q(mode__in=['DOCUMENT_EXAMPLE', 'DRAFT_SENSITIVITY']), name='ewaf_rpv_synthetic_only')]

    def clean(self):
        super().clean()
        if self.method != METHOD or self.mode != self.configuration.get('mode'):
            raise ValidationError('Revised method/provenance mismatch.')
        if self.previous_id:
            if self.previous.program_id != self.program_id or self.revision != self.previous.revision + 1:
                raise ValidationError('Preview predecessor mismatch.')
        elif self.revision != 1:
            raise ValidationError('Preview predecessor required.')
        if self.pool.get('program') != str(self.program_id):
            raise ValidationError('Frozen preview pool belongs to a different program context.')
        try:
            result = calculate(FrozenPool(canonical(self.pool)), Configuration(canonical(self.configuration)), capacity=self.capacity_example)
        except (CalculationError, KeyError, TypeError, ValueError) as error:
            raise ValidationError('Retained preview cannot be replayed: ' + str(error)) from error
        if result != self.result:
            raise ValidationError('Retained preview calculation differs from exact replay.')


class RevisedPreviewReview(PreviewArtifact):
    run = models.ForeignKey(RevisedPreviewRun, on_delete=models.PROTECT, related_name='reviews')
    run_digest = models.CharField(max_length=64)
    revision = models.PositiveIntegerField()
    previous = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='successor')
    finding = models.CharField(max_length=24, choices=[('REVIEWED', 'Reviewed demonstration'), ('CORRECTIONS_REQUESTED', 'Corrections requested')])

    class Meta:
        app_label = 'ewaf'
        ordering = ['-revision']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['run', 'revision'], name='ewaf_rpv_review_revision'),
                       models.CheckConstraint(condition=models.Q(finding__in=['REVIEWED', 'CORRECTIONS_REQUESTED']), name='ewaf_rpv_review_finding')]

    def clean(self):
        super().clean()
        self.run.clean()
        if self.program_id != self.run.program_id or self.run_digest != self.run.digest:
            raise ValidationError('Review requires the exact retained synthetic run.')
        if self.previous_id:
            if self.previous.run_id != self.run_id or self.revision != self.previous.revision + 1:
                raise ValidationError('Review predecessor mismatch.')
        elif self.revision != 1:
            raise ValidationError('Review predecessor required.')
