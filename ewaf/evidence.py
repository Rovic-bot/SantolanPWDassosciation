"""Minimal server-resolved provenance. Nothing in this module authorizes scoring."""
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from documents.services import file_digest

CRITERIA = ('SI', 'ES', 'PA', 'ND', 'PR')
SOURCE_TYPES = {
    'SI': ('monthly_income', 'socioeconomic_assessment', 'government_status', 'income_category', 'four_ps_membership'),
    'ES': ('employment_text', 'employment_category', 'employment_status'),
    'PA': ('successful_releases',), 'ND': ('dependent_count',),
    'HI': ('household_monthly_income',), 'HM': ('household_member_count',),
    'PR': ('program_relevance',),
}
ALL_CRITERIA = CRITERIA + ('HI', 'HM')


def criterion_codes(snapshot):
    from .household_criteria import CRITERIA as household
    return household + ('PR',) if 'HI' in snapshot.get('criteria', {}) or 'HM' in snapshot.get('criteria', {}) else CRITERIA


VIEW = ('programs.view_program', 'programs.view_programapplication', 'members.view_member',
        'ewaf.view_criterionassessment', 'ewaf.view_evidencepolicyrevision',
        'ewaf.view_eligibilityreadinesssnapshot')


def canonical(value):
    def convert(item):
        if isinstance(item, (date, datetime, Decimal, UUID)):
            return str(item)
        raise TypeError(f'Unsupported evidence value: {type(item).__name__}')
    return json.loads(json.dumps(value, default=convert, sort_keys=True, allow_nan=False))


def digest(value):
    return hashlib.sha256(json.dumps(canonical(value), sort_keys=True, ensure_ascii=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def recorded_timestamp(value):
    try:
        return isinstance(value, str) and parse_datetime(value) is not None
    except (ValueError, TypeError):
        return False


def validate_policy(snapshot):
    if (not isinstance(snapshot, dict) or set(snapshot) != {'criteria'} or
            not isinstance(snapshot['criteria'], dict) or set(snapshot['criteria']) != set(criterion_codes(snapshot))):
        raise ValidationError('Record HI, SI, ES, PA, HM and PR definitions for household criteria, or retain the complete historical SI, ES, PA, ND, PR version; no scoring or authorization fields.')
    allowed = {'definition', 'source_types', 'unit', 'categories', 'rubric', 'observation_rule',
               'freshness_days', 'rule_authority', 'pa_scope', 'evidence_mappings', 'rubric_definition'}
    for code, rule in snapshot['criteria'].items():
        if not isinstance(rule, dict) or set(rule) - allowed:
            raise ValidationError('Unsupported evidence policy field.')
        if not isinstance(rule.get('definition'), str) or not rule['definition'].strip():
            raise ValidationError(f'{code}: record the definition or explicitly describe what remains unresolved.')
        sources = rule.get('source_types')
        if (not isinstance(sources, list) or not sources or any(not isinstance(item, str) for item in sources) or
                len(sources) != len(set(sources)) or set(sources) - set(SOURCE_TYPES[code])):
            raise ValidationError(f'{code}: select distinct supported source types.')
        categories = rule.get('categories', {})
        if not isinstance(categories, dict) or any(not isinstance(k, str) or not k.strip() or
                not isinstance(v, str) or not v.strip() for k, v in categories.items()):
            raise ValidationError('Categories must be documented identifiers and definitions, never numerical scores.')
        if categories and code not in ('ES', 'PR') and not (code == 'SI' and set(sources) & {'income_category', 'four_ps_membership'}):
            raise ValidationError('Category definitions require a categorical source.')
        from members.profile import EMPLOYMENT, INCOME
        for source, choices in (('income_category', INCOME), ('employment_status', EMPLOYMENT), ('four_ps_membership', [('Yes', 'Yes'), ('No', 'No')])):
            if source in sources and (not categories or set(categories) - set(dict(choices))):
                raise ValidationError('Define the recorded membership category identifiers explicitly; no legacy category equivalence is assumed.')
        for key in ('unit', 'rubric', 'observation_rule', 'rule_authority', 'pa_scope'):
            if key in rule and (not isinstance(rule[key], str) or len(rule[key]) > 2000):
                raise ValidationError('Evidence definitions must be bounded text.')
        days = rule.get('freshness_days')
        if days is not None and (type(days) is not int or days < 1 or days > 36500):
            raise ValidationError('Freshness must be an explicitly documented positive day interval.')
        if (days is not None or rule.get('observation_rule') or categories or rule.get('rubric') or rule.get('pa_scope')) and not rule.get('rule_authority', '').strip():
            raise ValidationError('Record the separate authority reference for measurement/category/freshness rules.')
        from .evidence_rules import validate_contract
        if rule.get('rubric_definition') is not None and code != 'PR':
            raise ValidationError('A relevance rubric belongs only to PR.')
        validate_contract(rule)
    if len(json.dumps(snapshot)) > 24000:
        raise ValidationError('Evidence policy is too large.')


def approval_context(program):
    from programs.models import ProgramApprovalControl
    from programs.terms import snapshot_terms, terms_digest
    control = ProgramApprovalControl.objects.filter(program=program).first()
    return {'control_version': control.version if control else 0,
            'binding': control.active_binding_id if control else None,
            'terms_revision': control.current_revision_id if control else None,
            'terms_digest': control.current_digest if control else '',
            'actual_terms_digest': terms_digest(snapshot_terms(program))}


def source_context(application):
    """Caller resolves a fresh application. GET does not lock or create anything.

    Writes call this only after Terms, Program, Application and Member locks.
    No cross-program release row locks: supported writers share the Member lock.
    """
    from assistance.models import AssistanceCase, AssistanceLog, AssistanceRelease
    from assistance.services import case_snapshot
    from documents.models import MembershipApplicationDocument
    member, program = application.member, application.program
    case = AssistanceCase.objects.filter(application=application).first()
    review_log = AssistanceLog.objects.filter(application=application, action='eligibility_reviewed').first()
    documents = []
    for document in application.documents.select_related('source_document', 'source_verification', 'requirement').order_by('pk'):
        latest = document.source_document.verifications.first() if document.source_document_id else None
        documents.append({'id': str(document.pk), 'requirement': document.requirement_id,
            'program': str(document.requirement.program_id), 'digest': file_digest(document),
            'reusable_document_type': document.requirement.reusable_document_type_id,
            'source_membership_requirement': document.source_document.requirement_id if document.source_document_id else None,
            'source_document_type': document.source_document.requirement.document_type_id if document.source_document_id else None,
            'source_digest': file_digest(document.source_document) if document.source_document_id else None,
            'source': str(document.source_document_id) if document.source_document_id else None,
            'source_member_application': str(document.source_document.application_id) if document.source_document_id else None,
            'source_verification': document.source_verification_id,
            'latest_verification': review_manifest(latest) if latest else None})
    supporting = []
    for document in MembershipApplicationDocument.objects.filter(application=member.application).order_by('pk'):
        latest = document.verifications.first()
        supporting.append({'id': str(document.pk), 'digest': file_digest(document),
                           'membership_requirement': document.requirement_id,
                           'document_type': document.requirement.document_type_id,
                           'review': review_manifest(latest) if latest else None})
    photo = application.current_photo
    photo_review = photo.reviews.first() if photo else None
    releases = list(AssistanceRelease.objects.filter(application__member=member).order_by('pk').values(
        'id', 'application_id', 'active_application_id', 'released_on', 'recorded_at', 'recorded_by_id',
        'assistance_type', 'voided_at', 'voided_by_id'))
    successful = [row for row in releases if row['voided_at'] is None]
    intake = member.application
    verification_event = intake.events.filter(action__in=['prpwd_verified', 'prpwd_not_verified']).order_by('-occurred_at', '-pk').first()
    approval_event = intake.events.filter(action__in=['approved', 'rejected']).order_by('-occurred_at', '-pk').first()
    submission = application.source_snapshot if isinstance(application.source_snapshot, dict) else {}
    profile = {'monthly_income': member.monthly_income,
               'employment_information': member.employment_information, 'dependents': member.dependents}
    if member.income_category or member.employment_status:
        profile.update(income_category=member.income_category, income_category_label=member.income_category_label,
                       employment_status=member.employment_status)
    if member.registration_profile or member.household_monthly_income is not None or member.household_members is not None:
        profile.update(household_monthly_income=member.household_monthly_income,
            household_members=member.household_members, registration_profile_digest=digest(member.registration_profile))
    classifications = member.disability_ids
    from programs.information_confirmation import confirmation_context
    confirmation = confirmation_context(application)
    from programs.schedule_services import eligibility_schedule_witness
    schedule_witness = eligibility_schedule_witness(application, case) if case and case.program_version != program.version else {}
    return canonical({**({'current_information': confirmation} if confirmation else {}),
        **({'eligibility_schedule_revision': schedule_witness} if schedule_witness else {}),
        'application': str(application.pk), 'application_version': application.version,
        'program': str(program.pk), 'program_version': program.version, 'member': member.pk,
        'member_version': member.version, 'member_active': member.is_active and not member.archived_at,
        'profile_digest': digest(profile),
        'membership': {'intake': str(intake.pk), 'status': intake.status, 'verified': intake.prpwd_verified,
            'verified_at': intake.prpwd_verified_at, 'verified_by': intake.prpwd_verified_by_id,
            'decided_at': intake.decided_at, 'decided_by': intake.decided_by_id,
            'verification_event': verification_event.pk if verification_event else None,
            'approval_event': approval_event.pk if approval_event else None,
            'audit_matches': bool(verification_event and approval_event and
                verification_event.action == 'prpwd_verified' and approval_event.action == 'approved' and
                verification_event.actor_id == intake.prpwd_verified_by_id and approval_event.actor_id == intake.decided_by_id)},
        'status': application.status, 'reference_present': bool(application.public_reference),
        'submitted_at': application.submitted_at, 'submission_digest': digest(application.source_snapshot),
        'submission_provenance_valid': (str(submission.get('member_id')) == str(member.pk)
            and type(submission.get('member_version')) is int and type(submission.get('program_version')) is int
            and recorded_timestamp(submission.get('membership_verified_at'))
            and recorded_timestamp(submission.get('policy_authorized_at'))),
        'requirements': application.requirements_snapshot, 'answers_digest': digest(application.answers),
        **({'calendar_photo_required': False} if submission.get('evidence_policy') ==
            'configured_program_requirements_v1' and not application.current_photo_id else {}),
        'disability': member.disability_type_id,
        **({'disabilities': classifications} if classifications != (
            [member.disability_type_id] if member.disability_type_id else []) else {}),
        'qualifications': list(program.eligible_disability_types.order_by('pk').values_list('pk', flat=True)),
        'active_qualifications': list(program.eligible_disability_types.filter(is_active=True).order_by('pk').values_list('pk', flat=True)),
        'photo': {'id': str(photo.pk), 'application': str(photo.application_id), 'digest': file_digest(photo),
            'review': photo_review.pk if photo_review else None, 'outcome': photo_review.outcome if photo_review else None,
            'member_version': photo_review.member_version if photo_review else None,
            'integrity_basis': 'bytes_at_G12_capture_not_original_verification'} if photo else None,
        'documents': documents, 'supporting_documents': supporting,
        'case': {'id': case.pk, 'digest': digest(case_snapshot(case)), 'eligibility': case.eligibility_id,
            'active': case.eligibility.is_active, 'checklist': case.checklist, 'decision': case.decision,
            'member_version': case.member_version, 'program_version': case.program_version,
            'review_log': review_log.pk if review_log else None,
            'log_matches': bool(review_log and review_log.snapshot.get('after') == case_snapshot(case))} if case else None,
        'approval': approval_context(program),
        'pa': {'scope': 'diagnostic_all_retained_successful_records_only',
               'successful': successful, 'all_release_state_digest': digest(releases), 'count': len(successful)}})


def review_manifest(review):
    return canonical({'id': review.pk, 'verified': review.verified, 'expires_on': review.expires_on,
        'document': str(review.document_id), 'membership_requirement': review.document.requirement_id,
        'document_type': review.document.requirement.document_type_id,
        'member_version': review.member_version, 'digest': review.file_digest,
        'reviewer': review.reviewer_id, 'reviewer_label': review.reviewer_label, 'reviewed_at': review.reviewed_at})


def resolve_reviews(application, identifiers, *, at):
    from documents.models import DocumentVerification
    if not isinstance(identifiers, list) or any(type(item) is not int for item in identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValidationError('Supporting reviews must be distinct review identifiers.')
    result = []
    for identifier in identifiers:
        review = DocumentVerification.objects.select_related('document').filter(pk=identifier,
            document__application_id=application.member.application_id).first()
        if not review or review.document.verifications.first().pk != review.pk:
            raise ValidationError('Supporting review is unrelated or no longer current.')
        if (not review.verified or review.member_version != application.member.version or
                review.expires_on and review.expires_on < at or file_digest(review.document) != review.file_digest):
            raise ValidationError('Supporting evidence is rejected, expired, outdated or unavailable.')
        result.append(review_manifest(review))
    return result


def reviewed_value(application, criterion, source_type, value, rule):
    if source_type not in SOURCE_TYPES.get(criterion, ()) or source_type not in rule['source_types']:
        raise ValidationError('Source type is not defined for this criterion policy.')
    if source_type == 'government_status':
        raise ValidationError('Government-program status verification has no approved source contract.')
    member = application.member
    if member.employment_status and source_type in ('employment_text', 'employment_category'):
        raise ValidationError('Verify the recorded employment status under an explicit employment_status policy; no mapping to legacy categories is assumed.')
    original = {'monthly_income': str(member.monthly_income) if member.monthly_income is not None else None,
                'employment_text': member.employment_information, 'employment_category': member.employment_information,
                'dependent_count': member.dependents, 'income_category': member.income_category,
                'employment_status': member.employment_status,
                'household_monthly_income': str(member.household_monthly_income) if getattr(member, 'household_monthly_income', None) is not None else None,
                'household_member_count': getattr(member, 'household_members', None),
                'four_ps_membership': getattr(member, 'registration_profile', {}).get('four_ps_member')}.get(source_type)
    if source_type in ('income_category', 'employment_status', 'four_ps_membership'):
        if value is not None and str(value) != str(original):
            raise ValidationError('Review the exact recorded membership category; correct the member record before changing it.')
        if not original:
            return None, 'missing', original
        if original not in rule.get('categories', {}):
            raise ValidationError('This membership category has no documented mapping. Verification and an authorized policy definition are required.')
        return original, 'category', original
    if source_type in ('monthly_income', 'employment_text', 'dependent_count', 'household_monthly_income', 'household_member_count'):
        # Browser values must never silently replace the recorded source value.
        if value is not None and str(value) != str(original):
            raise ValidationError('The reviewed value differs from the source. Correct it through the authorized source workflow.')
        value = original
    if value is None or value == '':
        return None, 'missing', original
    if source_type in ('dependent_count', 'successful_releases', 'household_member_count'):
        if isinstance(value, bool) or not str(value).isdigit():
            raise ValidationError('A nonnegative whole number is required; missing is not zero.')
        value = int(value)
        if value > 2147483647:
            raise ValidationError('The reviewed count exceeds the supported storage range.')
        return value, 'integer', original
    if source_type in ('monthly_income', 'socioeconomic_assessment', 'household_monthly_income'):
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            raise ValidationError('A finite nonnegative decimal is required.') from None
        if not number.is_finite() or number < 0 or number > Decimal('999999999999.9999') or number.as_tuple().exponent < -4:
            raise ValidationError('Use a finite nonnegative decimal with at most four decimal places.')
        return str(number), 'decimal', original
    if source_type in ('employment_category', 'program_relevance'):
        if not isinstance(value, str) or value not in rule.get('categories', {}):
            raise ValidationError('Select an outcome from the documented category definitions.')
        return value, 'category', original
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValidationError('Preserve employment text of up to 200 characters.')
    return value, 'text', original
