"""Descriptions of the existing workflow used by the simplified program setup.

These describe the owner-confirmed configured-evidence workflow. Stored custom
text and previously approved/published terms are retained; this helper only fills
missing guidance on an unauthorised draft with no applications.
"""
from .application_workflow import enabled
from .terms import is_protected


STANDARD_GUIDANCE = {
    'selection_method': (
        'Authorized Admin reviews each application for eligibility. Eligible applicants are ranked using '
        'the approved EWAF configuration. Authorized Admin records beneficiary selections within the '
        'approved slot limit. Submission and eligibility do not automatically select an applicant.'),
    'photo_instructions': (
        'Photo evidence is required only when listed in the configured program '
        'requirements. An authorized Admin reviews the submitted evidence. '
        'For help with the application or requirements, contact the '
        'Barangay Santolan PWD Association Help Desk.'
    ),
}


def missing_draft_guidance(program):
    """Preview missing text; callers persist it only in an audited transaction."""
    missing = {name: text for name, text in STANDARD_GUIDANCE.items()
               if not getattr(program, name).strip()}
    if (not missing or not enabled() or program.status not in ('draft', 'archived')
            or program.published_at or program.policy_authorized_at
            or program.policy_authorized_by_id or is_protected(program)):
        return {}
    if not program._state.adding and program.applications.exists():
        return {}
    return missing
