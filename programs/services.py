from datetime import timedelta

from django.conf import settings
from ewaf.source_invalidation import source_writer
from ewaf.application_invalidation import application_writer, submission_files
from django.core.exceptions import ValidationError
from django.db import OperationalError, transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from accounts.backends import reserve_windows
from announcements.services import remove_file
from core.permissions import require_workspace_permissions
from events.services import normalize_name, normalize_phone, VERIFICATION_FAILED, check_version, check_notes
from members.models import Member
from .forms import ProgramForm, ProgramSetupForm, RequirementForm, ApplicationForm
from .models import Program, ProgramRequirement, ProgramApplication, ProgramDocument, ProgramLog, VerificationWindow
from .terms import terms_lock, is_protected
from .approval_policy import require_binding, grant_authorization, grant_matches
from .publication_guidance import missing_draft_guidance
from .pictures import ProgramPictureForm, picture_uploads, save_picture


def record_log(program, action, notes, *, user=None, application=None, changes=None, address=None):
    return ProgramLog.objects.create(program=program, action=action, notes=notes,
        actor=user, actor_label=user.get_username() if user else '', application=application,
        changes=changes or {}, address=address or None)


def reserve_verification(control_number, address):
    limits = {
        salted_hmac('programs.verify.member', control_number.strip().upper(), algorithm='sha256').hexdigest(): settings.PROGRAM_VERIFICATION_MEMBER_LIMIT,
        salted_hmac('programs.verify.address', address, algorithm='sha256').hexdigest(): settings.PROGRAM_VERIFICATION_ADDRESS_LIMIT,
    }
    try:
        return reserve_windows(limits, settings.PROGRAM_VERIFICATION_WINDOW_SECONDS, VerificationWindow)
    except (OperationalError, VerificationWindow.DoesNotExist):
        return False


def require_open(program):
    try:
        require_binding(program)
    except ValidationError:
        raise ValidationError('Applications are currently unavailable for this program.') from None
    if not program.registration_available:
        raise ValidationError('Applications are currently closed for this program.')
    event = getattr(program, 'organizational_event', None)
    if event and (event.status != 'published' or not event.published_at or event.published_at > timezone.now()):
        raise ValidationError('Applications are currently closed for this event.')


def disability_matches(program, member):
    if not program.eligible_disability_types.exists():
        return program.allows_all_disability_types
    return program.eligible_disability_types.filter(pk__in=member.disability_ids, is_active=True).exists()


def require_disability(program, member):
    from members.update_services import requires_verification
    if requires_verification(member):
        raise ValidationError('Your member record needs verification. Visit the Association Help Desk for review before applying for a program.', code='needs_verification')
    from .application_workflow import screening
    outcome, message = screening(member, program)
    if outcome != 'passed':
        raise ValidationError(message, code='ineligible' if outcome == 'not_met' else 'needs_information')


@terms_lock()
def verify_member(pk, *, version, control_number, full_name, birthdate, contact_number):
    with transaction.atomic():
        program = Program.objects.select_for_update().get(pk=pk)
        check_version(program, version)
        require_open(program)
        code = control_number.strip().upper()
        member = Member.objects.select_for_update().filter(control_number=code).first()
        if not (member and member.control_number.strip().upper() == code and member.is_active and not member.archived_at
                and normalize_name(member.full_name) == normalize_name(full_name) and member.birthdate == birthdate
                and normalize_phone(contact_number) and normalize_phone(member.contact_number) == normalize_phone(contact_number)):
            raise ValidationError('Unable to verify membership. Please visit/contact the Barangay Santolan PWD Association Help Desk.')
        require_disability(program, member)
        grant = {**grant_authorization(program), 'program': str(program.pk), 'version': program.version, 'member': member.pk,
                 'member_version': member.version,
                 'expires': (timezone.now() + timedelta(seconds=settings.PROGRAM_VERIFICATION_GRANT_SECONDS)).timestamp()}
    return grant


def grant_valid(grant, program):
    return (isinstance(grant, dict) and grant.get('program') == str(program.pk)
            and grant_matches(grant, program)
            and grant.get('version') == program.version
            and isinstance(grant.get('expires'), (int, float)) and grant['expires'] > timezone.now().timestamp())


@source_writer("pk", action="program_save", creation=True)
@terms_lock()
@transaction.atomic
def save_program(*, user, data, pk=None, address=None, setup_only=False):
    require_workspace_permissions(user, 'programs.view_program', 'programs.change_program' if pk else 'programs.add_program')
    item = Program.objects.select_for_update().get(pk=pk) if pk else Program(created_by=user)
    if item.status in ('published', 'cancelled'):
        require_workspace_permissions(user, 'programs.publish_program')
    before = {name: str(getattr(item, name)) for name in ProgramForm.Meta.fields if name != 'eligible_disability_types'}
    before_types = list(item.eligible_disability_types.values_list('pk', flat=True)) if pk else []
    expected = item.version
    from .application_workflow import enabled
    protected = is_protected(item) or (enabled() and item.policy_authorized_at)
    form = (ProgramSetupForm if setup_only else ProgramForm)(data, instance=item)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    if form.cleaned_data['version'] != expected:
        raise ValidationError('This program changed. Reload the page before continuing.')
    if pk and protected:
        from .schedule_services import EDITABLE_FIELDS, update_program_schedule
        if set(form.changed_data) & EDITABLE_FIELDS:
            return update_program_schedule(pk, user=user, values=form.cleaned_data, address=address)
        # Form validation has already rejected protected differences. An
        # unchanged review must not invalidate historical eligibility/results.
        return item
    if pk and item.applications.exists():
        frozen = ('requirements', 'eligible_disability_types')
        if item.policy_authorized_at:
            frozen += ('ewaf_applicable', 'selection_method', 'photo_instructions')
        if any(field in form.changed_data for field in frozen):
            raise ValidationError('Evaluation rules are locked after applications are submitted. Preserve this program and use a separately authorized new program/version for changed rules.')
    item = form.save(commit=False)
    if setup_only:
        for name, text in missing_draft_guidance(item).items():
            setattr(item, name, text)
    if pk and item.slot_limit is not None:
        from assistance.services import reserved_slots
        if reserved_slots(item) > item.slot_limit:
            raise ValidationError('Beneficiary slots cannot be lower than existing approvals. Return an approval for review first.')
    item.updated_by = user
    item.version += 1
    item.save()
    form.save_m2m()
    after_types = list(item.eligible_disability_types.values_list('pk', flat=True))
    if before_types != after_types:
        record_log(item, 'disability_types_configured', 'Program eligible disability types configured.', user=user,
                   address=address, changes={'eligible_disability_types': {'before': before_types, 'after': after_types}})
    record_log(item, 'updated' if pk else 'created', form.cleaned_data.get('notes') or 'Program saved as a private draft.',
        user=user, address=address, changes={name: {'before': value, 'after': str(getattr(item, name))}
                                           for name, value in before.items() if value != str(getattr(item, name))})
    if not pk:
        from ewaf.vault_services import inherit
        inherit(item, user=user)
    return item


@picture_uploads
@terms_lock()
@transaction.atomic
def save_program_with_requirements(*, user, data, requirements, pk=None, address=None, setup_only=False, files=None):
    """Save the program and added requirements together or roll everything back."""
    if requirements:
        require_workspace_permissions(user, 'programs.configure_program')
    program = save_program(user=user, data=data, pk=pk, address=address, setup_only=setup_only)
    picture_form = ProgramPictureForm(data, files)
    if not picture_form.is_valid():
        raise ValidationError([str(error) for errors in picture_form.errors.values() for error in errors])
    position = program.configured_requirements.count()
    for offset, requirement in enumerate(requirements):
        program.refresh_from_db()
        save_requirement(program.pk, user=user, address=address, data={
            **requirement, 'version': program.version, 'is_active': True,
            'position': position + offset, 'notes': data.get('notes') or 'Requirements supplied with the program draft.',
        })
    program.refresh_from_db()
    save_picture(program, form=picture_form, user=user, notes=data.get('notes', ''), address=address)
    return program


@source_writer("pk", action="publication")
@terms_lock()
@transaction.atomic
def change_publication(pk, *, user, version, action, notes='', address=None):
    require_workspace_permissions(user, 'programs.view_program', 'programs.publish_program')
    program = Program.objects.select_for_update().get(pk=pk)
    check_version(program, version)
    if action == 'unpublish' or (action == 'draft' and program.status == 'published'):
        if program.status != 'published':
            raise ValidationError('Only a published program can be unpublished.')
        action = 'draft'
    if action == 'archived' and program.status != 'draft':
        raise ValidationError('Only a draft program can be archived. Unpublish it to draft first.')
    if action == 'published':
        from .mandatory_ewaf import has_required_types
        if not has_required_types(program):
            raise ValidationError('Select at least one applicable disability type before publishing.')
        notes = (notes or '').strip() or 'Published using the program Publish action.'
    check_notes(notes)
    if action == 'authorize_policy':
        from .application_workflow import enabled
        if (program.status not in (('draft', 'published') if enabled() else ('published',))
                or program.policy_authorized_at):
            raise ValidationError('Policy authorization is available only for a published program with no recorded authorization.')
        if not program.photo_instructions.strip() or not program.selection_method.strip():
            raise ValidationError('Edit the program and enter the approved selection method and calendar-photo instructions before authorizing its policy.')
        program.policy_authorized_at = timezone.now()
        program.policy_authorized_by = user
        program.updated_by = user
        program.version += 1
        program.save(update_fields=['policy_authorized_at', 'policy_authorized_by', 'updated_by', 'version', 'updated_at'])
        record_log(program, 'policy_authorized', notes.strip(), user=user, address=address,
            changes={'policy_authorized_at': {'before': None, 'after': program.policy_authorized_at.isoformat()},
                     'policy_authorized_by': {'before': None, 'after': user.pk},
                     'selection_method': {'before': program.selection_method, 'after': program.selection_method}})
        from ewaf.fixed_scoring import bind as bind_fixed
        if not bind_fixed(program, user=user):
            from ewaf.revised.shared_application import apply as apply_shared_ewaf
            apply_shared_ewaf(program, user=user)
        return program
    if action not in Program.Status.values or action == program.status:
        raise ValidationError('Select a different, valid program status.')
    if action == 'cancelled' and program.published_at is None:
        raise ValidationError('Archive an unpublished draft instead of cancelling it.')
    before = program.status
    guidance = missing_draft_guidance(program) if action == 'published' else {}
    program.status = action
    if action == 'published':
        errors = program.publication_errors()
        if errors:
            raise ValidationError([f'{program._meta.get_field(name).verbose_name.capitalize()}: {message}'
                                   for name, message in errors.items()])
        require_binding(program, first_publication=program.published_at is None)
        from .application_workflow import enabled, require_publication_policy
        if enabled():
            if bool(program.policy_authorized_at) != bool(program.policy_authorized_by_id):
                raise ValidationError('The recorded program authorization is incomplete and needs review.')
            if not program.policy_authorized_at:
                if not program.slots or program.slots < 1:
                    raise ValidationError('Set positive beneficiary slots in Capacity before publishing.')
                guidance_changes = {name: {'before': getattr(program, name), 'after': text}
                                    for name, text in guidance.items()}
                for name, text in guidance.items():
                    setattr(program, name, text)
                if not program.selection_method.strip() or not program.photo_instructions.strip():
                    raise ValidationError('This program has protected or existing application records and incomplete guidance. Review its approved terms before publishing.')
                program.policy_authorized_at = timezone.now()
                program.policy_authorized_by = user
                # Shared EWAF application reloads the locked program. Persist
                # this authorization inside the same publication transaction;
                # any later prerequisite or audit failure rolls it back too.
                program.save(update_fields=['policy_authorized_at', 'policy_authorized_by', *guidance])
                record_log(program, 'policy_authorized', 'Program policy authorized as part of the Publish action.',
                    user=user, address=address, changes={
                        'policy_authorized_at': {'before': None, 'after': program.policy_authorized_at.isoformat()},
                        'policy_authorized_by': {'before': None, 'after': user.pk},
                        'selection_method': {'before': program.selection_method, 'after': program.selection_method},
                        **guidance_changes})
            from ewaf.vault_services import prepare_publication
            prepare_publication(program, user=user)
            require_publication_policy(program)
        # Announcement publication is distinct from authorization to process
        # applications and select beneficiaries. Never invent missing policies.
        if not enabled() and program.photo_instructions.strip() and program.selection_method.strip():
            program.policy_authorized_at = timezone.now()
            program.policy_authorized_by = user
        program.published_at = timezone.now()
    program.full_clean()
    program.updated_by = user
    program.version += 1
    program.save()
    record_log(program, action, notes.strip(), user=user, address=address,
               changes={'status': {'before': before, 'after': action}})
    return program


@source_writer("pk", action="requirement")
@terms_lock()
@transaction.atomic
def save_requirement(pk, *, user, data, requirement_id=None, address=None):
    require_workspace_permissions(user, 'programs.view_program', 'programs.configure_program')
    program = Program.objects.select_for_update().get(pk=pk)
    if program.applications.exists():
        raise ValidationError('Submitted requirements are locked. Preserve their version and create a separately authorized program/version for new requirements.')
    if program.status in ('published', 'cancelled'):
        require_workspace_permissions(user, 'programs.publish_program')
    item = program.configured_requirements.get(pk=requirement_id) if requirement_id else ProgramRequirement(program=program)
    before = {name: str(getattr(item, name)) for name in RequirementForm.Meta.fields}
    form = RequirementForm(data, instance=item)
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    check_version(program, form.cleaned_data['version'])
    check_notes(form.cleaned_data['notes'])
    if requirement_id and is_protected(program):
        return item  # Protected differences were rejected by the form.
    active = program.configured_requirements.filter(is_active=True).exclude(pk=item.pk)
    if item.is_active and active.count() >= 50:
        raise ValidationError('A program can have at most 50 active requirements and questions.')
    if item.is_active and item.kind == 'document' and active.filter(kind='document').count() >= settings.DATA_UPLOAD_MAX_NUMBER_FILES - 1:
        raise ValidationError('The active document count exceeds the upload limit. Deactivate another document requirement first.')
    item.save()
    program.version += 1
    program.updated_by = user
    program.save()
    record_log(program, 'requirement_updated' if requirement_id else 'requirement_added', form.cleaned_data['notes'], user=user,
        address=address, changes={'requirement': {'before': before if requirement_id else '',
                     'after': {'id': item.pk, **{name: str(getattr(item, name)) for name in RequirementForm.Meta.fields}}}})
    return item


@application_writer(submission=True)
@terms_lock()
def submit_application(pk, *, grant, data, files):
    saved_files = submission_files()
    try:
        with transaction.atomic():
            program = Program.objects.select_for_update().get(pk=pk)
            require_open(program)
            from .application_workflow import CONTRACT, enabled, secure_grant
            if enabled() and not secure_grant(grant, program):
                raise ValidationError('Verification expired or application requirements changed. Verify membership again.')
            if not grant_valid(grant, program):
                raise ValidationError('Verification expired or the program changed. Verify your membership again.')
            member = Member.objects.select_for_update().filter(pk=grant.get('member')).first()
            if not member or not member.is_active or member.archived_at or member.version != grant.get('member_version'):
                raise ValidationError('Membership changed. Verify your membership again.')
            require_disability(program, member)
            existing = program.applications.filter(member=member).first()
            if existing:
                if existing.status == 'CLOSED':
                    raise ValidationError('This application was cancelled. Contact the association to request restoration.')
                return existing
            # Rebuild and validate inside the program lock so configuration cannot change mid-submission.
            form_class = ApplicationForm
            if grant.get('application_workflow') == CONTRACT:
                from .confirmation_forms import ConfirmedApplicationForm
                form_class = ConfirmedApplicationForm
            form = form_class(data, files, program=program, member=member)
            if not form.is_valid():
                raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
            check_version(program, form.cleaned_data['version'])
            from .workflow import allocate_reference, store_photo, CONFIGURED_EVIDENCE
            reference = allocate_reference(program)
            if grant.get('application_workflow') == CONTRACT:
                from members.services import fill_application_email
                fill_application_email(member, email=form.cleaned_data['applicant_email'], reference=reference)
            application = ProgramApplication.objects.create(program=program, member=member, public_reference=reference,
                source_snapshot={**grant_authorization(program), 'member_id': member.pk, 'member_version': member.version, 'program_version': program.version,
                                 'membership_verified_at': timezone.now().isoformat(), 'policy_authorized_at': program.policy_authorized_at.isoformat(),
                                 **({'evidence_policy': CONFIGURED_EVIDENCE} if not form.require_calendar_photo else {}),
                                 **({'application_confirmation': {'contract': CONTRACT,
                                     'declared_at': timezone.now().isoformat(), **form.confirmation()}}
                                    if grant.get('application_workflow') == CONTRACT else {})},
                requirements_snapshot=form.snapshot,
                program_snapshot={**{name: str(getattr(program, name)) if getattr(program, name) is not None else None
                                  for name in ProgramForm.Meta.fields if name not in ('budget', 'eligible_disability_types')},
                                  'eligible_disability_types': ', '.join(program.eligible_disability_types.values_list('name', flat=True))},
                answers={str(item['id']): form.cleaned_data[f'requirement_{item["id"]}']
                         for item in form.snapshot if item['kind'] != 'document'})
            for item in form.snapshot:
                if item['kind'] != 'document':
                    continue
                upload = form.cleaned_data.get(f'requirement_{item["id"]}')
                if upload:
                    document = ProgramDocument(application=application, requirement_id=item['id'], label=item['label'],
                                               content_type=upload.content_type, size=upload.size)
                    document.file.save(upload.name, upload, save=False)
                    saved_files.append((document.file.storage, document.file.name))
                    document.save()
                elif item['id'] in form.reused:
                    source, verification = form.reused[item['id']]
                    ProgramDocument.objects.create(application=application, requirement_id=item['id'], label=item['label'],
                        file=source.file.name, content_type=source.content_type, size=source.size,
                        source_document=source, source_verification=verification)
            if form.require_calendar_photo:
                store_photo(application, form.cleaned_data['calendar_photo'], saved_files)
            else:
                application.status = ProgramApplication.Status.ELIGIBILITY_REVIEW
                application.save(update_fields=['status'])
            record_log(program, 'submitted', 'Verified member submitted a program application.', application=application)
            return application
    except Exception:
        for storage, name in saved_files:
            remove_file(storage, name)
        raise


@application_writer()
@transaction.atomic
def change_application(reference, *, user, version, status, notes, address=None):
    require_workspace_permissions(user, 'programs.view_program', 'programs.view_programapplication', 'programs.change_programapplication')
    program_id = ProgramApplication.objects.values_list('program_id', flat=True).get(pk=reference)
    program = Program.objects.select_for_update().get(pk=program_id)
    application = ProgramApplication.objects.select_for_update().get(pk=reference)
    check_version(application, version)
    check_notes(notes)
    from assistance.models import AssistanceCase
    from assistance.services import require_unreleased
    if status == 'CLOSED':
        require_unreleased(application)
        if AssistanceCase.objects.filter(application=application, decision='approved').exists():
            raise ValidationError('Return the assistance approval for review before cancelling this application.')
    if status != 'CLOSED' or status == application.status:
        raise ValidationError('Only reasoned closure is available here. Verification, eligibility and selection use their dedicated review actions.')
    before = application.status
    application.status = status
    application.version += 1
    application.save()
    if status == 'CLOSED':
        from assistance.models import EligibilityStatus
        from assistance.services import case_snapshot, record_log as record_assistance_log
        case = AssistanceCase.objects.filter(application=application).first()
        if case:
            before_case = case_snapshot(case)
            case.eligibility = EligibilityStatus.objects.get(pk='review')
            case.eligibility_label = case.eligibility.label
            case.decision = 'pending'
            case.decision_notes = notes.strip()
            case.decided_at = timezone.now()
            case.decided_by = user
            case.save()
            record_assistance_log(application, user, 'application_cancelled', notes,
                                  {'before': before_case, 'after': case_snapshot(case)}, address)
    record_log(program, 'application_updated', notes.strip(), user=user, application=application, address=address,
               changes={'status': {'before': before, 'after': status}})
    return application
