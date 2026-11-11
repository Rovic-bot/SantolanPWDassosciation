"""Two bounded evidence writers; verified disposable sessions only.

No storage overwrite/version policy or operational result interface is introduced.
The existing local non-overwriting storage contract is required for this gate.
"""
from contextvars import ContextVar
from functools import wraps
from inspect import signature

_files = ContextVar('generation_correction_files', default=None)


def correction_files():
    journal = _files.get()
    return journal if journal is not None else []


def _rows(model):
    return {row[model._meta.pk.attname]: row for row in model.objects.order_by('pk').values()}


def _added(model, before):
    from django.core.exceptions import ValidationError
    after = _rows(model)
    if any(after.get(pk) != row for pk, row in before.items()):
        raise ValidationError('EVIDENCE_HISTORY_CHANGED')
    return list(model.objects.filter(pk__in=set(after) - set(before)).order_by('pk'))


def _storage():
    from django.core.exceptions import ValidationError
    from django.core.files.storage import FileSystemStorage
    from programs.models import ApplicationPhoto, ProgramDocument
    for model in (ApplicationPhoto, ProgramDocument):
        storage = model._meta.get_field('file').storage
        if storage.__class__ is not FileSystemStorage or storage._allow_overwrite:
            raise ValidationError('NONOVERWRITING_LOCAL_STORAGE_REQUIRED')


def _validate(*, app, before, member, actor, data, correction, replacing, history, documents,
              logs, case_logs, before_case, completed_reassessment=False):
    from django.core.exceptions import ValidationError
    from programs.models import ApplicationPhoto, PhotoVerification, ProgramDocument, ProgramDocumentRevision
    from assistance.models import AssistanceCase
    from assistance.services import case_snapshot
    from documents.services import program_document_current

    def require(condition, message):
        if not condition:
            raise ValidationError(message)

    require((app.program_id, app.member_id, app.public_reference, app.version) ==
        (before['program_id'], before['member_id'], before['public_reference'], before['version'] + 1),
        'EVIDENCE_APPLICATION_SCOPE_OR_VERSION')
    photos = _added(ApplicationPhoto, history[ApplicationPhoto])
    reviews = _added(PhotoVerification, history[PhotoVerification])
    revisions = _added(ProgramDocumentRevision, history[ProgramDocumentRevision])
    reason = str(data.get('reason', '')).strip()
    require(len(photos) == int(replacing), 'EVIDENCE_PHOTO_SCOPE')
    photo = app.current_photo
    require(photo is not None and photo.application_id == app.pk and photo.file.storage.exists(photo.file.name),
            'EVIDENCE_CURRENT_PHOTO_MISSING_OR_FOREIGN')
    if replacing:
        require(photos[0].pk == photo.pk and photo.uploaded_by_id == actor.pk and
            photo.member_version == member.version and photo.reason == reason and
            photo.file.name not in {row['file'] for row in history[ApplicationPhoto].values()},
            'EVIDENCE_NEW_PHOTO_INVALID')
    else:
        require(app.current_photo_id == before['current_photo_id'], 'EVIDENCE_PHOTO_POINTER_CHANGED')
    require(len(reviews) == int(not correction or replacing), 'EVIDENCE_REVIEW_SCOPE')
    if reviews:
        review = reviews[0]
        outcome = 'PENDING' if correction else data.get('outcome')
        category = '' if correction else str(data.get('category', '')).strip()
        require((review.photo_id, review.outcome, review.reviewer_id, review.reviewer_label,
                 review.member_version, review.reason, review.category) ==
                (photo.pk, outcome, actor.pk, actor.get_username(), member.version, reason, category),
                'EVIDENCE_REVIEW_INVALID')
    if not correction:
        expected_status = {'VERIFIED': 'PHOTO_VERIFIED', 'NEEDS_RESUBMISSION': 'NEEDS_INFORMATION',
            'REJECTED': 'VERIFICATION_FAILED'}.get(data.get('outcome'))
        if completed_reassessment:
            from assistance.reassessment import completed_receipt
            completed_receipt(app)
            require(before['status'] == 'COMPLETED' and data.get('outcome') == 'VERIFIED',
                    'EVIDENCE_COMPLETED_REASSESSMENT')
            expected_status = 'COMPLETED'
        require(app.status == expected_status, 'EVIDENCE_REVIEW_STATUS')
        expected_changes = {'status': {'before': before['status'], 'after': app.status},
            'photo_review': {'before': None, 'after': {'photo': str(photo.pk), 'review': reviews[0].pk,
                'outcome': reviews[0].outcome, 'category': reviews[0].category}}}
        require(app.answers == before['answers'] and app.source_snapshot == before['source_snapshot'],
                'EVIDENCE_REVIEW_CHANGED_APPLICATION')
    else:
        require(app.status in ('PENDING_PHOTO_VERIFICATION', 'ELIGIBILITY_REVIEW') and
            (not replacing or app.status == 'PENDING_PHOTO_VERIFICATION'), 'EVIDENCE_CORRECTION_STATUS')
        expected_changes = {key: {'before': before[key], 'after': getattr(app, key)}
                            for key in ('answers', 'status', 'source_snapshot')}
    require(len(logs) == 1, 'EVIDENCE_NATIVE_AUDIT_SCOPE')
    log = logs[0]
    require((log.program_id, log.application_id, log.actor_id, log.actor_label, log.action, log.notes, log.changes) ==
        (app.program_id, app.pk, actor.pk, actor.get_username(),
         'application_corrected' if correction else 'photo_verified', reason, expected_changes),
         'EVIDENCE_NATIVE_AUDIT_INVALID')

    after_docs = _rows(ProgramDocument)
    require(set(documents) <= set(after_docs), 'EVIDENCE_DOCUMENT_REMOVED')
    changed = {pk for pk, row in after_docs.items() if documents.get(pk) != row}
    require(correction or not changed, 'EVIDENCE_REVIEW_CHANGED_DOCUMENT')
    expected_revisions = []
    fields = ('file', 'content_type', 'size', 'source_document_id', 'source_verification_id')
    for pk in changed:
        doc = ProgramDocument.objects.get(pk=pk)
        require(doc.application_id == app.pk and doc.requirement.program_id == app.program_id,
                'EVIDENCE_DOCUMENT_SCOPE')
        if pk in documents:
            old = documents[pk]
            require((old['application_id'], old['requirement_id'], old['label']) ==
                    (doc.application_id, doc.requirement_id, doc.label), 'EVIDENCE_DOCUMENT_IDENTITY')
            expected_revisions.append({'document_id': pk, **{key: old[key] for key in fields},
                'actor_id': actor.pk, 'actor_label': actor.get_username(), 'reason': reason})
    actual_revisions = [{key: getattr(row, key) for key in ('document_id', *fields,
        'actor_id', 'actor_label', 'reason')} for row in revisions]
    require(sorted(actual_revisions, key=lambda r: str(r['document_id'])) ==
            sorted(expected_revisions, key=lambda r: str(r['document_id'])), 'EVIDENCE_DOCUMENT_REVISION_SCOPE')
    for doc in ProgramDocument.objects.filter(application=app):
        require(doc.requirement.program_id == app.program_id, 'EVIDENCE_DOCUMENT_SCOPE')
        if doc.source_document_id:
            require(doc.source_document.application_id == member.application_id and
                doc.source_verification_id is not None and
                doc.source_verification.document_id == doc.source_document_id, 'EVIDENCE_REUSED_DOCUMENT_SCOPE')
        require(program_document_current(doc, member), 'EVIDENCE_DOCUMENT_MISSING_OR_STALE')
    require(len(case_logs) == int(before_case is not None), 'EVIDENCE_CASE_AUDIT_SCOPE')
    if before_case is not None:
        case = AssistanceCase.objects.get(application=app)
        case_log = case_logs[0]
        require((case.eligibility_id, case.eligibility_label, case.decision, case.decision_notes,
                 case.decided_at, case.decided_by_id) ==
                ('review', 'Needs Information', 'pending', 'Evidence changed; current eligibility review is required.', None, None),
                'EVIDENCE_CASE_NOT_INVALIDATED')
        require((case_log.application_id, case_log.actor_id, case_log.actor_label, case_log.action,
                 case_log.notes, case_log.snapshot) ==
                (app.pk, actor.pk, actor.get_username(), 'evidence_invalidated', reason,
                 {'before': before_case, 'after': case_snapshot(case)}), 'EVIDENCE_CASE_AUDIT_INVALID')
    else:
        require(not AssistanceCase.objects.filter(application=app).exists(), 'EVIDENCE_UNEXPECTED_CASE')
    return logs + case_logs + reviews + revisions


def photo_writer(*, correction=False):
    def decorate(function):
        spec = signature(function)

        @wraps(function)
        def wrapped(*args, **kwargs):
            from accounts.authority_services import enlisted
            from django.core.exceptions import PermissionDenied, ValidationError
            expected = kwargs.pop('source_expected', None)
            if not enlisted():
                if expected is not None:
                    raise PermissionDenied('Source tokens require a registered disposable session.')
                from programs.terms import terms_lock as operational_terms_lock
                with operational_terms_lock():
                    return function(*args, **kwargs)
            from django.db.models import Max
            from programs.models import (Program, ProgramApplication, ProgramRequirement, ProgramLog,
                ProgramDocument, ProgramDocumentRevision, ApplicationPhoto, PhotoVerification)
            from members.models import Member
            from documents.models import MembershipApplicationDocument, DocumentVerification
            from assistance.models import EligibilityStatus, AssistanceCase, AssistanceLog
            from assistance.services import case_snapshot
            from announcements.services import remove_file
            from programs.terms import terms_lock
            from . import generation_services as generation
            from .generation_models import ProgramSourceState
            from .generation_records import _owned_transaction
            from .source_invalidation import _actor, _authority_identity, _final_validate

            generation.durable_services._boundary()
            bound = spec.bind(*args, **kwargs)
            bound.apply_defaults()
            arguments = bound.arguments
            journal = []
            token = _files.set(journal)
            try:
                with terms_lock(), _owned_transaction():
                    authority = generation._authority()
                    program_id = ProgramApplication.objects.values_list('program_id', flat=True).get(pk=arguments['reference'])
                    program = Program.objects.select_for_update().get(pk=program_id)
                    state = ProgramSourceState.objects.select_for_update().filter(program=program).first()
                    if not isinstance(expected, dict) or set(expected) != {str(program.pk)}:
                        raise ValidationError('INCOMPLETE_SOURCE_SCOPE')
                    prior = expected[str(program.pk)]
                    generation._expect(state, authority, prior)
                    actor = _actor(arguments['user'])
                    identity = _authority_identity(actor)
                    arguments['user'] = actor
                    app = ProgramApplication.objects.select_for_update().get(pk=arguments['reference'], program=program)
                    member = Member.objects.select_for_update().get(pk=app.member_id)
                    # Ordered leaves; no joined locking query can pull Photo before Member.
                    list(EligibilityStatus.objects.select_for_update().filter(pk='review'))
                    list(ProgramRequirement.objects.select_for_update().filter(program=program).order_by('pk'))
                    list(MembershipApplicationDocument.objects.select_for_update().filter(application_id=member.application_id).order_by('pk'))
                    list(DocumentVerification.objects.select_for_update().filter(document__application_id=member.application_id)
                         .order_by('pk').select_for_update(of=('self',)))
                    list(ProgramDocument.objects.select_for_update().filter(application=app).order_by('pk'))
                    list(ApplicationPhoto.objects.select_for_update().filter(application=app).order_by('pk'))
                    list(PhotoVerification.objects.filter(photo__application=app).order_by('pk').select_for_update(of=('self',)))
                    case = AssistanceCase.objects.select_for_update().filter(application=app).first()
                    if app.current_photo_id and not ApplicationPhoto.objects.filter(pk=app.current_photo_id, application=app).exists():
                        raise ValidationError('EVIDENCE_CURRENT_PHOTO_MISSING_OR_FOREIGN')
                    before = ProgramApplication.objects.values().get(pk=app.pk)
                    before_case = case_snapshot(case) if case else None
                    history = {model: _rows(model) for model in (ApplicationPhoto, PhotoVerification, ProgramDocumentRevision)}
                    documents = _rows(ProgramDocument)
                    start = ProgramLog.objects.aggregate(value=Max('pk'))['value'] or 0
                    case_start = AssistanceLog.objects.aggregate(value=Max('pk'))['value'] or 0
                    _storage()
                    result = function(*bound.args, **bound.kwargs)
                    if not enlisted() or _authority_identity(_actor(actor)) != identity:
                        raise PermissionDenied('Evidence actor or disposable session changed.')
                    app = ProgramApplication.objects.get(pk=app.pk)
                    logs = list(ProgramLog.objects.filter(pk__gt=start).order_by('pk'))
                    case_logs = list(AssistanceLog.objects.filter(pk__gt=case_start).order_by('pk'))
                    audits = _validate(app=app, before=before, member=member, actor=actor, data=arguments['data'],
                        correction=correction, replacing=bool(correction and arguments['files'].get('calendar_photo')),
                        history=history, documents=documents, logs=logs, case_logs=case_logs, before_case=before_case,
                        completed_reassessment=arguments.get('completed_reassessment', False))
                    if ((correction and (not isinstance(result, ProgramApplication) or result.pk != app.pk)) or
                            (not correction and (not isinstance(result, PhotoVerification) or
                             result.pk not in {row.pk for row in audits if isinstance(row, PhotoVerification)}))):
                        raise ValidationError('EVIDENCE_RESULT_SCOPE')
                    generation._expect(state, generation._authority(), prior)
                    batch = generation._invalidate([state], kind='SOURCE_CHANGE', source_kind='application',
                        source_id=str(app.pk), metadata=generation._metadata(actor, 'APPLICATION_EVIDENCE',
                            'Application photo review or correction.'),
                        native_audits=[generation.native_reference(row) for row in audits])
                    _final_validate(state, authority, prior, batch)
                    return result
            except Exception:
                for storage, name in journal:
                    remove_file(storage, name)
                raise
            finally:
                _files.reset(token)
        return wrapped
    return decorate
