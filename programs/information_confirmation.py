"""Review of application change reports without accepting replacement score values."""
import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from core.permissions import require_workspace_permissions
from ewaf.source_invalidation import source_writer
from .application_workflow import CONTRACT
from .models import ProgramLog
from .terms import terms_lock, snapshot_terms, terms_digest

VIEW = ('programs.view_program', 'programs.view_programapplication', 'members.view_member')
REVIEW = (*VIEW, 'assistance.review_eligibility', 'documents.view_membershipapplicationdocument',
    'documents.view_documentverification')
UPDATE = (*VIEW, 'members.change_member', 'assistance.view_assistancecase', 'assistance.review_eligibility')
ACTION = 'current_information_reviewed'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def declaration(application):
    source = application.source_snapshot
    return source.get('application_confirmation') if isinstance(source, dict) else None


def member_basis(member):
    return {'version': member.version, 'profile': digest({key: getattr(member, key) for key in (
        'employment_status', 'employment_information', 'household_monthly_income', 'household_members',
        'monthly_income', 'dependents', 'registration_profile')})}


def policy_basis(program):
    result = {'terms': terms_digest(snapshot_terms(program))}
    if program.ewaf_applicable:
        from ewaf.operational_models import OperationalConfiguration
        row = OperationalConfiguration.objects.filter(program=program).first()
        result['configuration'] = row.digest if row else None
    return result


def review_policy_matches(record, program):
    recorded = record.get('policy')
    current = policy_basis(program)
    if recorded == current:
        return True
    # Removing an extra ranking-file requirement changes the configuration
    # digest, but not a previously reviewed correction to member information.
    # All declaration/member/profile checks below still apply independently.
    if (record.get('method') != 'member_update' or not isinstance(recorded, dict)
            or not program.ewaf_applicable or recorded.get('terms') != current.get('terms')):
        return False
    from ewaf.operational_models import OperationalConfiguration
    from ewaf.revised.member_record_evidence import preserves_information_review
    configuration = OperationalConfiguration.objects.filter(program=program).select_related(
        'dataset_policy', 'previous__dataset_policy').first()
    try:
        # A correction may predate both the document-removal revision and the
        # subsequent authorized automatic-member-input revision.
        while configuration and configuration.previous_id:
            previous = configuration.previous
            if not preserves_information_review(previous, configuration):
                return False
            if previous.digest == recorded.get('configuration'):
                return True
            configuration = previous
        return False
    except ValidationError:
        return False


def confirmation_context(application):
    data = declaration(application)
    if data is None:
        return {}  # Preserve historical source contracts and recorded digests.
    valid = isinstance(data, dict) and data.get('contract') == CONTRACT and data.get('confirm_information') is True
    report = data.get('current_information') if valid else 'invalid'
    # New applications use the saved member record and do not ask for a change
    # declaration. Preserve older declarations and their review requirements.
    if (valid and data.get('information_basis') == 'member_record'
            and 'current_information' not in data and 'change_details' not in data):
        report = 'not_requested'
    result = {'declaration': digest(data), 'report': report, 'resolved': report == 'unchanged', 'review': None}
    if report == 'not_requested':
        result['resolved'] = True
        return result
    if report == 'unchanged':
        return result
    review = ProgramLog.objects.filter(application=application, action=ACTION).order_by('-occurred_at', '-pk').first()
    if review:
        result['review'] = {'id': review.pk, 'digest': digest(review.changes)}
        record = review.changes
        if not isinstance(record, dict):
            return result
        matches = (record.get('declaration') == result['declaration']
            and record.get('member') == member_basis(application.member)
            and review_policy_matches(record, application.program))
        if matches and record.get('method') == 'member_update':
            from members.profile import profile_snapshot
            matches = record.get('profile') == digest(profile_snapshot(application.member))
        elif matches:
            from ewaf.evidence import resolve_reviews
            try:
                current = resolve_reviews(application, [row['id'] for row in record['evidence']], at=timezone.localdate())
                matches = bool(current) and current == record['evidence']
            except (ValidationError, KeyError, TypeError):
                matches = False
        result['resolved'] = bool(valid and matches)
    return result


def require_resolved(application):
    context = confirmation_context(application)
    if context and not context['resolved']:
        raise ValidationError('Review and save the reported changes in member information before continuing.')


def review_token(application):
    return digest({'application': str(application.pk), 'version': application.version,
        'member': member_basis(application.member), 'policy': policy_basis(application.program),
        'confirmation': confirmation_context(application)})


@terms_lock()
def update_reported_information(reference, *, user, data, address=None):
    """Save the administrator's edits and report review together, without scoring."""
    from django.contrib.auth import get_user_model
    from assistance.services import locked_application, require_unreleased
    from members.profile import profile_snapshot
    from members.services import update_member
    from .information_forms import information_update_form
    from .review_services import DIRECT_REVIEW_STATUSES
    from .workflow import invalidate_case
    from .services import record_log

    user = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    if user is None:
        raise PermissionDenied
    require_workspace_permissions(user, *UPDATE)
    application, program, member = locked_application(reference, user, 'assistance.review_eligibility')
    application.program, application.member = program, member
    require_unreleased(application)
    if application.status not in DIRECT_REVIEW_STATUSES:
        raise ValidationError('Use the authorized return-for-review procedure before updating information for this application.')
    if member.archived_at or not member.is_active:
        raise ValidationError('Restore active membership before updating information for this application.')
    report = declaration(application)
    if (not isinstance(report, dict) or report.get('contract') != CONTRACT
            or report.get('current_information') not in ('changed', 'uncertain')
            or report.get('confirm_information') is not True):
        raise ValidationError('There is no supported change report to review.')
    form = information_update_form(data, application=application)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    values = form.cleaned_data
    if values['expected'] != form.initial['expected'] or values['version'] != member.version:
        raise ValidationError('The application or member information changed. Reload before saving.')
    notes = values['notes'].strip() or f'Reviewed reported changes and current member information for {application.public_reference}.'
    changed = set(form.changed_data) - {'expected', 'notes', 'version', 'member_profile_format'}
    member_event = None
    if changed:
        submitted = data.copy()
        submitted.pop('expected', None)
        member = update_member(member.pk, user=user, version=member.version,
            data=submitted, notes=notes, address=address)
        member_event = member.events.filter(action='profile_updated').first().pk
        application.member = member
    # A member edit requires renewed application eligibility/photo review, while
    # the original submission, issued reference and earlier decisions stay intact.
    invalidate_case(application, user, notes, address)
    if application.status == 'ELIGIBLE':
        application.status = 'ELIGIBILITY_REVIEW'
    application.version += 1
    application.save(update_fields=['status', 'version', 'updated_at'])
    record_log(program, ACTION, notes, user=user, application=application, address=address,
        changes={'method': 'member_update', 'declaration': digest(report),
                 'member': member_basis(member), 'profile': digest(profile_snapshot(member)),
                 'policy': policy_basis(program), 'member_event': member_event})
    return application


@source_writer('reference', action=ACTION, application_scope=True)
@terms_lock()
def resolve(reference, *, user, expected, evidence_ids, reason, confirmed):
    from ewaf.evidence_services import locked_application
    from ewaf.evidence import resolve_reviews
    from assistance.services import require_unreleased
    from .services import record_log
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    if user is None:
        raise PermissionDenied
    require_workspace_permissions(user, *REVIEW)
    application = locked_application(reference)
    require_unreleased(application)
    if application.status not in ('PENDING_PHOTO_VERIFICATION', 'PHOTO_VERIFIED', 'NEEDS_INFORMATION',
            'ELIGIBILITY_REVIEW', 'ELIGIBLE'):
        raise ValidationError('Use the authorized return-for-review procedure before reviewing information for this application.')
    data = declaration(application)
    if not isinstance(data, dict) or data.get('contract') != CONTRACT or data.get('current_information') not in ('changed', 'uncertain'):
        raise ValidationError('There is no supported change report to resolve.')
    if expected != review_token(application):
        raise ValidationError('The application, member information, evidence or policy changed. Reload before reviewing.')
    if confirmed is not True or not isinstance(reason, str) or not reason.strip() or len(reason) > 2000:
        raise ValidationError('Confirm evidence review and explain the accepted findings and applicable reference period/cutoff.')
    if application.program.ewaf_applicable:
        from ewaf.operational_services import latest_configuration
        latest_configuration(application.program)
    evidence = resolve_reviews(application, evidence_ids, at=timezone.localdate())
    if not evidence:
        raise ValidationError('Select current accepted supporting evidence for this member.')
    record = {'declaration': digest(data), 'member': member_basis(application.member),
        'policy': policy_basis(application.program), 'evidence': evidence}
    application.version += 1
    application.save(update_fields=['version', 'updated_at'])
    record_log(application.program, ACTION, reason.strip(), user=user, application=application, changes=record)
    return application
