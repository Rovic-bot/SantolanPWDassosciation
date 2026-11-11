"""Eight additive, inactive G18-B foundation models. No operational consumers."""
import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q

from .generation_records import GenerationRecord, GenerationState, MAX_GENERATION, PROTOCOL


def fk(target, **kwargs):
    return models.ForeignKey(target, on_delete=models.PROTECT, related_name='+', **kwargs)


def one(target, **kwargs):
    return models.OneToOneField(target, on_delete=models.PROTECT, related_name='+', **kwargs)


def check(name, condition):
    return models.CheckConstraint(name=name, condition=condition)


def bounds(prefix, *fields):
    return [check(f'{prefix}_{field}_bound', Q(**{field + '__gte': 0, field + '__lte': MAX_GENERATION}))
            for field in fields]


def audit_checks(prefix):
    return [check(prefix + '_actor_xor', (Q(actor__isnull=False) & Q(system_code='')) |
                  (Q(actor__isnull=True) & ~Q(system_code=''))),
            check(prefix + '_reason_code', ~Q(reason_code=''))]


class ActorReason(models.Model):
    actor = fk(settings.AUTH_USER_MODEL, null=True, blank=True)
    actor_label = models.CharField(max_length=150)
    system_code = models.CharField(max_length=64, blank=True, default='')
    reason_code = models.CharField(max_length=64)
    reason = models.TextField(max_length=2000)

    class Meta:
        abstract = True


class AuthorityGeneration(GenerationState):
    id = models.PositiveSmallIntegerField(primary_key=True)
    generation = models.PositiveBigIntegerField(default=0)
    last_event = fk('ewaf.AuthorityInvalidation', null=True, blank=True, default=None, db_index=False)

    class Meta(GenerationState.Meta):
        abstract = False
        constraints = bounds('g18_ag', 'generation') + [
            check('g18_ag_singleton', Q(id=1)),
            check('g18_ag_tail_shape', Q(generation=0, last_event__isnull=True) |
                  Q(generation__gt=0, last_event__isnull=False))]


class AuthorityInvalidation(GenerationRecord, ActorReason):
    KINDS = ('INITIALIZE', 'USER_CHANGE', 'GROUP_CHANGE', 'CREDENTIAL_CHANGE', 'CATALOG_RECONCILE')
    SUBJECTS = ('installation', 'user', 'group', 'catalog')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    before_generation = models.PositiveBigIntegerField()
    after_generation = models.PositiveBigIntegerField(unique=True)
    kind = models.CharField(max_length=24, choices=[(v, v) for v in KINDS])
    subject_kind = models.CharField(max_length=24, choices=[(v, v) for v in SUBJECTS])
    subject_id = models.CharField(max_length=64)
    native_audits = models.JSONField(default=list, blank=True)

    class Meta(GenerationRecord.Meta):
        abstract = False
        constraints = bounds('g18_ai', 'before_generation', 'after_generation') + audit_checks('g18_ai') + [
            check('g18_ai_sequence', Q(after_generation=F('before_generation') + 1)),
            check('g18_ai_kind', Q(kind__in=('INITIALIZE', 'USER_CHANGE', 'GROUP_CHANGE', 'CREDENTIAL_CHANGE', 'CATALOG_RECONCILE'))),
            check('g18_ai_subject', Q(subject_kind__in=('installation', 'user', 'group', 'catalog')))]
        indexes = [models.Index(fields=['subject_kind', 'subject_id', 'recorded_at'], name='g18_ai_subject_time')]


class ProgramSourceState(GenerationState):
    program = one('programs.Program', primary_key=True)
    generation = models.PositiveBigIntegerField(default=0)
    revision = models.PositiveBigIntegerField(default=0)
    last_invalidation = fk('ewaf.SourceInvalidation', null=True, blank=True, default=None)
    current_binding = fk('ewaf.RunSourceBinding', null=True, blank=True, default=None)

    class Meta(GenerationState.Meta):
        abstract = False
        constraints = bounds('g18_ps', 'generation', 'revision') + [
            check('g18_ps_revision', Q(revision__gte=F('generation'))),
            check('g18_ps_tail_shape', Q(generation=0, revision=0, last_invalidation__isnull=True,
                                      current_binding__isnull=True) |
                  Q(generation__gt=0, last_invalidation__isnull=False))]


class SourceMutationBatch(GenerationRecord, ActorReason):
    KINDS = ('INITIALIZE', 'SOURCE_CHANGE', 'EXPIRY', 'REPLACEMENT')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=24, choices=[(v, v) for v in KINDS])
    source_kind = models.CharField(max_length=64)
    source_id = models.CharField(max_length=64)
    source_audits = models.JSONField(default=list, blank=True)
    scope_digest = models.CharField(max_length=64)
    scope_count = models.PositiveIntegerField()

    class Meta(GenerationRecord.Meta):
        abstract = False
        constraints = audit_checks('g18_sb') + [check('g18_sb_kind',
            Q(kind__in=('INITIALIZE', 'SOURCE_CHANGE', 'EXPIRY', 'REPLACEMENT')))]
        indexes = [models.Index(fields=['source_kind', 'source_id', 'recorded_at'], name='g18_sb_source_time')]


class SourceInvalidation(GenerationRecord):
    batch = fk('ewaf.SourceMutationBatch')
    program = fk('programs.Program')
    before_generation = models.PositiveBigIntegerField()
    after_generation = models.PositiveBigIntegerField()
    before_revision = models.PositiveBigIntegerField()
    after_revision = models.PositiveBigIntegerField()
    cleared_binding = fk('ewaf.RunSourceBinding', null=True, blank=True)

    class Meta(GenerationRecord.Meta):
        abstract = False
        constraints = bounds('g18_si', 'before_generation', 'after_generation', 'before_revision', 'after_revision') + [
            check('g18_si_generation', Q(after_generation=F('before_generation') + 1)),
            check('g18_si_revision', Q(after_revision=F('before_revision') + 1)),
            check('g18_si_prior_revision', Q(before_revision__gte=F('before_generation'))),
            models.UniqueConstraint(fields=['program', 'after_generation'], name='g18_si_program_generation'),
            models.UniqueConstraint(fields=['batch', 'program'], name='g18_si_batch_program')]
        indexes = [models.Index(fields=['program', 'recorded_at'], name='g18_si_program_time')]


class RequestSourceBinding(GenerationRecord):
    request = one('ewaf.DurableRequest', primary_key=True)
    source_generation = models.PositiveBigIntegerField()
    authority_generation = models.PositiveBigIntegerField()
    expected_state_revision = models.PositiveBigIntegerField()
    expected_current_binding = fk('ewaf.RunSourceBinding', null=True, blank=True)
    protocol = models.CharField(max_length=64)
    coverage_contract = models.CharField(max_length=64)
    engine_profile = models.CharField(max_length=64)
    accepted_snapshot = models.JSONField()
    context_digest = models.CharField(max_length=64)
    inventory_digest = models.CharField(max_length=64)
    submission_digest = models.CharField(max_length=64)
    valid_until = models.DateTimeField()
    evaluation_timezone = models.CharField(max_length=64)

    class Meta(GenerationRecord.Meta):
        abstract = False
        constraints = bounds('g18_rb', 'source_generation', 'authority_generation', 'expected_state_revision') + [
            check('g18_rb_positive', Q(source_generation__gt=0, authority_generation__gt=0, expected_state_revision__gt=0)),
            check('g18_rb_protocol', Q(protocol=PROTOCOL)),
            check('g18_rb_deadline', Q(valid_until__gt=F('recorded_at')))]
        indexes = [models.Index(fields=['valid_until'], name='g18_rb_deadline_idx')]


class RunSourceBinding(GenerationRecord):
    run = one('ewaf.DurableRun', primary_key=True)
    request_binding = one('ewaf.RequestSourceBinding')
    graph_digest = models.CharField(max_length=64)
    retained_count = models.PositiveIntegerField()
    eligible_count = models.PositiveIntegerField()

    class Meta(GenerationRecord.Meta):
        abstract = False
        constraints = [check('g18_run_counts', Q(eligible_count__gte=1, retained_count__gte=F('eligible_count')))]


class DevelopmentPromotion(GenerationRecord):
    program = fk('programs.Program')
    previous_binding = fk('ewaf.RunSourceBinding', null=True, blank=True)
    new_binding = one('ewaf.RunSourceBinding')
    source_generation = models.PositiveBigIntegerField()
    authority_generation = models.PositiveBigIntegerField()
    before_revision = models.PositiveBigIntegerField()
    after_revision = models.PositiveBigIntegerField()
    checked_at = models.DateTimeField()
    actor = fk(settings.AUTH_USER_MODEL)
    actor_label = models.CharField(max_length=150)
    reason_code = models.CharField(max_length=64)
    reason = models.TextField(max_length=2000)

    class Meta(GenerationRecord.Meta):
        abstract = False
        constraints = bounds('g18_dp', 'source_generation', 'authority_generation', 'before_revision', 'after_revision') + [
            check('g18_dp_revision', Q(after_revision=F('before_revision') + 1)),
            check('g18_dp_positive', Q(source_generation__gt=0, authority_generation__gt=0)),
            check('g18_dp_different', Q(previous_binding__isnull=True) | ~Q(previous_binding=F('new_binding'))),
            models.UniqueConstraint(fields=['program', 'after_revision'], name='g18_dp_program_revision')]
        indexes = [models.Index(fields=['program', 'recorded_at'], name='g18_dp_program_time')]
