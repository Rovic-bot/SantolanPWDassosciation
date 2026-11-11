"""Explicit opt-in for the owner's October 26 online registration workflow.

This is the local application's collection contract, not an assertion of PDAO
approval or a new institutional retention policy. See the dated workflow note.
"""


def association_policy(file_limit, total_limit):
    reference = 'docs/online-membership-2026-10-26-validation.md'
    return {
        'public_enabled': True, 'staff_enabled': True, 'correction_enabled': True,
        'onsite_enabled': False, 'handoff_enabled': False,
        'version': 'owner-online-20261109-v1', 'form_version': 'association-word-20261109-v1',
        'applicant_profile': 'association_pdf_v1',
        'applicant_profile_reference': 'Santolan_PWD_Membership_Form.docx; existing digital household fields',
        'field_contract_reference': reference,
        'authority_reference': 'Owner instruction, 2026-11-09: office invitation, in-person verification, then final membership approval and confirmation email',
        'privacy_version': 'association-online-20261109-v1',
        'privacy_notice': 'Your submitted details are saved privately for authorized Association staff to review your membership application. '
            'Confirm your details before submitting. Visit the Help Desk for verification and corrections. '
            'Only an administrator can approve membership and create a member record. '
            'For online applications, your email and PWD number are required. The Association uses its Gmail account '
            'to send pending-review notices and an invitation to visit the barangay office to verify your information. '
            'Bring your PWD ID. Your application remains pending until office verification and final Admin approval. '
            'A separate email then confirms your Association membership. '
            'Your original submission and review history are retained; ask the Help Desk about retention and privacy requests. '
            'Save or print your receipt before finishing, and protect downloaded copies on shared devices.',
        'retention_reference': reference + ': preserve original submissions and audit history; no new disposal schedule',
        'staff_assignments_reference': 'Existing dashboard, registration view, correction and membership decision permissions',
        'upload_policy_reference': 'No online attachments in this workflow; bring physical requirements onsite',
        'onsite_instructions': 'For online applications, check your email for an office-verification invitation. '
            'Bring your PWD ID, reference and the Association requirements to the barangay office / Help Desk. '
            'You are not yet a member. After verification and final Admin approval, a separate email confirms membership.',
        'security_review_reference': reference + ': local workflow validation; not external certification',
        'correction_procedure_reference': 'Existing versioned administrator correction before membership decision',
        'context_seconds': 3600, 'attempt_window_seconds': 900,
        'address_attempt_limit': 120, 'session_attempt_limit': 40, 'reference_attempt_limit': 40,
        'file_max_bytes': file_limit, 'total_max_bytes': total_limit,
        'body_max_bytes': 131072, 'file_count_limit': 1, 'upload_slots': [],
    }
