"""No production defaults: missing institutional/security contracts fail closed.

ASSOCIATION_REGISTRATION_POLICY is absent unless explicitly enabled in settings.
The owner's online workflow supplies its documented contract; test fixtures are not policy.
"""
from copy import deepcopy
import hashlib
import json

from django.conf import settings
from django.core.exceptions import PermissionDenied

from .guidance import ASSOCIATION_REQUIREMENTS, LEGACY_ASSOCIATION_REQUIREMENTS

SLOTS = {'photo_2x2': 'One 2×2 photograph', 'civil_document': 'Birth OR Marriage Certificate',
         'voter_certificate': "Voter's Certificate"}
STATES = ('received', 'under_review', 'needs_information', 'ready_for_onsite', 'onsite_review')
SCOPES = ('public', 'staff', 'onsite', 'correction')


class RegistrationUnavailable(PermissionDenied):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


def policy_for(scope):
    raw = getattr(settings, 'ASSOCIATION_REGISTRATION_POLICY', None)
    if scope not in SCOPES or not isinstance(raw, dict) or raw.get(f'{scope}_enabled') is not True:
        raise RegistrationUnavailable('This registration action is currently unavailable.')
    policy = deepcopy(raw)
    profile_kind = policy.get('applicant_profile', 'minimal_v1')
    if profile_kind not in ('minimal_v1', 'onsite_applicant_v1', 'association_pdf_v1'):
        raise RegistrationUnavailable('The applicant field contract is unavailable.')
    if profile_kind in ('onsite_applicant_v1', 'association_pdf_v1') and (
            not isinstance(policy.get('applicant_profile_reference'), str)
            or not policy['applicant_profile_reference'].strip()):
        raise RegistrationUnavailable('The expanded applicant field contract is incomplete.')
    strings = ('version', 'form_version', 'field_contract_reference', 'authority_reference',
               'privacy_version', 'privacy_notice', 'retention_reference', 'staff_assignments_reference',
               'upload_policy_reference', 'onsite_instructions', 'security_review_reference')
    numbers = ('context_seconds', 'attempt_window_seconds', 'address_attempt_limit', 'session_attempt_limit',
               'reference_attempt_limit', 'file_max_bytes', 'total_max_bytes', 'body_max_bytes', 'file_count_limit')
    if any(not isinstance(policy.get(key), str) or not policy[key].strip() for key in strings):
        raise RegistrationUnavailable('The registration contract is incomplete.')
    if any(type(policy.get(key)) is not int or policy[key] <= 0 for key in numbers):
        raise RegistrationUnavailable('The registration security contract is incomplete.')
    slots = policy.get('upload_slots')
    if (not isinstance(slots, list) or any(not isinstance(slot, str) for slot in slots)
            or len(slots) != len(set(slots)) or any(slot not in SLOTS for slot in slots)
            or policy['file_count_limit'] < len(slots)
            or policy['file_count_limit'] > settings.DATA_UPLOAD_MAX_NUMBER_FILES
            or policy['file_max_bytes'] > settings.MEMBERSHIP_FILE_MAX_BYTES
            or policy['total_max_bytes'] > settings.MEMBERSHIP_TOTAL_MAX_BYTES
            or policy['file_max_bytes'] > policy['total_max_bytes']):
        raise RegistrationUnavailable('The registration upload contract is incomplete.')
    if scope == 'onsite':
        methods = policy.get('onsite_methods')
        if (not isinstance(policy.get('onsite_procedure_reference'), str) or not policy['onsite_procedure_reference'].strip()
                or not isinstance(methods, list) or not methods
                or any(not isinstance(value, str) or not value.strip() or len(value) > 120 for value in methods)):
            raise RegistrationUnavailable('The onsite procedure is not approved/configured.')
    if scope == 'correction' and (not isinstance(policy.get('correction_procedure_reference'), str)
            or not policy['correction_procedure_reference'].strip()):
        raise RegistrationUnavailable('The correction procedure is not approved/configured.')
    policy['checklist'] = deepcopy(ASSOCIATION_REQUIREMENTS if profile_kind == 'association_pdf_v1'
                                  else LEGACY_ASSOCIATION_REQUIREMENTS)
    return policy


def available(scope):
    try:
        policy_for(scope)
        return True
    except RegistrationUnavailable:
        return False
