from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Configuration(models.Model):
    name = models.CharField(max_length=120)
    si_source = models.CharField(max_length=20, choices=[('monthly_income', 'Monthly income'), ('assessment', 'Recorded socioeconomic assessment')])
    pairwise = models.JSONField()
    encodings = models.JSONField()
    bounds = models.JSONField()
    thresholds = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        default_permissions = ('add', 'view')
        ordering = ['-pk']

    def __str__(self):
        return f'{self.name} · version {self.pk}'

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Configurations are immutable. Create a new version.')
        return super().save(*args, **kwargs)


class ApplicationInput(models.Model):
    application = models.OneToOneField('programs.ProgramApplication', on_delete=models.PROTECT, related_name='ewaf_input')
    relevance = models.CharField(max_length=200)
    socioeconomic = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        default_permissions = ('view', 'change')


class RankingRun(models.Model):
    program = models.ForeignKey('programs.Program', on_delete=models.PROTECT, related_name='ranking_runs')
    configuration = models.ForeignKey(Configuration, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)

    class Meta:
        default_permissions = ('view',)
        permissions = [('generate_ranking', 'Can calculate EWAF and rank program applicants')]
        ordering = ['-pk']


class Snapshot(models.Model):
    run = models.ForeignKey(RankingRun, on_delete=models.PROTECT, related_name='snapshots')
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT, related_name='ewaf_snapshots')
    raw = models.JSONField()
    encoded = models.JSONField()
    normalized = models.JSONField()
    weights = models.JSONField()
    consistency = models.JSONField()
    score = models.DecimalField(max_digits=24, decimal_places=20)
    classification = models.CharField(max_length=120)
    rank = models.PositiveIntegerField()
    context = models.JSONField()

    class Meta:
        default_permissions = ('view',)
        ordering = ['rank', 'application__public_reference']
        constraints = [models.UniqueConstraint(fields=['run', 'application'], name='ewaf_one_snapshot_per_run_application')]


from .evidence_records import EvidenceArtifact


class EvidencePolicyRevision(EvidenceArtifact):
    """Recorded definitions only; no authorization/activation flag or scoring data."""
    revision = models.PositiveIntegerField()
    snapshot = models.JSONField()
    authority_reference = models.CharField(max_length=500)
    terms_revision = models.ForeignKey('programs.ProgramTermsRevision', null=True, blank=True,
                                      on_delete=models.PROTECT, related_name='+')
    terms_digest = models.CharField(max_length=64, blank=True)

    class Meta(EvidenceArtifact.Meta):
        default_permissions = ('view',)
        permissions = [('record_evidencepolicyrevision', 'Can record evidence policy references for review')]
        ordering = ['-revision']
        constraints = [models.UniqueConstraint(fields=['program', 'revision'], name='g12_policy_revision'),
                       models.CheckConstraint(condition=models.Q(revision__gte=1), name='g12_policy_positive')]

    def clean(self):
        super().clean()
        from .evidence import validate_policy
        validate_policy(self.snapshot)
        if self.terms_revision_id and (self.terms_revision.program_id != self.program_id or
                                      self.terms_revision.digest != self.terms_digest):
            raise ValidationError('Terms must belong to this program and match their retained digest.')
        if not self.terms_revision_id and self.terms_digest:
            raise ValidationError('A terms digest requires a terms revision.')


class CriterionAssessment(EvidenceArtifact):
    CRITERIA = [('SI', 'Socioeconomic Indicator'), ('ES', 'Employment Status'),
                ('PA', 'Previous Assistance Received'), ('ND', 'Number of Dependents'), ('PR', 'Program Relevance'),
                ('HI', 'Household monthly income'), ('HM', 'Number of Household members')]
    STATES = [(value, value.replace('_', ' ').title()) for value in ('DECLARED', 'NEEDS_REVIEW', 'VERIFIED', 'REJECTED')]
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT, related_name='criterion_assessments')
    criterion = models.CharField(max_length=2, choices=CRITERIA)
    revision = models.PositiveIntegerField()
    previous = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    policy = models.ForeignKey(EvidencePolicyRevision, on_delete=models.PROTECT, related_name='+')
    state = models.CharField(max_length=12, choices=STATES)
    value = models.JSONField(null=True, blank=True)
    value_type = models.CharField(max_length=12, choices=[('integer', 'Integer'), ('decimal', 'Decimal'),
        ('text', 'Text'), ('category', 'Category'), ('missing', 'Missing')])
    unit = models.CharField(max_length=80, blank=True)
    source_type = models.CharField(max_length=40)
    observation_start = models.DateField(null=True, blank=True)
    observation_end = models.DateField(null=True, blank=True)
    expires_on = models.DateField(null=True, blank=True)
    disputed = models.BooleanField(default=False)
    source_manifest = models.JSONField()
    source_digest = models.CharField(max_length=64)
    supporting_reviews = models.JSONField(default=list, blank=True)

    class Meta(EvidenceArtifact.Meta):
        default_permissions = ('view',)
        permissions = [('declare_criterionassessment', 'Can record criterion declarations'),
                       ('review_criterionassessment', 'Can record criterion verification findings')]
        ordering = ['-revision', '-pk']
        constraints = [models.UniqueConstraint(fields=['application', 'criterion', 'revision'], name='g12_assessment_revision'),
            models.CheckConstraint(condition=models.Q(revision__gte=1), name='g12_assessment_positive'),
            models.CheckConstraint(condition=models.Q(criterion__in=['SI', 'ES', 'PA', 'ND', 'PR', 'HI', 'HM']), name='g12_criterion_code'),
            models.CheckConstraint(condition=models.Q(state__in=['DECLARED', 'NEEDS_REVIEW', 'VERIFIED', 'REJECTED']), name='g12_evidence_state'),
            models.CheckConstraint(condition=~models.Q(state='VERIFIED') | (
                models.Q(value__isnull=False, disputed=False) & ~models.Q(value_type='missing')), name='g12_verified_value')]

    def clean(self):
        super().clean()
        from .evidence import digest
        if self.application.program_id != self.program_id or self.policy.program_id != self.program_id:
            raise ValidationError('Application and evidence policy must belong to this program.')
        if self.previous_id and (self.previous.application_id, self.previous.criterion, self.previous.revision) != (
                self.application_id, self.criterion, self.revision - 1):
            raise ValidationError('The previous assessment must be the preceding review of this criterion.')
        if not self.previous_id and self.revision != 1:
            raise ValidationError('Later revisions require their previous assessment.')
        if digest(self.source_manifest) != self.source_digest:
            raise ValidationError('Source digest mismatch.')


class EligibilityReadinessSnapshot(EvidenceArtifact):
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT, related_name='readiness_snapshots')
    result = models.JSONField()
    source_manifest = models.JSONField()

    class Meta(EvidenceArtifact.Meta):
        default_permissions = ('view',)
        permissions = [('record_eligibilityreadinesssnapshot', 'Can retain diagnostic readiness snapshots')]
        ordering = ['-recorded_at', '-pk']

    def clean(self):
        super().clean()
        if self.application.program_id != self.program_id or self.result.get('operational_ready') is not False:
            raise ValidationError('Readiness snapshots are program-scoped diagnostics, never processing authorization.')


from .configuration_records import ConfigurationArtifact


class ConfigurationRevision(ConfigurationArtifact):
    criteria_order = models.JSONField()
    judgments = models.JSONField()
    canonical_judgments = models.JSONField(null=True, blank=True)
    method = models.CharField(max_length=60)
    profile = models.CharField(max_length=60)
    policy = models.ForeignKey(EvidencePolicyRevision, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    policy_digest = models.CharField(max_length=64, blank=True)
    terms_revision = models.ForeignKey('programs.ProgramTermsRevision', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    terms_digest = models.CharField(max_length=64, blank=True)
    source_context = models.JSONField()

    class Meta(ConfigurationArtifact.Meta):
        permissions = [('record_configurationrevision', 'Can record private configuration drafts')]
        constraints = ConfigurationArtifact.Meta.constraints + [models.UniqueConstraint(fields=['program', 'revision'], name='g14_program_revision')]

    def clean(self):
        super().clean()
        from .ahp_validation import CRITERIA, METHOD, PROFILE, safe_payload, validate_ahp
        from . import four_policy
        if self.profile == four_policy.PROFILE:
            four_policy.validate_configuration(self)
        else:
            if self.criteria_order != list(CRITERIA) or self.method != METHOD or self.profile != PROFILE:
                raise ValidationError('Only the exact five-criterion reference method is supported.')
            safe_payload(self.judgments)
            if validate_ahp(self.judgments)['canonical_input'] != self.canonical_judgments:
                raise ValidationError('Canonical judgments must be server-derived.')
        for field in ('policy', 'terms_revision'):
            row = getattr(self, field)
            retained = self.policy_digest if field == 'policy' else self.terms_digest
            if row and (row.program_id != self.program_id or row.digest != retained) or not row and retained:
                raise ValidationError('Policy/terms ownership or digest mismatch.')


class ConfigurationValidation(ConfigurationArtifact):
    configuration = models.ForeignKey(ConfigurationRevision, on_delete=models.PROTECT, related_name='validations')
    configuration_digest = models.CharField(max_length=64)
    engine = models.CharField(max_length=60)
    profile = models.CharField(max_length=60)
    result = models.JSONField()

    class Meta(ConfigurationArtifact.Meta):
        permissions = [('record_configurationvalidation', 'Can retain reference AHP validation')]
        constraints = ConfigurationArtifact.Meta.constraints + [models.UniqueConstraint(fields=['configuration', 'revision'], name='g14_validation_revision')]

    def clean(self):
        super().clean()
        from .ahp_validation import ENGINE, PROFILE, validate_ahp
        from . import four_policy
        if self.profile == four_policy.PROFILE:
            four_policy.validate_validation(self)
            return
        if self.engine != ENGINE or self.profile != PROFILE or self.result != validate_ahp(self.configuration.judgments):
            raise ValidationError('Mathematical evidence must match the versioned server calculation.')


class ConfigurationReview(ConfigurationArtifact):
    configuration = models.ForeignKey(ConfigurationRevision, on_delete=models.PROTECT, related_name='reviews')
    configuration_digest = models.CharField(max_length=64)
    validation = models.ForeignKey(ConfigurationValidation, on_delete=models.PROTECT, related_name='+')
    validation_digest = models.CharField(max_length=64)
    finding = models.CharField(max_length=24, choices=[('REVIEWED', 'Review completed'), ('CORRECTIONS_REQUESTED', 'Corrections requested')])
    correction_requests = models.TextField(max_length=2000, blank=True)

    class Meta(ConfigurationArtifact.Meta):
        permissions = [('record_configurationreview', 'Can review configuration findings')]
        constraints = ConfigurationArtifact.Meta.constraints + [
            models.UniqueConstraint(fields=['configuration', 'revision'], name='g14_review_revision'),
            models.CheckConstraint(condition=models.Q(finding__in=['REVIEWED', 'CORRECTIONS_REQUESTED']), name='g14_review_finding')]

    def clean(self):
        super().clean()
        if self.finding == 'CORRECTIONS_REQUESTED' and not self.correction_requests.strip():
            raise ValidationError('Describe the requested corrections.')


class ConfigurationAuthorizationEvidence(ConfigurationArtifact):
    configuration = models.ForeignKey(ConfigurationRevision, on_delete=models.PROTECT, related_name='authority_evidence')
    configuration_digest = models.CharField(max_length=64)
    validation = models.ForeignKey(ConfigurationValidation, on_delete=models.PROTECT, related_name='+')
    validation_digest = models.CharField(max_length=64)
    authority_reference = models.CharField(max_length=500)
    stated_scope = models.CharField(max_length=1000)
    attested = models.BooleanField(default=False)

    class Meta(ConfigurationArtifact.Meta):
        permissions = [('record_configurationauthorizationevidence', 'Can record non-effective documentary authority evidence')]
        constraints = ConfigurationArtifact.Meta.constraints + [
            models.UniqueConstraint(fields=['configuration', 'revision'], name='g14_authority_revision'),
            models.CheckConstraint(condition=models.Q(attested=True), name='g14_authority_attested')]

    def clean(self):
        super().clean()
        if self.attested is not True or not self.authority_reference.strip() or not self.stated_scope.strip():
            raise ValidationError('Documentary reference, stated scope and recording attestation are required.')


# G15 is additive. Historical and G12/G14 artifacts above retain their contracts.
from .scoring_records import ScoringArtifact


class ScoringPolicyRevision(ScoringArtifact):
    criteria_order = models.JSONField()
    proposal = models.JSONField()
    engine = models.CharField(max_length=60)
    profile = models.CharField(max_length=60)
    evidence_policy = models.ForeignKey(EvidencePolicyRevision, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    evidence_policy_digest = models.CharField(max_length=64, blank=True)
    configuration = models.ForeignKey(ConfigurationRevision, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    configuration_digest = models.CharField(max_length=64, blank=True)
    validation = models.ForeignKey(ConfigurationValidation, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    validation_digest = models.CharField(max_length=64, blank=True)
    terms_revision = models.ForeignKey('programs.ProgramTermsRevision', null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    terms_revision_digest = models.CharField(max_length=64, blank=True)
    source_context = models.JSONField()

    class Meta(ScoringArtifact.Meta):
        permissions = [('record_scoringpolicyrevision', 'Can record non-effective scoring-policy proposals')]
        constraints = ScoringArtifact.Meta.constraints + [models.UniqueConstraint(fields=['program', 'revision'], name='g15_policy_revision')]

    def clean(self):
        super().clean()
        from .scoring_policy import proposal
        from .normalization import CRITERIA, ENGINE, PROFILE
        from . import four_policy
        if self.profile == four_policy.PROFILE:
            four_policy.validate_policy(self)
        elif self.criteria_order != list(CRITERIA) or self.engine != ENGINE or self.profile != PROFILE or proposal(self.proposal) != self.proposal:
            raise ValidationError('Unsupported or noncanonical scoring proposal.')
        if self.configuration_id and (self.configuration.policy_id != self.evidence_policy_id or self.configuration.policy_digest != self.evidence_policy_digest):
            raise ValidationError('Configuration and evidence policy must match exactly.')


class CalculationDiagnosticRun(ScoringArtifact):
    policy = models.ForeignKey(ScoringPolicyRevision, on_delete=models.PROTECT, related_name='runs')
    policy_digest = models.CharField(max_length=64)
    configuration = models.ForeignKey(ConfigurationRevision, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    configuration_digest = models.CharField(max_length=64, blank=True)
    validation = models.ForeignKey(ConfigurationValidation, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    validation_digest = models.CharField(max_length=64, blank=True)
    mode = models.CharField(max_length=30, choices=[('READINESS_ONLY', 'Applicant readiness only')])
    engine = models.CharField(max_length=60)
    profile = models.CharField(max_length=60)
    evaluation_date = models.DateField()
    evaluation_timezone = models.CharField(max_length=60)
    result = models.JSONField()
    context_digest = models.CharField(max_length=64)
    item_manifest = models.JSONField()

    class Meta(ScoringArtifact.Meta):
        permissions = [('record_calculationdiagnosticrun', 'Can retain private applicant readiness diagnostics')]
        constraints = ScoringArtifact.Meta.constraints + [
            models.UniqueConstraint(fields=['program', 'revision'], name='g15_run_revision'),
            models.CheckConstraint(condition=models.Q(mode='READINESS_ONLY'), name='g15_readiness_only')]

    def clean(self):
        super().clean()
        from .scoring_inputs import validate_readiness_payload
        from .normalization import ENGINE, PROFILE
        if self.mode != 'READINESS_ONLY' or self.engine != ENGINE or self.profile != PROFILE:
            raise ValidationError('Only readiness retention is available. Synthetic mathematics stays in development fixtures.')
        if self.configuration_id != self.policy.configuration_id or self.validation_id != self.policy.validation_id:
            raise ValidationError('Run references must match policy proposal.')
        validate_readiness_payload(self.result)
        if self.context_digest != self.result['context_digest']:
            raise ValidationError('Run context digest mismatch.')


class CalculationDiagnosticItem(ScoringArtifact):
    run = models.ForeignKey(CalculationDiagnosticRun, on_delete=models.PROTECT, related_name='items')
    item_key = models.CharField(max_length=80)
    application = models.ForeignKey('programs.ProgramApplication', on_delete=models.PROTECT, related_name='+')
    result = models.JSONField()
    trace_manifest = models.JSONField()

    class Meta(ScoringArtifact.Meta):
        constraints = ScoringArtifact.Meta.constraints + [models.UniqueConstraint(fields=['run', 'item_key'], name='g15_run_item')]

    @property
    def audit_application_id(self):
        return self.application_id

    def clean(self):
        super().clean()
        from .scoring_inputs import validate_readiness_payload
        if self.revision != 1 or self.previous_id or self.program_id != self.run.program_id or self.application.program_id != self.program_id:
            raise ValidationError('Diagnostic item ownership mismatch.')
        validate_readiness_payload(self.result)
        if self.result != self.run.result or self.item_key != str(self.application_id):
            raise ValidationError('Item must match this exact captured application result.')


class CalculationCriterionTrace(ScoringArtifact):
    item = models.ForeignKey(CalculationDiagnosticItem, on_delete=models.PROTECT, related_name='traces')
    criterion = models.CharField(max_length=2, choices=[(key, key) for key in ('SI', 'ES', 'PA', 'ND', 'PR')])
    assessment = models.ForeignKey(CriterionAssessment, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    assessment_digest = models.CharField(max_length=64, blank=True)
    source_digest = models.CharField(max_length=64, blank=True)
    evidence_policy = models.ForeignKey(EvidencePolicyRevision, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    evidence_policy_digest = models.CharField(max_length=64, blank=True)
    value_type = models.CharField(max_length=40, blank=True)
    unit = models.CharField(max_length=100, blank=True)
    current = models.BooleanField()

    class Meta(ScoringArtifact.Meta):
        constraints = ScoringArtifact.Meta.constraints + [
            models.UniqueConstraint(fields=['item', 'criterion'], name='g15_item_criterion'),
            models.CheckConstraint(condition=models.Q(criterion__in=['SI', 'ES', 'PA', 'ND', 'PR']), name='g15_criterion_identity')]

    @property
    def audit_application_id(self):
        return self.item.application_id

    def clean(self):
        super().clean()
        if self.revision != 1 or self.previous_id or self.program_id != self.item.program_id:
            raise ValidationError('Trace ownership mismatch.')
        row = self.assessment
        if row:
            if (row.application_id, row.criterion, row.digest, row.source_digest, row.policy_id, row.policy.digest, row.value_type, row.unit) != (
                    self.item.application_id, self.criterion, self.assessment_digest, self.source_digest,
                    self.evidence_policy_id, self.evidence_policy_digest, self.value_type, self.unit):
                raise ValidationError('Trace must match the exact criterion assessment.')
        elif any((self.assessment_digest, self.source_digest, self.evidence_policy_id, self.evidence_policy_digest, self.value_type, self.unit, self.current)):
            raise ValidationError('Missing assessments cannot manufacture provenance.')
        captured = next(entry for entry in self.item.result['criteria'] if entry['criterion'] == self.criterion)
        if (captured['assessment'], captured['current']) != (self.assessment_id, self.current):
            raise ValidationError('Trace differs from captured readiness.')


# Additive development storage. No Admin registration or operational entry point.
from .durable_models import (DurableRequest, DurableAttempt, DurableRun, DurableResult,
                             DurableTrace, DurableOutcome)  # noqa: E402,F401

# Empty, non-promotable generation foundations; no source-writer enlistment.
from .generation_models import (AuthorityGeneration, AuthorityInvalidation, ProgramSourceState,
    SourceMutationBatch, SourceInvalidation, RequestSourceBinding, RunSourceBinding,
    DevelopmentPromotion)  # noqa: E402,F401

from .decision_models import DevelopmentHumanDecision, DevelopmentHumanDecisionAudit  # noqa: E402,F401
from .operational_models import OperationalConfiguration, OperationalRun, OperationalDecision
from .vault_models import VaultRevision, RegisteredInputReview
from .revised.models import RevisedPreviewRun, RevisedPreviewReview
from .revised.live_models import SharedDatasetPolicy, DatasetInputReview
