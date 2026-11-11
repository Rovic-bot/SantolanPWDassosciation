"""Dedicated durable storage; never G15 READINESS_ONLY or legacy tables."""
from django.core.exceptions import ValidationError
from django.db import models
from .durable_records import DurableArtifact


class DurableRequest(DurableArtifact):
    request_key = models.CharField(max_length=64)
    content_digest = models.CharField(max_length=64)
    expected_context = models.CharField(max_length=64)
    policy = models.ForeignKey('ewaf.ScoringPolicyRevision', on_delete=models.PROTECT, related_name='+')
    contract = models.JSONField()
    previous = models.ForeignKey('ewaf.DurableRun', null=True, blank=True, on_delete=models.PROTECT, related_name='successor_requests')

    class Meta(DurableArtifact.Meta):
        permissions = [('process_durablerequest', 'Can process isolated EWAF development requests')]
        constraints = [models.UniqueConstraint(fields=['program', 'request_key'], name='ewaf_durable_request_key')]

    def clean(self):
        super().clean()
        from .evidence import digest
        from .durable_services import _contract
        _contract(self.contract)
        if self.content_digest != digest({'actor': self.actor_id, 'reason': self.reason,
                'context': self.expected_context, 'contract': self.contract, 'previous': self.previous_id}):
            raise ValidationError('Request identity/content mismatch.')


class DurableAttempt(DurableArtifact):
    request = models.ForeignKey(DurableRequest, on_delete=models.PROTECT, related_name='attempts')
    ordinal = models.PositiveIntegerField()

    class Meta(DurableArtifact.Meta):
        constraints = [models.UniqueConstraint(fields=['request', 'ordinal'], name='ewaf_durable_attempt_number'),
                       models.CheckConstraint(condition=models.Q(ordinal__gte=1), name='ewaf_durable_attempt_positive')]


class DurableRun(DurableArtifact):
    request = models.OneToOneField(DurableRequest, on_delete=models.PROTECT, related_name='successful_run')
    attempt = models.OneToOneField(DurableAttempt, on_delete=models.PROTECT, related_name='successful_run')
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='successors')
    context_digest = models.CharField(max_length=64)
    snapshot = models.JSONField()
    # This is immutable historical content; completeness is an audited outcome.
    # There is deliberately no operational current-result pointer in this increment.

    def clean(self):
        super().clean()
        if self.attempt.request_id != self.request_id or self.previous_id != self.request.previous_id:
            raise ValidationError('Run/request/predecessor mismatch.')
        if (self.context_digest != self.request.expected_context or
                self.snapshot.get('program') != str(self.program_id) or
                self.snapshot.get('policy', {}).get('id') != self.request.policy_id):
            raise ValidationError('Run accepted context mismatch.')
        if self.previous_id and (self.previous_id == self.pk or self.previous.recorded_at >= self.recorded_at):
            raise ValidationError('Predecessor must be an earlier immutable run.')
        seen = {self.pk} if self.pk else set()
        row = self.previous
        while row:
            if row.pk in seen or row.program_id != self.program_id:
                raise ValidationError('Invalid calculation lineage.')
            seen.add(row.pk)
            row = row.previous


class DurableResult(DurableArtifact):
    run = models.ForeignKey(DurableRun, on_delete=models.PROTECT, related_name='results')
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT, related_name='+')
    calculation = models.JSONField()
    comparison = models.JSONField()

    class Meta(DurableArtifact.Meta):
        constraints = [models.UniqueConstraint(fields=['run', 'application'], name='ewaf_durable_run_application')]


class DurableTrace(DurableArtifact):
    result = models.ForeignKey(DurableResult, on_delete=models.PROTECT, related_name='traces')
    criterion = models.CharField(max_length=2)
    assessment = models.ForeignKey('ewaf.CriterionAssessment', on_delete=models.PROTECT, related_name='+')
    snapshot = models.JSONField()

    class Meta(DurableArtifact.Meta):
        constraints = [models.UniqueConstraint(fields=['result', 'criterion'], name='ewaf_durable_result_criterion'),
                       models.CheckConstraint(condition=models.Q(criterion__in=['SI', 'ES', 'PA', 'ND', 'PR']), name='ewaf_durable_criterion')]

    def clean(self):
        super().clean()
        if self.assessment.application_id != self.result.application_id or self.assessment.criterion != self.criterion:
            raise ValidationError('Cross-application/criterion assessment.')
        if self.snapshot.get('assessment') != {'id': self.assessment_id, 'digest': self.assessment.digest,
                                               'payload': self.assessment.payload()}:
            raise ValidationError('Accepted assessment identity mismatch.')


class DurableOutcome(DurableArtifact):
    attempt = models.OneToOneField(DurableAttempt, on_delete=models.PROTECT, related_name='outcome')
    status = models.CharField(max_length=12, choices=[(x, x) for x in ('COMPLETED', 'FAILED', 'INTERRUPTED')])
    code = models.CharField(max_length=60)
    run = models.OneToOneField(DurableRun, null=True, blank=True, on_delete=models.PROTECT, related_name='completion')

    class Meta(DurableArtifact.Meta):
        constraints = [models.CheckConstraint(condition=(models.Q(status='COMPLETED', run__isnull=False) |
            models.Q(status__in=['FAILED', 'INTERRUPTED'], run__isnull=True)), name='ewaf_durable_outcome_state')]

    def clean(self):
        super().clean()
        if self.status == 'COMPLETED':
            from .durable_services import validate_graph
            if not self.run_id or self.run.attempt_id != self.attempt_id:
                raise ValidationError('Incomplete outcome association.')
            validate_graph(self.run)
        elif self.run_id:
            raise ValidationError('Unsuccessful attempts cannot publish a run.')
