from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.permissions import require_workspace_permissions
from ewaf.assistance_invalidation import assistance_writer
from events.services import check_version, check_notes
from members.models import Member
from programs.models import Program, ProgramApplication
from .forms import EligibilityForm, DecisionForm, ReceiptForm, ReleaseForm, VoidForm, StatusForm
from .models import AssistanceCase, AssistanceRelease, AssistanceLog, EligibilityStatus
from .claimant import ClaimantForm


VIEW_PERMISSIONS = ('programs.view_program', 'programs.view_programapplication', 'assistance.view_assistancecase')
AUTO_SELECTION_POLICY = 'non_ewaf_all_eligible_v1'
AUTO_SELECTION_REASON = 'Automatically selected after Admin confirmed eligibility. Non-EWAF programs have no beneficiary limit.'


def record_log(application, user, action, notes, snapshot, address=None):
    return AssistanceLog.objects.create(application=application, actor=user, actor_label=user.get_username(),
        action=action, notes=notes.strip(), snapshot=snapshot, address=address or None)


def previous_assistance_count(member):
    return AssistanceRelease.objects.successful().filter(application__member=member).count()


def reserved_slots(program):
    reserved = set(AssistanceCase.objects.filter(application__program=program, decision='approved').values_list('application_id', flat=True))
    if program.ewaf_applicable:
        from ewaf.operational_services import available, latest_decisions
        if available():
            reserved.update(latest_decisions(program).filter(outcome='SELECTED').values_list('application_id', flat=True))
    return len(reserved)


def validate_form(form):
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    return form.cleaned_data


def locked_application(reference, user, permission):
    require_workspace_permissions(user, *VIEW_PERMISSIONS, permission)
    program_id = ProgramApplication.objects.values_list('program_id', flat=True).get(pk=reference)
    program = Program.objects.select_for_update().get(pk=program_id)
    application = ProgramApplication.objects.select_for_update().get(pk=reference)
    if permission == 'assistance.decide_assistance':
        list(Member.objects.select_for_update().filter(program_applications__program=program).order_by('pk'))
    member = Member.objects.select_for_update().get(pk=application.member_id)
    return application, program, member


def require_available(application, program, member):
    from programs.workflow import require_verified_photo
    require_verified_photo(application, member)
    from programs.services import require_disability
    require_disability(program, member)
    if application.status in ('CLOSED', 'VERIFICATION_FAILED', 'INELIGIBLE'):
        raise ValidationError('Restore the cancelled application before continuing.')
    if not member.is_active or member.archived_at:
        raise ValidationError('Active membership is required.')
    if program.status != 'published' or not program.published_at or program.published_at > timezone.now():
        raise ValidationError('A currently published program is required.')
    if not program.policy_authorized_at or not program.selection_method.strip():
        raise ValidationError('An approved program selection method is required.')


def require_unreleased(application):
    if application.assistance_releases.successful().exists():
        raise ValidationError('Assistance has been released. Void an incorrect release before changing this assessment or decision.')


def bump(application):
    application.version += 1
    application.save(update_fields=['status', 'version', 'updated_at'])


def case_snapshot(case):
    return {'eligibility': case.eligibility_id, 'eligibility_label': case.eligibility_label,
            'checklist': case.checklist, 'review_notes': case.review_notes,
            'reviewed_at': case.reviewed_at.isoformat(), 'reviewed_by': case.reviewed_by_id,
            'member_version': case.member_version, 'program_version': case.program_version,
            'decision': case.decision, 'decision_notes': case.decision_notes,
            'decided_at': case.decided_at.isoformat() if case.decided_at else None, 'decided_by': case.decided_by_id}


@assistance_writer('eligibility')
@transaction.atomic
def review_eligibility(reference, *, user, data, address=None, direct_review=False):
    application, program, member = locked_application(reference, user, 'assistance.review_eligibility')
    if not program.ewaf_applicable:
        raise ValidationError('This program must be updated to EWAF before eligibility review.')
    application.program, application.member = program, member
    completed_witness = None
    if direct_review and application.status == 'COMPLETED':
        from .reassessment import completed_receipt
        _, completed_witness = completed_receipt(application)
    else:
        require_unreleased(application)
    from programs.workflow import require_verified_photo
    if direct_review:
        from programs.review_services import DIRECT_REVIEW_PERMISSIONS
        require_workspace_permissions(user, *DIRECT_REVIEW_PERMISSIONS)
        if data.get('eligibility') not in ('eligible', 'review', 'ineligible'):
            raise ValidationError('Choose Eligible, Needs Information or Ineligible.')
    if not direct_review or data.get('eligibility') == 'eligible':
        require_verified_photo(application, member)
    allowed = ('PHOTO_VERIFIED', 'ELIGIBILITY_REVIEW', 'NEEDS_INFORMATION', 'ELIGIBLE')
    if direct_review:
        allowed += ('PENDING_PHOTO_VERIFICATION',)
    if completed_witness:
        allowed += ('COMPLETED',)
    if application.status not in allowed:
        raise ValidationError('This application must complete the required verification/review stage first.')
    values = validate_form(EligibilityForm(data, application=application))
    check_version(application, values['version'])
    if values['member_version'] != member.version or values['program_version'] != program.version:
        raise ValidationError('Member or program details changed while this form was open. Reload before assessing eligibility.')
    check_notes(values['notes'])
    status = EligibilityStatus.objects.select_for_update().get(pk=values['eligibility'].pk)
    if status.pk == 'eligible' and not direct_review:
        from programs.information_confirmation import require_resolved
        require_resolved(application)
    if not status.is_active:
        raise ValidationError('This eligibility status is no longer available. Reload the page.')
    active = member.is_active and not member.archived_at
    checklist = [{'key': 'membership', 'label': 'Active membership', 'required': True, 'result': 'pass' if active else 'fail'}]
    from programs.services import disability_matches
    if program.eligible_disability_types.exists():
        checklist.append({'key': 'disability', 'label': 'Approved program-specific qualification', 'required': True,
                          'result': 'pass' if disability_matches(program, member) else ('review' if not member.disability_ids else 'fail')})
    from documents.services import program_document_current
    documents = {document.requirement_id for document in application.documents.select_related('source_document')
                 if program_document_current(document, member)}
    for item in application.requirements_snapshot:
        present = (item['id'] in documents if item['kind'] == 'document' else bool(application.answers.get(str(item['id']))))
        result = values[f'check_{item["id"]}'] or 'review'
        if result == 'pass' and not present:
            raise ValidationError(f'{item["label"]}: no submission exists to validate. Select review or failed.')
        checklist.append({'key': str(item['id']), 'label': item['label'], 'kind': item['kind'],
                          'required': item['is_required'], 'present': present, 'result': result})
    checklist.append({'key': 'other_requirements', 'label': 'Program instructions and other requirements',
                      'required': True, 'result': values['other_requirements']})
    if direct_review:
        checklist.append({'key': 'admin_review', 'label': 'Administrator review of the submitted application',
                          'required': True, 'result': {'eligible': 'pass', 'review': 'review', 'ineligible': 'fail'}[status.pk]})
        from programs.information_confirmation import confirmation_context
        information = confirmation_context(application)
        if information.get('report') in ('changed', 'uncertain') and not information['resolved']:
            checklist.append({'key': 'information_change',
                'label': 'Reported information change awaiting confirmation at the barangay office',
                'required': False, 'result': 'review'})
    if status.pk == 'eligible' and any(item['required'] and item['result'] != 'pass' for item in checklist):
        raise ValidationError('Eligible requires active membership and every required checklist item to pass.')
    if status.pk == 'ineligible' and not any(item['required'] and item['result'] == 'fail' for item in checklist):
        raise ValidationError('Use Needs Information for correctable missing evidence. Ineligible requires a confirmed mandatory qualification failure and a reason.')
    case = AssistanceCase.objects.filter(application=application).first()
    before = case_snapshot(case) if case else None
    if case is None:
        case = AssistanceCase(application=application)
    case.eligibility = status
    case.eligibility_label = str(status)
    case.checklist = checklist
    case.review_notes = values['notes'].strip()
    case.reviewed_at = timezone.now()
    case.reviewed_by = user
    case.member_version = member.version
    case.program_version = program.version
    case.decision = 'pending'
    case.decision_notes = ''
    case.decided_at = None
    case.decided_by = None
    case.full_clean()
    case.save()
    application.status = {
        'eligible': 'ELIGIBLE', 'ineligible': 'INELIGIBLE', 'review': 'NEEDS_INFORMATION', 'pending': 'ELIGIBILITY_REVIEW'}[status.pk]
    if completed_witness:
        application.status = 'COMPLETED'
    bump(application)
    snapshot = {'before': before, 'after': case_snapshot(case)}
    if completed_witness:
        from .reassessment import review_witness
        snapshot['completed_reassessment'] = review_witness(application, completed_witness)
    record_log(application, user, 'eligibility_reviewed', case.review_notes, snapshot, address)
    from announcements.program_publication import refresh_existing_results
    refresh_existing_results(program, user=user, address=address)
    return case


def require_current_review(case, program, member, *, allow_schedule_revision=False):
    from programs.information_confirmation import require_resolved
    application = case.application
    application.member, application.program = member, program
    require_resolved(application)
    from documents.services import program_document_current
    for document in case.application.documents.select_related('source_document'):
        required = any(item['id'] == document.requirement_id and item['is_required'] for item in case.application.requirements_snapshot)
        if required and not program_document_current(document, member):
            raise ValidationError('Required evidence needs renewed verification. Return the application for review.')
    schedule = {}
    if allow_schedule_revision and case.program_version != program.version:
        from programs.schedule_services import eligibility_schedule_witness
        schedule = eligibility_schedule_witness(application, case)
    if case.member_version != member.version or (case.program_version != program.version and not schedule):
        raise ValidationError('Member or program details changed after assessment. Review eligibility again.')
    status = EligibilityStatus.objects.select_for_update().get(pk=case.eligibility_id)
    if status.pk != 'eligible' or not status.is_active:
        raise ValidationError('An active Eligible assessment is required before approval or release.')
    if any(item['required'] and item['result'] != 'pass' for item in case.checklist):
        raise ValidationError('Required eligibility checks must pass.')
    return schedule


@assistance_writer('decision')
@transaction.atomic
def decide_assistance(reference, *, user, data, address=None):
    application, program, member = locked_application(reference, user, 'assistance.decide_assistance')
    values = validate_form(DecisionForm(data))
    check_version(application, values['version'])
    check_notes(values['notes'])
    require_unreleased(application)
    case = AssistanceCase.objects.filter(application=application).first()
    if not case:
        raise ValidationError('Record an eligibility assessment first.')
    decision = values['decision']
    if decision == case.decision and decision != 'pending':
        raise ValidationError('This decision is already recorded.')
    ranking = None
    if decision in ('approved', 'rejected'):
        require_available(application, program, member)
        require_current_review(case, program, member)
        if application.status not in ('ELIGIBLE', 'RANKED', 'SELECTED', 'NOT_SELECTED'):
            raise ValidationError('A current eligible application is required for final selection.')
        from ewaf.services import require_ranked
        ranking = require_ranked(application, program)
        if program.registration_closes_at > timezone.now():
            raise ValidationError('Final selection begins after the application period closes.')
    if decision == 'approved':
        if program.slot_limit is not None and reserved_slots(program) >= program.slot_limit:
            raise ValidationError('All beneficiary slots are reserved. Return an existing approval for review or adjust the program slots first.')
    before = case_snapshot(case)
    case.decision = decision
    case.decision_notes = values['notes'].strip()
    case.decided_at = timezone.now()
    case.decided_by = user
    # Returning for review requires a new assessment before a later approval.
    if decision == 'pending':
        case.eligibility = EligibilityStatus.objects.get(pk='review')
        case.eligibility_label = case.eligibility.label
    case.save()
    application.status = {'approved': 'SELECTED', 'rejected': 'NOT_SELECTED', 'pending': 'ELIGIBILITY_REVIEW'}[decision]
    bump(application)
    record_log(application, user, 'decision_recorded', case.decision_notes, {'before': before, 'after': case_snapshot(case), 'ranking_run': ranking.pk if ranking else None,
        'selection_method': program.selection_method, 'policy_authorized_at': program.policy_authorized_at.isoformat() if program.policy_authorized_at else None}, address)
    from announcements.program_publication import refresh_existing_results
    refresh_existing_results(program, user=user, address=address)
    return case


@transaction.atomic
def record_actual_receipt(reference, *, user, data, address=None, source_expected=None):
    """Confirm receipt of the selected program's assistance with current defaults."""
    require_workspace_permissions(user, *VIEW_PERMISSIONS, 'assistance.view_assistancerelease',
                                  'assistance.record_release')
    form = ReceiptForm(data)
    values = validate_form(form)
    application = ProgramApplication.objects.select_related('program').get(pk=reference)
    program = application.program
    check_version(program, values['program_version'])
    payload = {
        **{name: values[name] for name in ClaimantForm.base_fields},
        'version': values['version'], 'confirm': True,
        'assistance_type': program.assistance_type,
        'benefit': program.benefit.strip() or f'Assistance for {program.name}',
        'amount': program.amount if program.amount is not None else '',
        'estimated_value': '', 'reference': '', 'released_on': timezone.localdate(),
        'notes': f'Actual receipt confirmed for {program.name}. Applicant selected for this program.',
    }
    # The ordinary release writer owns all selection, receipt, audit and source
    # locks. Recheck the program version under its lock before using these values.
    release = record_release(reference, user=user, data=payload, address=address,
        receipt_program_version=program.version, source_expected=source_expected)
    from .receipt_email import queue_receipt_email
    queue_receipt_email(release, user=user)
    return release


@assistance_writer('release')
@transaction.atomic
def record_release(reference, *, user, data, address=None, receipt_program_version=None):
    application, program, member = locked_application(reference, user, 'assistance.record_release')
    require_workspace_permissions(user, 'assistance.view_assistancerelease')
    if receipt_program_version is not None:
        check_version(program, receipt_program_version)
    form = ReleaseForm(data)
    values = validate_form(form)
    check_version(application, values['version'])
    check_notes(values['notes'])
    require_available(application, program, member)
    require_unreleased(application)
    case = AssistanceCase.objects.filter(application=application).first()
    operational = None
    if program.ewaf_applicable:
        from ewaf.operational_services import delivery_selection
        operational = delivery_selection(application, program, user)
    if not case or (not operational and case.decision != 'approved'):
        raise ValidationError('An authorized administrator must approve assistance before release.')
    if application.status != ('ELIGIBLE' if operational else 'SELECTED'):
        raise ValidationError('Current Selected status is required before recording actual receipt.')
    schedule = require_current_review(case, program, member, allow_schedule_revision=bool(operational))
    from announcements.release_publication import require_published_selection
    publication = require_published_selection(application, program)
    approved_at = operational.recorded_at if operational else case.decided_at
    if values['released_on'] < timezone.localtime(approved_at).date():
        raise ValidationError('The release date cannot precede its approval.')
    release = form.save(commit=False)
    release.application = application
    release.active_application = application
    release.recorded_by = user
    release.approval_snapshot = {**case_snapshot(case), 'program_name': program.name, 'assistance_type': program.assistance_type,
                                 'approved_by_label': case.decided_by.get_username() if case.decided_by else ''}
    release.approval_snapshot['result_publication'] = publication
    if receipt_program_version is not None or 'claimant_type' in data:
        claimant = ClaimantForm(data)
        validate_form(claimant)
        release.approval_snapshot['claimant'] = claimant.claimant_snapshot(member=member, user=user)
    if receipt_program_version is not None:
        release.approval_snapshot.update(recording_method='program_receipt_button',
                                         receipt_program_version=receipt_program_version)
    if schedule:
        release.approval_snapshot['eligibility_schedule_revision'] = schedule
    if operational:
        release.approval_snapshot.update(
            decision='approved', decision_notes=operational.reason, decided_at=operational.recorded_at.isoformat(),
            decided_by=operational.actor_id, approved_by_label=operational.actor_label,
            operational_run_id=operational.run_id, operational_run_digest=operational.run.digest,
            operational_decision_id=operational.pk, operational_decision_digest=operational.digest)
    release.full_clean()
    release.save()
    application.status = 'COMPLETED'
    bump(application)
    record_log(application, user, 'assistance_released', release.notes, {'release': str(release.pk),
        'assistance_type': release.assistance_type, 'benefit': release.benefit, 'amount': str(release.amount) if release.amount is not None else None,
        'estimated_value': str(release.estimated_value) if release.estimated_value is not None else None,
        'released_on': str(release.released_on), 'reference': release.reference, 'approval': release.approval_snapshot}, address)
    return release


@assistance_writer('void')
@transaction.atomic
def void_release(reference, release_id, *, user, data, address=None):
    application, program, member = locked_application(reference, user, 'assistance.void_release')
    require_workspace_permissions(user, 'assistance.view_assistancerelease')
    values = validate_form(VoidForm(data))
    check_version(application, values['version'])
    check_notes(values['notes'])
    release = AssistanceRelease.objects.select_for_update().get(pk=release_id, application=application)
    if release.voided_at:
        raise ValidationError('This release has already been voided.')
    release.voided_at = timezone.now()
    release.voided_by = user
    release.void_reason = values['notes'].strip()
    release.active_application = None
    release.save(update_fields=['voided_at', 'voided_by', 'void_reason', 'active_application'])
    case = AssistanceCase.objects.get(application=application)
    case.decision = 'pending'
    case.decision_notes = 'Release voided; renewed assessment and approval required.'
    case.decided_at = timezone.now()
    case.decided_by = user
    case.eligibility = EligibilityStatus.objects.get(pk='review')
    case.eligibility_label = case.eligibility.label
    case.save()
    application.status = 'NEEDS_INFORMATION'
    bump(application)
    record_log(application, user, 'release_voided', release.void_reason, {'release': str(release.pk), 'after': case_snapshot(case)}, address)
    from announcements.program_publication import refresh_existing_results
    refresh_existing_results(program, user=user, address=address)
    return release


@transaction.atomic
def configure_status(code, *, user, data, address=None):
    require_workspace_permissions(user, 'assistance.view_eligibilitystatus', 'assistance.change_eligibilitystatus')
    raise ValidationError('Workflow status meanings are fixed by the current specification. Historical labels are retained for audit only.')
