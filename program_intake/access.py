from datetime import timedelta
import json
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from events.services import normalize_name
from members.models import Member
from programs.models import Program
from programs.terms import terms_lock
from programs.services import require_open, require_disability, grant_valid
from programs.approval_policy import grant_authorization

FAILED = "We couldn't match your information with the Association's membership records or this program's qualifications. Please check your details or contact the Association Help Desk."


def active_member(member):
    if not member or not member.is_active or member.archived_at:
        return False
    intake = member.application
    return bool(intake.status == 'approved' and intake.decided_at and intake.decided_by_id)


def registered_name(member):
    if member.first_name and member.last_name:
        suffix = member.suffix_other if member.suffix == 'other' else member.suffix
        return ' '.join(filter(None, [member.first_name, '' if member.no_middle_name else member.middle_name,
                                     member.last_name, suffix]))
    return member.full_name


def match_snapshot(member):
    return {'control': member.control_number.strip().upper(), 'name': normalize_name(registered_name(member)),
            'disabilities': sorted(member.disability_ids), 'cause': member.disability_cause,
            'visibility': member.disability_visibility}


def signature(value):
    # Internal session integrity only: never issued to the applicant as a code.
    return salted_hmac('program_intake.member_match.v1',
        json.dumps(value, sort_keys=True, separators=(',', ':')), algorithm='sha256').hexdigest()


def require_source_setup(program):
    if program.ewaf_applicable:
        from .sources import uses_sources, validate_configuration
        from ewaf.operational_services import latest_configuration
        configuration = latest_configuration(program)
        if not uses_sources(configuration):
            raise ValidationError('This program needs an authorized program-document SI policy before accepting new public applications. Contact the Association Help Desk.')
        validate_configuration(program, configuration.policy, configuration.evidence_policy)


@terms_lock()
def verify_member(program_id, *, control_number, full_name, disability_types, disability_cause,
                  disability_visibility, version):
    program = Program.objects.select_for_update().get(pk=program_id)
    try:
        require_open(program)
        require_source_setup(program)
        member = Member.objects.select_for_update().filter(control_number=control_number.strip().upper()).first()
        if not (active_member(member) and version == program.version
                and member.control_number.strip().upper() == control_number.strip().upper()
                and normalize_name(registered_name(member)) == normalize_name(full_name)
                and set(member.disability_ids) == {item.pk for item in disability_types}
                and member.disability_cause == disability_cause and member.disability_visibility == disability_visibility):
            raise ValidationError(FAILED)
    except ValidationError:
        raise ValidationError(FAILED) from None
    # Qualification feedback is safe only after the complete identity match.
    require_disability(program, member)
    grant = {**grant_authorization(program), 'program': str(program.pk), 'version': program.version,
        'member': member.pk, 'member_version': member.version,
        'expires': (timezone.now() + timedelta(seconds=settings.PROGRAM_VERIFICATION_GRANT_SECONDS)).timestamp(),
        'verification_method': 'onsite_member_match_v1', 'matched_record': signature(match_snapshot(member))}
    return {**grant, 'match_signature': signature(grant)}


def secure_grant(grant, program):
    if not grant_valid(grant, program) or grant.get('verification_method') != 'onsite_member_match_v1':
        return False
    payload = {key: value for key, value in grant.items() if key != 'match_signature'}
    if not constant_time_compare(signature(payload), grant.get('match_signature', '')):
        return False
    try:
        member = Member.objects.select_related('application').filter(pk=grant.get('member')).first()
        if not active_member(member) or member.version != grant.get('member_version'):
            return False
        require_open(program)
        require_disability(program, member)
        return constant_time_compare(signature(match_snapshot(member)), grant.get('matched_record', ''))
    except (ValueError, ValidationError):
        return False
