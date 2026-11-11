"""Append-only operational records; historical engines and tables are unchanged."""
from django.core.exceptions import ValidationError
from django.db import models

from .evidence_records import EvidenceArtifact


class OperationalConfiguration(EvidenceArtifact):
    revision = models.PositiveIntegerField()
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=[('DRAFT', 'Draft'), ('LOCKED', 'Authorized and locked')])
    policy = models.JSONField(blank=True)
    judgments = models.JSONField(blank=True)
    validation = models.JSONField(default=dict, blank=True)
    source = models.JSONField()
    evidence_policy = models.ForeignKey('ewaf.EvidencePolicyRevision', null=True, blank=True, on_delete=models.PROTECT)
    vault_revision = models.ForeignKey('ewaf.VaultRevision', null=True, blank=True, on_delete=models.PROTECT)
    dataset_policy = models.ForeignKey('ewaf.SharedDatasetPolicy', null=True, blank=True, on_delete=models.PROTECT)
    assessment_cutoff = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-revision']
        default_permissions = ()
        permissions = [('view_operational', 'View private operational EWAF'),
                       ('configure_operational', 'Record EWAF policy drafts'),
                       ('authorize_operational', 'Authorize and lock EWAF policies'),
                       ('calculate_operational', 'Generate and recalculate EWAF'),
                       ('decide_operational', 'Record reasoned EWAF beneficiary decisions')]
        constraints = [models.UniqueConstraint(fields=['program', 'revision'], name='ewaf_op_config_revision')]

    @property
    def uses_dataset_scoring(self):
        from .fixed_scoring import is_fixed
        return bool(self.dataset_policy_id or is_fixed(self))

    def clean(self):
        super().clean()
        from .fixed_scoring import is_fixed, validate
        if is_fixed(self):
            validate(self)
            return
        if self.dataset_policy_id:
            from .revised.live_services import validate_configuration
            validate_configuration(self)
            return
        from .dataset_methods import is_dataset, SES_SOURCE, COMPOSITE_SOURCE
        from .vault_policy import scoring_pending
        if self.assessment_cutoff is not None or is_dataset(self.policy) and not scoring_pending(self.policy):
            raise ValidationError('The dataset method requires an immutable approved scoring-policy binding.')
        from .vault_policy import CONTRACT
        if self.vault_revision_id:
            from .vault_services import validate_inheritance
            validate_inheritance(self)
        elif isinstance(self.policy, dict) and self.policy.get('source_contract') in (CONTRACT, SES_SOURCE, COMPOSITE_SOURCE):
            raise ValidationError('A shared configuration must retain its vault revision.')
        from .weight_input import validate_provenance
        if isinstance(self.policy, dict):
            validate_provenance(self.policy.get('weight_input'), self.judgments)
        if self.previous_id and (self.previous.program_id != self.program_id or self.revision != self.previous.revision + 1):
            raise ValidationError('Configuration predecessor mismatch.')
        if not self.previous_id and self.revision != 1:
            raise ValidationError('Configuration predecessor required.')
        if self.status == 'LOCKED':
            from .operational_policy import validate
            validate(self.policy, self.judgments)
            from .operational_policy import ahp
            if self.validation != ahp(self.judgments) or not (self.evidence_policy_id or self.vault_revision_id):
                raise ValidationError('Locked configuration replay failed.')

    def payload(self):
        value = super().payload()
        # Preserve all issued historical digests when the additive FK is empty.
        if not self.vault_revision_id:
            value.pop('vault_revision_id', None)
        if not self.uses_dataset_scoring:
            value.pop('dataset_policy_id', None)
            value.pop('assessment_cutoff', None)
        elif self.digest and self.assessment_cutoff is not None:
            # Earlier schedule edits signed the aware Philippine-time cutoff
            # before MySQL normalized it to UTC. Recover only that exact signed
            # representation of the same instant; all fields and the mandatory
            # audit still have to match. Never reseal or edit retained history.
            from zoneinfo import ZoneInfo
            from django.utils import timezone
            from .evidence import digest
            if timezone.is_aware(self.assessment_cutoff) and digest(value) != self.digest:
                original = value | {'assessment_cutoff': str(
                    self.assessment_cutoff.astimezone(ZoneInfo('Asia/Manila')))}
                if digest(original) == self.digest:
                    return original
        return value


class OperationalRun(EvidenceArtifact):
    configuration = models.ForeignKey(OperationalConfiguration, on_delete=models.PROTECT)
    previous = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='successor')
    revision = models.PositiveIntegerField()
    snapshot = models.JSONField()
    calculations = models.JSONField()
    valid_until = models.DateTimeField()
    request_key = models.UUIDField()

    class Meta:
        ordering = ['-revision']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['program', 'revision'], name='ewaf_op_run_revision'),
                       models.UniqueConstraint(fields=['program', 'request_key'], name='ewaf_op_run_request')]

    def clean(self):
        super().clean()
        if self.configuration.program_id != self.program_id or self.configuration.status != 'LOCKED':
            raise ValidationError('Authorized program configuration required.')
        if self.previous_id and (self.previous.program_id != self.program_id or self.revision != self.previous.revision + 1):
            raise ValidationError('Calculation predecessor mismatch.')
        if not self.previous_id and self.revision != 1:
            raise ValidationError('Calculation predecessor required.')
        from .operational_policy import calculations
        self.configuration.clean()
        from .revised.rolling_pool import observed_at
        assessment_time = observed_at(self.snapshot)
        if assessment_time and assessment_time > self.recorded_at:
            raise ValidationError('The ranking observation cannot follow the saved calculation.')
        from .shared_weights import KEY
        if KEY in self.snapshot:
            from django.utils.dateparse import parse_datetime
            from .shared_weights import retained
            selected = retained(self.snapshot, self.configuration)
            if parse_datetime(selected['approved_at']) > self.recorded_at:
                raise ValidationError('The weight approval must precede the saved calculation.')
        from .shared_calculation_rules import retained as retained_rules
        selected_rules = retained_rules(self.snapshot, self.configuration)
        if selected_rules:
            from django.utils.dateparse import parse_datetime
            if (parse_datetime(selected_rules['approved_at']) > self.recorded_at
                    or not parse_datetime(selected_rules['effective_from']) <= self.recorded_at < parse_datetime(selected_rules['effective_until'])
                    or self.valid_until > parse_datetime(selected_rules['effective_until'])):
                raise ValidationError('The calculation must fall within its saved rule approval and effective period.')
        if calculations(self.snapshot, self.configuration) != self.calculations:
            raise ValidationError('Stored calculation replay failed.')


class OperationalDecision(EvidenceArtifact):
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT)
    run = models.ForeignKey(OperationalRun, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    previous = models.OneToOneField('self', null=True, blank=True, on_delete=models.PROTECT, related_name='successor')
    outcome = models.CharField(max_length=16, choices=[('SELECTED', 'Selected'), ('NOT_SELECTED', 'Not selected'), ('DEFERRED', 'Deferred for review')])
    tie_reason = models.TextField(blank=True, max_length=2000)
    review = models.JSONField()

    class Meta:
        ordering = ['-recorded_at', '-pk']
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=['program', 'application', 'revision'], name='ewaf_op_decision_revision')]

    def clean(self):
        super().clean()
        if self.run.program_id != self.program_id or self.application.program_id != self.program_id:
            raise ValidationError('Decision program mismatch.')
        if str(self.application_id) not in self.run.calculations:
            raise ValidationError('Decision requires an eligible calculated application.')
        if self.previous_id and (self.previous.application_id != self.application_id or self.revision != self.previous.revision + 1):
            raise ValidationError('Decision predecessor mismatch.')
        if not self.previous_id and self.revision != 1:
            raise ValidationError('Decision predecessor required.')
        if self.review.get('run_digest') != self.run.digest:
            raise ValidationError('Decision calculation binding mismatch.')
