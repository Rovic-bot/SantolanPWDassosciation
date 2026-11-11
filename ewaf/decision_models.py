"""Append-only fictional decisions, isolated from assistance and publication."""
import re
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from .evidence import digest
from .evidence_records import EvidenceQuerySet
from .generation_records import canonical_payload, require_owner, MAX_GENERATION

DECISION_PROTOCOL = 'g18-four-human-decision-1'
AUDIT_PROTOCOL = 'g18-four-human-audit-1'
DECISIONS = ('SELECT_DEMO', 'DEFER_REVIEW', 'WITHDRAW_DEMO')


class DecisionRecord(models.Model):
    program = models.ForeignKey('programs.Program', on_delete=models.PROTECT, related_name='+')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    actor_label = models.CharField(max_length=150)
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)
    digest = models.CharField(max_length=64, editable=False)
    objects = EvidenceQuerySet.as_manager()

    class Meta:
        abstract = True
        base_manager_name = 'objects'
        default_permissions = ()

    def content(self):
        return canonical_payload({'model': self._meta.label_lower, 'fields': {
            field.attname: getattr(self, field.attname) for field in self._meta.fields
            if field.name not in ('id', 'digest', 'audit')}})

    def clean(self):
        if (timezone.is_naive(self.recorded_at) or not self.actor_label.strip() or
                not re.fullmatch('[0-9a-f]{64}', self.digest or '') or digest(self.content()) != self.digest):
            raise ValidationError('HUMAN_DECISION_DIGEST_INVALID')

    def save(self, *args, **kwargs):
        require_owner()
        from .decision_services import require_recording
        require_recording()
        if not self._state.adding or self.pk is not None:
            raise ValidationError('HUMAN_DECISION_IMMUTABLE')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('HUMAN_DECISION_IMMUTABLE')


class DevelopmentHumanDecisionAudit(DecisionRecord):
    action = models.CharField(max_length=24, default='RECORD_DEMO_DECISION', editable=False)
    decision_digest = models.CharField(max_length=64)
    protocol = models.CharField(max_length=60, default=AUDIT_PROTOCOL, editable=False)

    class Meta(DecisionRecord.Meta):
        abstract = False
        constraints = [
            models.CheckConstraint(condition=models.Q(action='RECORD_DEMO_DECISION'), name='four_human_audit_action'),
            models.CheckConstraint(condition=models.Q(protocol=AUDIT_PROTOCOL), name='four_human_audit_protocol')]

    def clean(self):
        super().clean()
        if (self.protocol != AUDIT_PROTOCOL or self.action != 'RECORD_DEMO_DECISION' or
                not re.fullmatch('[0-9a-f]{64}', self.decision_digest or '')):
            raise ValidationError('HUMAN_DECISION_AUDIT_INVALID')


class DevelopmentHumanDecision(DecisionRecord):
    run_binding = models.ForeignKey('ewaf.RunSourceBinding', on_delete=models.PROTECT, related_name='+')
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT, related_name='+')
    decision = models.CharField(max_length=24, choices=[(value, value) for value in DECISIONS])
    reason = models.TextField(max_length=1000)
    revision = models.PositiveBigIntegerField()
    previous = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    source_generation = models.PositiveBigIntegerField()
    authority_generation = models.PositiveBigIntegerField()
    state_revision = models.PositiveBigIntegerField()
    run_digest = models.CharField(max_length=64)
    graph_digest = models.CharField(max_length=64)
    protocol = models.CharField(max_length=60, default=DECISION_PROTOCOL, editable=False)
    payload = models.JSONField()
    audit = models.OneToOneField(DevelopmentHumanDecisionAudit, on_delete=models.PROTECT, related_name='+')

    class Meta(DecisionRecord.Meta):
        abstract = False
        constraints = [
            models.UniqueConstraint(fields=['program', 'application', 'revision'], name='four_human_revision'),
            models.CheckConstraint(condition=models.Q(decision__in=DECISIONS), name='four_human_outcome'),
            models.CheckConstraint(condition=models.Q(protocol=DECISION_PROTOCOL), name='four_human_protocol'),
            *[models.CheckConstraint(condition=models.Q(**{field + '__gte': 1, field + '__lte': MAX_GENERATION}),
                name='four_human_' + suffix) for field, suffix in [('revision', 'rev_bound'),
                ('source_generation', 'source_bound'), ('authority_generation', 'auth_bound'), ('state_revision', 'state_bound')]]]
        indexes = [models.Index(fields=['program', 'application', 'recorded_at'], name='four_human_app_time'),
                   models.Index(fields=['run_binding', 'recorded_at'], name='four_human_run_time')]

    def clean(self):
        super().clean()
        from .decision_services import validate_record
        validate_record(self)
