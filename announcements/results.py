"""Explicit, versioned publication of privacy-masked official program results."""
from collections import Counter
import hashlib
import json
import re

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from core.permissions import require_workspace_permissions
from members.models import Member
from programs.models import Program
from programs.terms import terms_lock
from programs.workflow import require_verified_photo
from assistance.services import require_current_review
from .models import Announcement, ProgramResultRevision
from .services import record_event

RESULT_PERMISSIONS = ('announcements.view_announcement', 'programs.view_program',
                      'programs.view_programapplication', 'assistance.view_assistancecase')


@transaction.atomic
def collect_recipients(program):
    """Actual non-voided receipts, with the existing approved public identity mask."""
    from assistance.models import AssistanceRelease
    receipts = list(AssistanceRelease.objects.successful().filter(application__program=program)
        .select_related('application__member').order_by('pk'))
    if not receipts:
        raise ValidationError('Record actual assistance receipts for this program before preparing a recipient announcement.')
    rows, sources = [], []
    for receipt in receipts:
        application = receipt.application
        row = mask_identity(application.member.full_name, application.public_reference)
        row['status'] = 'Received'
        rows.append(row)
        sources.append({'receipt': str(receipt.pk), 'application': str(application.pk),
                        'member_version': application.member.version,
                        'received_on': str(receipt.released_on), 'recorded_at': receipt.recorded_at.isoformat(),
                        'approval': receipt.approval_snapshot})
    rows.sort(key=lambda row: (row['name'], row['reference']))
    counts = Counter((row['name'], row['reference']) for row in rows)
    for row in rows:
        row['ambiguous'] = counts[(row['name'], row['reference'])] > 1
    payload = {
        'schema': 1, 'kind': 'assistance_recipients', 'program_name': program.name,
        'description': program.description,
        'program_date': timezone.localtime(program.starts_at).strftime('%B %d, %Y') if program.starts_at else 'See program schedule',
        'slots': program.slots, 'selection_method': program.selection_method,
        'eligibility_explanation': 'This announcement lists members with confirmed assistance receipts for this program.',
        'ewaf_explanation': 'Approval and actual receipt are separate. Only recorded, non-voided receipts appear below.',
        'rows': rows,
    }
    fingerprint = {'program_version': program.version, 'sources': sources, 'payload': payload}
    return payload, hashlib.sha256(json.dumps(fingerprint, sort_keys=True, default=str).encode()).hexdigest()


def mask_identity(name, reference):
    # One fixed mask per word; no surname parsing or disclosure of word length.
    initials = [next((char.upper() for char in part if char.isalpha()), '') for part in name.split()]
    masked = ' '.join(initial + '***' for initial in initials if initial) or 'Participant'
    if len(reference) <= 4 or not re.fullmatch(r'[A-Za-z0-9-]+', reference):
        raise ValidationError('This legacy reference needs an approved safe display before publication.')
    return {'name': masked, 'reference': '****' + reference[-4:], 'status': 'Selected'}


@transaction.atomic
def collect_results(program):
    """Return an allowlisted public projection and a private source fingerprint."""
    now = timezone.now()
    if (program.status != 'published' or not program.published_at or program.published_at > now
            or program.registration_closes_at > now):
        raise ValidationError('Publish results only after the published program application period closes.')
    if not program.policy_authorized_at or not program.selection_method.strip():
        raise ValidationError('This program needs an authorized selection method. Open the program review page, enter the approved selection method and calendar-photo instructions, then choose “Authorize program policy” in its Publication controls. For a draft program, authorize these policies when publishing it.')
    if program.ewaf_applicable:
        from ewaf.operational_services import available, publication_snapshot
        from ewaf.operational_models import OperationalConfiguration
        if available() and OperationalConfiguration.objects.filter(program=program).exists():
            return publication_snapshot(program)
        raise ValidationError('EWAF program results are not available in this version. This program requires EWAF calculation and ranking before final selection and result publication. Keep its approved selection method and wait until that workflow is available; do not switch off EWAF to bypass this requirement.')
    rows, sources, eligible_count = [], [], 0
    for application in program.applications.select_related('member', 'current_photo', 'assistance_case').order_by('pk'):
        case = getattr(application, 'assistance_case', None)
        source = {'application': str(application.pk), 'status': application.status,
                  'member_version': application.member.version}
        if application.status in ('INELIGIBLE', 'VERIFICATION_FAILED', 'CLOSED'):
            # Excluded final outcomes are never exposed as participant rows.
            sources.append(source)
            continue
        if application.status not in ('SELECTED', 'NOT_SELECTED', 'COMPLETED') or not case:
            raise ValidationError('Finish every application review and official decision before preparing final results. Needs Information and pending reviews must be resolved first.')
        if not application.member.is_active or application.member.archived_at:
            raise ValidationError('A result refers to inactive membership. Review the official decisions first.')
        review = require_verified_photo(application)
        require_current_review(case, program, application.member)
        expected = 'rejected' if application.status == 'NOT_SELECTED' else 'approved'
        if case.decision != expected or not case.decided_at or not case.decision_notes.strip():
            raise ValidationError('A current, reasoned official decision is required for each eligible application.')
        eligible_count += 1
        source.update(photo=application.current_photo_id, photo_review=review.pk,
                      reviewed_at=case.reviewed_at.isoformat(), decided_at=case.decided_at.isoformat(),
                      decision=case.decision, checklist=case.checklist)
        # Actual receipt does not change the authorized Selected result.
        source['status'] = 'NOT_SELECTED' if expected == 'rejected' else 'SELECTED'
        sources.append(source)
        if expected == 'approved':
            rows.append(mask_identity(application.member.full_name, application.public_reference))
    if program.slot_limit is not None and len(rows) > program.slot_limit:
        raise ValidationError('Selected participants exceed the authorized available slots.')
    rows.sort(key=lambda row: (row['name'], row['reference']))
    counts = Counter((row['name'], row['reference']) for row in rows)
    for row in rows:
        row['ambiguous'] = counts[(row['name'], row['reference'])] > 1
    payload = {
        'schema': 1, 'program_name': program.name, 'description': program.description,
        'program_date': timezone.localtime(program.starts_at).strftime('%B %d, %Y, %I:%M %p') if program.starts_at else 'Schedule to be announced',
        'slots': program.slots, 'eligible_count': eligible_count, 'selection_method': program.selection_method,
        'eligibility_explanation': 'Only verified association members who completed manual photo verification and met the program requirements were considered. Authorized administrators recorded the final decisions using the approved selection method.',
        'ewaf_explanation': 'This program uses the approved selection method shown here. EWAF ranking was not used.',
        'rows': rows,
    }
    fingerprint = {'program_version': program.version, 'policy_authorized_at': program.policy_authorized_at.isoformat(),
                   'sources': sources, 'public_payload': payload}
    digest = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, default=str).encode()).hexdigest()
    return payload, digest


def results_current(item):
    revision = item.result_revision
    if not revision or revision.announcement_id != item.pk or not item.program_id:
        return False
    try:
        if revision.public_payload.get('publication_mode') == 'recorded':
            from .recorded_results import collect_recorded_results
            collector = collect_recorded_results
        elif revision.public_payload.get('kind') == 'program_participation':
            from .participation import collect_program_results
            collector = lambda program: collect_program_results(program, retained_revision=revision)
        else:
            collector = collect_recipients if revision.public_payload.get('kind') == 'assistance_recipients' else collect_results
        from programs.mandatory_ewaf import publication_source_program
        payload, digest = collector(publication_source_program(item.program, revision))
        from .selection_reason import retained_selection_reason
        payload, digest = retained_selection_reason(payload, digest, revision.public_payload)
    except ValidationError:
        return False
    return digest == revision.source_digest and payload == revision.public_payload


def lock_program(pk):
    program = Program.objects.select_for_update().get(pk=pk)
    # Serialize with verified member/document corrections as well as program decisions.
    list(Member.objects.select_for_update().filter(program_applications__program=program).order_by('pk'))
    return program


@terms_lock()
@transaction.atomic
def prepare_results(program_id, *, user, version, reason, address=None, recipients=False, roster=False, recorded=False,
                    selection_reason=None):
    require_workspace_permissions(user, *RESULT_PERMISSIONS, 'announcements.add_announcement', 'announcements.change_announcement')
    if recipients:
        require_workspace_permissions(user, 'assistance.view_assistancerelease')
    program = lock_program(program_id)
    item = Announcement.objects.select_for_update().filter(program=program).first()
    if version != (item.version if item else 0):
        raise ValidationError('Another administrator changed this announcement. Reload before preparing a revision.')
    if not reason.strip() or len(reason) > 2000:
        raise ValidationError('Record a preparation/revision reason of up to 2,000 characters.')
    if item and item.status == 'deleted':
        raise ValidationError('This announcement was deleted and cannot be republished.')
    if item and item.status == 'published':
        require_workspace_permissions(user, 'announcements.publish_announcement')
    if recorded:
        require_workspace_permissions(user, 'announcements.publish_announcement')
        from .recorded_results import collect_recorded_results
        payload, digest = collect_recorded_results(program)
    elif roster:
        from .participation import collect_program_results
        if recipients:
            raise ValidationError('Prepare the program roster separately from historical receipt-only revisions.')
        payload, digest = collect_program_results(program)
    else:
        payload, digest = (collect_recipients if recipients else collect_results)(program)
    if selection_reason is not None:
        from .selection_reason import with_selection_reason
        payload, digest = with_selection_reason(payload, digest, selection_reason)
    previous_content = ({'title': item.title, 'content': item.content, 'status': item.status,
        'published_at': item.published_at.isoformat() if item.published_at else None,
        'version': item.version, 'result_revision': item.result_revision_id} if item else {})
    if item is None:
        item = Announcement(program=program, created_by=user)
    previous_status = item.status
    item.title = f'{"Assistance recipients" if recipients else "Results"}: {program.name}'[:200]
    item.content = ('Confirmed assistance recipients. ' if recipients else 'Official program results. ') + 'Please keep your original application reference and contact the Barangay Santolan PWD Association Help Desk for assistance.'
    item.status = 'draft'
    item.updated_by = user
    item.version += 1
    item.save()
    previous = item.result_revisions.first()
    revision = ProgramResultRevision.objects.create(announcement=item, number=(previous.number + 1 if previous else 1),
        public_payload=payload, previous_announcement=previous_content, source_digest=digest,
        reason=reason.strip(), created_by=user, creator_label=user.get_username())
    item.result_revision = revision
    item.save(update_fields=['result_revision'])
    source_label = 'recorded selections independently of review readiness' if recorded else 'current official decisions'
    record_event(item, user, 'results_prepared', f'Result revision {revision.number} prepared from {source_label}; previous status {previous_status}. Reason retained in revision history.', address)
    return item


@terms_lock()
@transaction.atomic
def publish_results(pk, *, user, version, address=None):
    require_workspace_permissions(user, *RESULT_PERMISSIONS, 'announcements.publish_announcement')
    program_id = Announcement.objects.values_list('program_id', flat=True).get(pk=pk)
    program = lock_program(program_id)
    item = Announcement.objects.select_for_update().select_related('result_revision').get(pk=pk)
    if item.result_revision and item.result_revision.public_payload.get('kind') == 'assistance_recipients':
        require_workspace_permissions(user, 'assistance.view_assistancerelease')
    item.program = program
    if item.version != version or item.status not in ('draft', 'archived'):
        raise ValidationError('Reload the draft before publishing; this version is no longer available.')
    if not results_current(item):
        raise ValidationError('These results are missing or changed after preparation. Prepare and review a new result revision before publishing.')
    from .selection_reason import clean_selection_reason
    clean_selection_reason(item.result_revision.public_payload.get('selection_reason'))
    item.status = 'published'
    item.published_at = timezone.now()
    item.updated_by = user
    item.version += 1
    item.save()
    record_event(item, user, 'results_published', f'Authorized publication of reviewed privacy-masked result revision {item.result_revision.number}.', address)
    return item
