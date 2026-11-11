"""Plain-language projections; the engine retains its complete diagnostic details."""
import re


INPUT_MESSAGES = {
    'MEMBERSHIP_PROVENANCE_REVIEW_REQUIRED': 'The membership approval or manual PRPWD check needs attention. Open the member record.',
    'CRITERION_MISSING': 'Scoring inputs have not been accepted under this program\'s rules. Review the member record and scoring configuration.',
    'BINDING_INVALID': 'The scoring authorization does not match this program. Review the program settings.',
    'TERMS_CHANGED': 'Program details changed after scoring authorization. Review the program settings.',
    'CURRENT_INFORMATION_REVIEW_REQUIRED': 'The applicant reported information needing review. Open View applicant.',
    'ELIGIBILITY_PENDING': 'Application eligibility is pending. Open View applicant.',
    'ELIGIBILITY_STALE': 'The member or program record changed after eligibility was reviewed. Recheck the changed details in View applicant.',
    'QUALIFICATION_FAILED': 'The current member record does not meet this program\'s qualification requirements. Review the qualification in View applicant.',
    'QUALIFICATION_REVIEW_REQUIRED': 'The member\'s qualification information is incomplete. Review the member record and View applicant.',
    'IDENTITY_REVIEW_REQUIRED': 'Required identity evidence is missing or needs a new review. Check the evidence in View applicant.',
    'MEMBERSHIP_INVALID': 'The applicant\'s membership is not currently valid. Open the member record.',
    'MEMBER_INACTIVE': 'The applicant\'s membership is inactive. Open the member record.',
    'APPLICATION_INVALID': 'The application record is incomplete or inconsistent. Open View applicant.',
    'SUBMISSION_PROVENANCE_REVIEW_REQUIRED': 'The application submission record needs review. Open View applicant.',
    'HISTORICAL_DECISION_REASSESSMENT_REQUIRED': 'An earlier assistance decision needs reassessment before this applicant can be ranked again.',
    'CHECKLIST_INCOMPLETE': 'The eligibility checklist is incomplete. Open View applicant.',
    'CHECKLIST_FAILED': 'An eligibility checklist requirement was not met. Open View applicant.',
    'REQUIRED_EVIDENCE_MISSING': 'A required applicant document or evidence item is missing. Open View applicant.',
    'ELIGIBILITY_INELIGIBLE': 'The applicant has been reviewed as ineligible and is not included in ranking.',
    'APPLICATION_NOT_CANDIDATE': 'An application needs eligibility review before ranking. Open Program Applications & Eligibility to resolve it.',
    'APPLICATION_REVIEW_UNRESOLVED': 'An application needs eligibility review before ranking. Open Program Applications & Eligibility to resolve it.',
    'SOURCE_CHANGED': 'The accepted scoring inputs predate a record change. Open Review ranking inputs.',
}


def messages_for_officers(messages):
    result = []
    for value in messages:
        text = str(value)
        code = text.rsplit(': ', 1)[-1]
        if code in INPUT_MESSAGES:
            text = INPUT_MESSAGES[code]
        elif any(code in text for code in ('APPLICATION_NOT_CANDIDATE', 'APPLICATION_REVIEW_UNRESOLVED')):
            text = 'An application needs eligibility review before ranking. Open Program Applications & Eligibility to resolve it.'
        elif text.startswith('eligible_pool:'):
            text = 'No eligible applicants are ready to rank yet. Review applications and their required information.'
        elif re.search(r'(authority_reference|authorized_scope|approval_date|effective_from|effective_until|selection_rule|tie_rule|tie_procedure|classification_mode|edge_cases|pa_scope|pa_period|[A-Z]{2}\.|PR_|[A-Z]{3,}_[A-Z_]+|configuration:|timezone)', text):
            if any(word in text.lower() for word in ('stale', 'source_changed', 'evidence', 'assessment', 'expired', 'pool')):
                text = 'Some applicant information needs verification. Review the applicants before calculating.'
            else:
                text = 'Scoring settings are incomplete or need approval. Review the program settings.'
        if text not in result:
            result.append(text)
    return result


def simplify_form_errors(form):
    if form.is_bound:
        for key, errors in list(form.errors.items()):
            form.errors[key] = form.error_class(messages_for_officers(errors))
    return form
