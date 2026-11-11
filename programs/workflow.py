from django.core.exceptions import ValidationError
from django.db import transaction
from ewaf.photo_invalidation import photo_writer, correction_files
from django.utils import timezone
from announcements.services import remove_file
from core.permissions import require_workspace_permissions
from events.services import check_version
from members.models import Member
from .models import (Program, ProgramApplication, ProgramCodeCounter, ReferenceCounter, ApplicationPhoto,
                     PhotoVerification, ProgramDocument, ProgramDocumentRevision)

PHOTO_VIEW = ('programs.view_program', 'programs.view_programapplication', 'programs.view_applicationphoto')
CONFIGURED_EVIDENCE = 'configured_program_requirements_v1'


def calendar_photo_required(application):
    # Existing applications retain their issued evidence contract. The new
    # marker is written only by submission, never taken from public form data.
    source = application.source_snapshot
    return (bool(application.current_photo_id) or not isinstance(source, dict)
            or source.get('evidence_policy') != CONFIGURED_EVIDENCE)


def allocate_reference(program):
    """Caller holds the Program row lock; all counters commit with submission."""
    if not program.public_code:
        ProgramCodeCounter.objects.get_or_create(pk=1)
        counter = ProgramCodeCounter.objects.select_for_update().get(pk=1)
        if counter.value >= 999999:
            raise ValidationError('Program reference capacity reached. Contact system administration.')
        counter.value += 1
        counter.save(update_fields=['value'])
        program.public_code = f'PRG{counter.value:06d}'
        program.save(update_fields=['public_code'])
    year = timezone.localdate().year
    counter, _ = ReferenceCounter.objects.get_or_create(program=program, year=year)
    if counter.value >= 9999999999:
        raise ValidationError('Application reference capacity reached. Contact system administration.')
    counter.value += 1
    counter.save(update_fields=['value'])
    return f'SPWDA-{year}-{program.public_code}-{counter.value:010d}'


def store_photo(application, photo, saved_files, *, user=None, reason='Initial application photo'):
    evidence = ApplicationPhoto(application=application, member_version=application.member.version, uploaded_by=user, reason=reason)
    evidence.file.save('calendar.png', photo, save=False)
    saved_files.append((evidence.file.storage, evidence.file.name))
    evidence.save()
    application.current_photo = evidence
    application.status = ProgramApplication.Status.PENDING_PHOTO_VERIFICATION
    application.save(update_fields=['current_photo', 'status', 'updated_at'])
    PhotoVerification.objects.create(photo=evidence, outcome='PENDING', reason=reason,
        reviewer=user, reviewer_label=user.get_username() if user else 'Application submission', member_version=application.member.version)
    return evidence


def require_verified_photo(application, member=None):
    if not calendar_photo_required(application):
        return None  # Not required is distinct from a verified photograph.
    member = member or application.member
    photo = application.current_photo
    review = photo.reviews.first() if photo else None
    if not (photo and photo.application_id == application.pk and review and review.outcome == 'VERIFIED'
            and review.member_version == member.version and photo.file.storage.exists(photo.file.name)):
        raise ValidationError('Current manual Photo Verification is required before further processing.')
    return review


def locked_application(reference):
    program_id = ProgramApplication.objects.values_list('program_id', flat=True).get(pk=reference)
    program = Program.objects.select_for_update().get(pk=program_id)
    application = ProgramApplication.objects.select_for_update().get(pk=reference)
    member = Member.objects.select_for_update().get(pk=application.member_id)
    if application.current_photo_id:
        application.current_photo = ApplicationPhoto.objects.select_for_update().get(
            pk=application.current_photo_id, application=application)
    application.program, application.member = program, member
    return application


def invalidate_case(application, user, reason, address=None):
    from assistance.models import AssistanceCase, EligibilityStatus
    from assistance.services import case_snapshot, record_log
    case = AssistanceCase.objects.filter(application=application).first()
    if case:
        before = case_snapshot(case)
        case.eligibility = EligibilityStatus.objects.get(pk='review')
        case.eligibility_label = 'Needs Information'
        case.decision = 'pending'
        case.decision_notes = 'Evidence changed; current eligibility review is required.'
        case.decided_at = None
        case.decided_by = None
        case.save()
        record_log(application, user, 'evidence_invalidated', reason,
                   {'before': before, 'after': case_snapshot(case)}, address)


@photo_writer()
@transaction.atomic
def review_photo(reference, *, user, data, address=None, completed_reassessment=False):
    from .forms import PhotoReviewForm
    from .services import record_log
    require_workspace_permissions(user, *PHOTO_VIEW, 'programs.review_applicationphoto')
    form = PhotoReviewForm(data)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    values = form.cleaned_data
    application = locked_application(reference)
    check_version(application, values['version'])
    if completed_reassessment:
        from assistance.reassessment import completed_receipt
        from .review_services import DIRECT_REVIEW_PERMISSIONS
        require_workspace_permissions(user, *DIRECT_REVIEW_PERMISSIONS)
        completed_receipt(application)
        if values['outcome'] != 'VERIFIED':
            raise ValidationError('Use the eligibility decision to record the completed-recipient review.')
    elif application.status not in ('PENDING_PHOTO_VERIFICATION', 'NEEDS_INFORMATION', 'PHOTO_VERIFIED', 'ELIGIBILITY_REVIEW'):
        raise ValidationError('This application is not awaiting photo review. Use the authorized correction workflow when appropriate.')
    if not application.current_photo_id or application.current_photo_id != values['photo_id']:
        raise ValidationError('The current photo changed. Reload before reviewing.')
    if not application.current_photo.file.storage.exists(application.current_photo.file.name):
        raise ValidationError('The private photo is unavailable. Request resubmission through the Help Desk.')
    if not application.member.is_active or application.member.archived_at:
        raise ValidationError('Membership must be active before verification.')
    if not application.program.policy_authorized_at:
        raise ValidationError('Authorize the program photo instructions before reviewing.')
    before = application.status
    review = PhotoVerification.objects.create(photo=application.current_photo, outcome=values['outcome'],
        reason=values['reason'], category=values['category'], reviewer=user,
        reviewer_label=user.get_username(), member_version=application.member.version)
    application.status = {'VERIFIED': 'PHOTO_VERIFIED', 'NEEDS_RESUBMISSION': 'NEEDS_INFORMATION', 'REJECTED': 'VERIFICATION_FAILED'}[review.outcome]
    if completed_reassessment:
        application.status = 'COMPLETED'
    application.version += 1
    application.save(update_fields=['status', 'version', 'updated_at'])
    invalidate_case(application, user, values['reason'], address)
    record_log(application.program, 'photo_verified', values['reason'], user=user, application=application, address=address,
        changes={'status': {'before': before, 'after': application.status},
                 'photo_review': {'before': None, 'after': {'photo': str(review.photo_id), 'review': review.pk, 'outcome': review.outcome, 'category': review.category}}})
    return review


def retain_document_revision(document, user, reason):
    ProgramDocumentRevision.objects.create(document=document, file=document.file.name,
        content_type=document.content_type, size=document.size, source_document=document.source_document,
        source_verification=document.source_verification, actor=user, actor_label=user.get_username(), reason=reason)


@photo_writer(correction=True)
def correct_application(reference, *, user, data, files, address=None):
    from .forms import CorrectionForm
    from .services import record_log
    require_workspace_permissions(user, *PHOTO_VIEW, 'programs.resubmit_applicationphoto', 'programs.view_programdocument')
    saved_files = correction_files()
    try:
        with transaction.atomic():
            application = locked_application(reference)
            if application.status not in ('NEEDS_INFORMATION', 'PENDING_PHOTO_VERIFICATION', 'PHOTO_VERIFIED', 'ELIGIBILITY_REVIEW'):
                raise ValidationError('Only applications awaiting verification/information can be corrected. Retained final decisions are not overwritten.')
            if not application.member.is_active or application.member.archived_at or application.program.status != 'published':
                raise ValidationError('An active Member and published program are required for correction.')
            deadline = application.program.resubmission_closes_at
            if deadline and timezone.now() > deadline:
                raise ValidationError('The approved correction period has closed. Contact the Association Help Desk for review.')
            form = CorrectionForm(data, files, application=application)
            if not form.is_valid():
                raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
            values = form.cleaned_data
            check_version(application, values['version'])
            latest = application.current_photo.reviews.first() if application.current_photo_id else None
            if latest and latest.outcome == 'NEEDS_RESUBMISSION' and not values.get('calendar_photo'):
                raise ValidationError('Submit a replacement calendar photo for the requested resubmission.')
            before = {'answers': application.answers.copy(), 'status': application.status, 'source_snapshot': application.source_snapshot.copy()}
            for item in form.snapshot:
                key = f'requirement_{item["id"]}'
                if item['kind'] != 'document':
                    application.answers[str(item['id'])] = values.get(key, '')
                    continue
                upload = values.get(key)
                current = application.documents.filter(requirement_id=item['id']).first()
                reused = form.reused.get(item['id'])
                if not upload and current and (not current.source_document_id or not reused or current.source_verification_id == reused[1].pk):
                    continue
                if not upload and not reused:
                    continue
                if current:
                    retain_document_revision(current, user, values['reason'])
                else:
                    current = ProgramDocument(application=application, requirement_id=item['id'], label=item['label'])
                if upload:
                    current.file.save(upload.name, upload, save=False)
                    saved_files.append((current.file.storage, current.file.name))
                    current.content_type, current.size = upload.content_type, upload.size
                    current.source_document = current.source_verification = None
                else:
                    document, verification = reused
                    current.file.name = document.file.name
                    current.content_type, current.size = document.content_type, document.size
                    current.source_document, current.source_verification = document, verification
                current.save()
            if values.get('calendar_photo'):
                store_photo(application, values['calendar_photo'], saved_files, user=user, reason=values['reason'])
            else:
                try:
                    require_verified_photo(application)
                    application.status = 'ELIGIBILITY_REVIEW'
                except ValidationError:
                    application.status = 'PENDING_PHOTO_VERIFICATION'
            application.version += 1
            application.source_snapshot = {**application.source_snapshot, 'correction_member_version': application.member.version,
                'corrected_at': timezone.now().isoformat(), 'corrected_by': user.pk}
            application.save(update_fields=['answers', 'status', 'source_snapshot', 'version', 'updated_at'])
            invalidate_case(application, user, values['reason'], address)
            record_log(application.program, 'application_corrected', values['reason'], user=user, application=application, address=address,
                changes={key: {'before': value, 'after': getattr(application, key)} for key,value in before.items()})
            return application
    except Exception:
        for storage, name in saved_files:
            remove_file(storage, name)
        raise
