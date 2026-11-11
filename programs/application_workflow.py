"""Verified screening; submission may fill a blank member email, never assessment data."""
from datetime import timedelta
import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from events.services import normalize_name, normalize_phone
from members.models import Member
from .models import Program
from .terms import terms_lock

CONTRACT = 'confirmed_program_application_v1'
FAILED = ('We could not confirm your membership using the details provided. Please review your entries '
    'or contact the Association Help Desk. New applicants may follow the membership application guide.')


def enabled():
    return getattr(settings, 'PROGRAM_APPLICATION_WORKFLOW_ENABLED', False)


def signature(value):
    return salted_hmac(CONTRACT, json.dumps(value, sort_keys=True, default=str), algorithm='sha256').hexdigest()


def registered_name(member):
    if member.first_name and member.last_name:
        suffix = member.suffix_other if member.suffix == 'other' else member.suffix
        return ' '.join(filter(None, (member.first_name, '' if member.no_middle_name else member.middle_name,
            member.last_name, suffix)))
    return member.full_name


def identity(member):
    return {'member': member.pk, 'version': member.version, 'name': normalize_name(registered_name(member)),
        'control': member.control_number.strip().upper(), 'birthdate': member.birthdate,
        'phone': normalize_phone(member.contact_number), 'active': member.is_active,
        'archived': member.archived_at, 'intake_status': member.application.status,
        'decided_at': member.application.decided_at, 'decided_by': member.application.decided_by_id,
        'classifications': sorted(member.disability_ids)}


def confirmed_member(member):
    from members.update_services import requires_verification
    return bool(member and member.is_active and not member.archived_at
        and member.application.status == 'approved' and member.application.decided_at
        and member.application.decided_by_id and not requires_verification(member))


def screening(member, program):
    allowed = set(program.eligible_disability_types.values_list('pk', flat=True))
    if not allowed:
        if program.allows_all_disability_types:
            return 'passed', 'Screening passed. Proceed to Admin review after submitting the required information and evidence.'
        return 'unable', 'The program eligibility profile is incomplete. Contact the Association Help Desk.'
    recorded = set(member.disability_ids)
    active = set(program.eligible_disability_types.filter(is_active=True).values_list('pk', flat=True))
    from members.models import DisabilityType
    current = set(DisabilityType.objects.filter(pk__in=recorded, is_active=True).values_list('pk', flat=True))
    if active & current:
        return 'passed', 'Screening passed. At least one recorded disability classification matches this program. Other mandatory requirements still need Admin review.'
    if not recorded or recorded != current or allowed != active:
        return 'unable', 'The recorded disability classifications need clarification before this requirement can be confirmed. Contact the Association Help Desk for review.'
    return 'not_met', ('You cannot proceed with this application because the disability types in your '
        "verified member record do not match this program's target disability types. "
        'Review the program requirements or contact the Association Help Desk if your record needs correction.')


def require_application_policy(program):
    from .mandatory_ewaf import has_required_types
    if not program.ewaf_applicable or not program.slots or not has_required_types(program):
        raise ValidationError('Complete the EWAF program, beneficiary slots and disability eligibility profile first.')
    from .services import require_open
    require_open(program)
    if not program.policy_authorized_by_id:
        raise ValidationError('The program needs a recorded policy authorization before accepting applications.')
    if program.ewaf_applicable:
        from ewaf.intake_policy import require_configuration
        require_configuration(program)


@terms_lock()
def verify(program_id, *, version, control_number, full_name):
    from .approval_policy import grant_authorization
    program = Program.objects.select_for_update().get(pk=program_id)
    require_application_policy(program)
    if version != program.version:
        raise ValidationError('The program changed. Reload its requirements before continuing.')
    member = Member.objects.select_for_update().select_related('application').filter(
        control_number=control_number.strip().upper()).first()
    if not (confirmed_member(member)
            and member.control_number.strip().upper() == control_number.strip().upper()
            and normalize_name(registered_name(member)) == normalize_name(full_name)):
        raise ValidationError(FAILED)
    outcome, message = screening(member, program)
    if outcome != 'passed':
        return None, outcome, message
    grant = {**grant_authorization(program), 'program': str(program.pk), 'version': program.version,
        'member': member.pk, 'member_version': member.version,
        'expires': (timezone.now() + timedelta(seconds=settings.PROGRAM_VERIFICATION_GRANT_SECONDS)).timestamp(),
        'application_workflow': CONTRACT, 'identity': signature(identity(member)),
        # Values already supplied by this person; no stored profile is exposed.
        'entered_name': full_name}
    return {**grant, 'signature': signature(grant)}, outcome, message


def secure_grant(grant, program):
    from .services import grant_valid
    if not grant_valid(grant, program) or grant.get('application_workflow') != CONTRACT:
        return False
    payload = {key: value for key, value in grant.items() if key != 'signature'}
    if not constant_time_compare(signature(payload), grant.get('signature', '')):
        return False
    try:
        member = Member.objects.select_related('application').filter(pk=grant.get('member')).first()
        require_application_policy(program)
        return bool(confirmed_member(member) and screening(member, program)[0] == 'passed'
            and constant_time_compare(signature(identity(member)), grant.get('identity', '')))
    except (ValidationError, ValueError, TypeError):
        return False


def publication_configuration_problem(program):
    """Explain the existing publication gate without exposing internal errors."""
    if not program.ewaf_applicable:
        return ''
    from ewaf.operational_services import latest_configuration, configuration_source
    try:
        row = latest_configuration(program, require_locked=False)
    except ValidationError:
        from ewaf.vault_policy import enabled as vault_enabled
        if vault_enabled():
            return 'Approve shared weights and scoring rules in the EWAF Configuration Vault before publishing this program.'
        return ('EWAF scoring settings are missing or need correction. Open EWAF settings for this program, '
                'complete the scoring rules and weights, then have an authorized administrator lock the configuration before publishing.')
    from ewaf.vault_policy import scoring_pending, SCORING_PENDING_MESSAGE
    if row.uses_dataset_scoring:
        from ewaf.revised.live_services import require_binding
        try:
            require_binding(row)
        except ValidationError as error:
            return ' '.join(error.messages)
        return ''  # Complete policy and exact binding; future applicant bounds are not required here.
    if scoring_pending(row.policy):
        from ewaf.intake_policy import validate_weights
        try:
            validate_weights(row)
        except ValidationError as error:
            return ' '.join(error.messages)
        return ''  # Approved weights suffice for publication; scoring stays blocked.
    if row.status != 'LOCKED':
        if row.vault_revision_id:
            return ''  # Already approved centrally; bound to program terms on publication.
        return ('The EWAF configuration is saved but has not been approved and locked. '
                'An authorized administrator must review and lock it in EWAF settings before publishing.')
    if row.source != configuration_source(program):
        return ('The locked EWAF configuration no longer matches the current program terms or evidence policy. '
                'Review EWAF settings and authorize a new configuration version before publishing.')
    return ''


def require_publication_policy(program):
    from .approval_policy import require_binding
    require_binding(program, first_publication=program.published_at is None)
    if not program.policy_authorized_at or not program.policy_authorized_by_id:
        raise ValidationError('Record program policy authorization before publication.')
    if not program.selection_method.strip() or not program.photo_instructions.strip():
        raise ValidationError('Record the selection method and identity-evidence instructions before publication.')
    if not program.slots:
        raise ValidationError('Set positive beneficiary slots before publishing an EWAF program.')
    from .mandatory_ewaf import has_required_types
    if not program.ewaf_applicable or not has_required_types(program):
        raise ValidationError('All programs require EWAF and applicable disability types.')
    problem = publication_configuration_problem(program)
    if problem:
        raise ValidationError(problem)


def availability(program):
    if not program.registration_available:
        return False
    try:
        require_application_policy(program)
    except ValidationError:
        return False
    return True
