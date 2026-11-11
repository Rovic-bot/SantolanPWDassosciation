"""Versioned supported-writer contract; no operational policy or schema change."""
from contextlib import contextmanager
from contextvars import ContextVar

from django.core.exceptions import ValidationError

COVERAGE = 'g18-stage8-integrated-disposable-1'
WRITERS = (
    'accounts.AdminUserGroupAndOwnPassword',
    'membership.submit_application', 'membership.record_verification', 'membership.decide_application',
    'members.update_member', 'members.change_status', 'documents.verify_document',
    'reference.DocumentType', 'reference.MembershipDocumentRequirement',
    'reference.DisabilityType', 'reference.MembershipSettings',
    'programs.definition_requirements_publication_approval_terms',
    'programs.submit_application', 'programs.change_application',
    'programs.review_photo', 'programs.correct_application',
    'programs.private_photo_access_audit', 'programs.private_document_access_audit',
    'membership.private_document_access_audit', 'members.private_document_access_audit',
    'events.save_event', 'events.change_publication',
    'assistance.review_eligibility', 'assistance.decide_assistance',
    'assistance.record_release', 'assistance.void_release',
    'ewaf.evidence_configuration_scoring_policy', 'ewaf.readiness_diagnostics',
)
_promotion = ContextVar('development_promotion_writer', default=False)


@contextmanager
def promotion_recording():
    token = _promotion.set(True)
    try:
        yield
    finally:
        _promotion.reset(token)


def validate_promotion(row):
    from .generation_models import RunSourceBinding
    if not row.new_binding_id or (row._state.adding and not _promotion.get()):
        raise ValidationError('DEVELOPMENT_PROMOTION_UNAVAILABLE')
    binding = RunSourceBinding.objects.get(pk=row.new_binding_id)
    binding.full_clean()
    request = binding.request_binding
    if (request.coverage_contract != COVERAGE or row.program_id != binding.run.program_id or
            row.source_generation != request.source_generation or row.authority_generation != request.authority_generation or
            row.before_revision != request.expected_state_revision or
            row.previous_binding_id != request.expected_current_binding_id or
            row.actor_id != request.request.actor_id or row.actor_label != request.request.actor_label or
            row.checked_at < request.recorded_at or row.checked_at >= request.valid_until or
            row.checked_at > row.recorded_at):
        raise ValidationError('DEVELOPMENT_PROMOTION_MISMATCH')
