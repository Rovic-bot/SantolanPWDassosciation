"""Reasoned fictional decisions under the existing source/authority fence.

No operational consumer, slot allocation, release, public projection or score edit.
"""
from contextvars import ContextVar
from uuid import UUID

from django.core.exceptions import ValidationError
from django.utils import timezone
from core.permissions import require_workspace_permissions
from . import generation_processing as processing, generation_services as generation
from .decision_models import (DevelopmentHumanDecision as Decision, DevelopmentHumanDecisionAudit as Audit,
    DECISION_PROTOCOL, DECISIONS)
from .evidence import digest
from .four_policy import POOL_ENGINE
from .generation_records import bounded

_recording = ContextVar('four_human_decision_recording', default=False)


def require_recording():
    if not _recording.get():
        raise ValidationError('USE_HUMAN_DECISION_SERVICE')


def retained_payload(binding, application_id):
    key = str(application_id)
    accepted = binding.run.snapshot['eligible'].get(key)
    if accepted is None:
        raise ValidationError('FOUR_CONFIRMED_ELIGIBLE_RESULT_REQUIRED')
    result = binding.run.results.get(application_id=application_id)
    return {'version': DECISION_PROTOCOL, 'application': key, 'result_digest': result.digest,
        'eligibility': accepted['program_relevance_eligibility'], 'calculation': result.calculation,
        'comparison': result.comparison, 'operational_ready': False, 'actually_assisted': False}


def validate_record(row):
    binding = row.run_binding
    from .generation_models import DevelopmentPromotion
    promotion = DevelopmentPromotion.objects.filter(new_binding=binding).first()
    if (row.protocol != DECISION_PROTOCOL or row.decision not in DECISIONS or
            not row.reason.strip() or len(row.reason) > 1000 or
            binding.run.snapshot.get('engine') != POOL_ENGINE or
            binding.run.program_id != row.program_id or row.application.program_id != row.program_id or
            row.run_digest != binding.run.digest or row.graph_digest != binding.graph_digest or
            row.source_generation != binding.request_binding.source_generation or
            row.authority_generation != binding.request_binding.authority_generation or
            not promotion or row.state_revision != promotion.after_revision or
            row.payload != retained_payload(binding, row.application_id)):
        raise ValidationError('HUMAN_DECISION_PROVENANCE_INVALID')
    for value in (row.revision, row.source_generation, row.authority_generation, row.state_revision):
        bounded(value, positive=True)
    if row.previous_id:
        previous = row.previous
        previous.audit.clean()
        if (previous.program_id != row.program_id or previous.application_id != row.application_id or
                previous.revision + 1 != row.revision or previous.recorded_at > row.recorded_at or
                previous.pk == row.pk or digest(previous.content()) != previous.digest or
                previous.audit.decision_digest != previous.digest):
            raise ValidationError('HUMAN_DECISION_LINEAGE_INVALID')
    elif row.revision != 1:
        raise ValidationError('HUMAN_DECISION_LINEAGE_INVALID')
    audit = row.audit
    audit.clean()
    if (audit.program_id, audit.actor_id, audit.actor_label, audit.recorded_at, audit.decision_digest) != (
            row.program_id, row.actor_id, row.actor_label, row.recorded_at, row.digest):
        raise ValidationError('HUMAN_DECISION_AUDIT_MISMATCH')


def _persist(row):
    row.digest = digest(row.content())
    audit = Audit(program_id=row.program_id, actor_id=row.actor_id, actor_label=row.actor_label,
        recorded_at=row.recorded_at, decision_digest=row.digest)
    audit.digest = digest(audit.content())
    token = _recording.set(True)
    try:
        audit.save()
        row.audit = audit
        row.save()
    finally:
        _recording.reset(token)
    return row


def record(program_id, *, user, expected, run_id, application_id, decision, reason,
           expected_revision, expected_previous):
    if (type(run_id) is not int or decision not in DECISIONS or type(reason) is not str or
            not reason.strip() or len(reason) > 1000):
        raise ValidationError('HUMAN_DECISION_REASON_REQUIRED')
    bounded(expected_revision)
    if expected_previous is not None:
        bounded(expected_previous, positive=True)
    try:
        if type(application_id) not in (str, UUID):
            raise ValueError
        application_id = UUID(str(application_id))
    except (ValueError, TypeError):
        raise ValidationError('FOUR_APPLICATION_UUID_REQUIRED')
    with processing._fence(program_id, user) as (actor, authority, program, state, applications):
        require_workspace_permissions(actor, 'assistance.decide_assistance')
        generation._expect(state, authority, expected)
        binding = processing._current(actor, authority, program, state, applications, sticky=True)
        if binding.run_id != run_id or binding.run.snapshot['engine'] != POOL_ENGINE:
            raise ValidationError('FOUR_CURRENT_RUN_REQUIRED')
        latest = Decision.objects.select_for_update().filter(program=program, application_id=application_id).order_by('-revision').first()
        if latest:
            latest.clean()
            # Exact retry of the same predecessor proposal has no duplicate audit.
            if (latest.revision == expected_revision + 1 and latest.previous_id == expected_previous and
                    latest.run_binding_id == binding.pk and latest.actor_id == actor.pk and
                    latest.decision == decision and latest.reason == reason.strip()):
                processing._current(actor, authority, program, state, applications, sticky=True)
                require_workspace_permissions(processing.durable._authorize(actor), 'assistance.decide_assistance')
                return latest
        if (latest.revision if latest else 0, latest.pk if latest else None) != (expected_revision, expected_previous):
            raise ValidationError('STALE_HUMAN_DECISION_REVISION')
        row = Decision(program=program, actor=actor, actor_label=actor.get_username(), run_binding=binding,
            application_id=application_id, decision=decision, reason=reason.strip(), revision=expected_revision + 1,
            previous=latest, source_generation=state.generation, authority_generation=authority.generation,
            state_revision=state.revision, run_digest=binding.run.digest, graph_digest=binding.graph_digest,
            payload=retained_payload(binding, application_id), recorded_at=timezone.now())
        _persist(row)
        # A post-write failure must roll back both the decision and its audit.
        processing._current(actor, authority, program, state, applications, sticky=False)
        require_workspace_permissions(processing.durable._authorize(actor), 'assistance.decide_assistance')
        generation._expect(state, authority, expected)
        row.clean()
        return row


def inspect_history(program_id, *, user, limit=50, page=1):
    bounded(limit, positive=True)
    bounded(page, positive=True)
    if limit > 50:
        raise ValidationError('HUMAN_HISTORY_PAGE_LIMIT')
    with processing._fence(program_id, user) as (actor, authority, program, state, applications):
        require_workspace_permissions(actor, 'assistance.decide_assistance')
        query = Decision.objects.filter(program=program, actor=actor).order_by('-pk')
        total = query.count()
        pages = max(1, (total + limit - 1) // limit)
        page = min(page, pages)
        start = (page - 1) * limit
        rows = list(query.select_related('audit', 'previous', 'run_binding__run', 'run_binding__request_binding')[start:start + limit])
        checked = set()
        for row in rows:
            row.clean()
            if row.run_binding_id not in checked:
                processing.durable._assert_history(row.run_binding.run)
                checked.add(row.run_binding_id)
        return {'rows': rows, 'total': total, 'limit': limit, 'page': page, 'pages': pages,
            'previous_page': page - 1 if page > 1 else None, 'next_page': page + 1 if page < pages else None}
