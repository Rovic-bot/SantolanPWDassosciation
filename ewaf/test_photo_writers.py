"""Gate 2D-2B fictional evidence, rollback and real MySQL lock tests."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from threading import Event
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from accounts import authority_services
from accounts.tests.test_authority_generation import worker
from announcements.tests import image_upload
from assistance import services as assistance
from assistance.models import AssistanceCase, AssistanceLog, EligibilityStatus
from assistance.tests import seed_statuses
from members.tests import create_member
from membership.tests import pdf
from programs import workflow, services as programs
from programs.models import (Program, ProgramApplication, ProgramLog, ProgramRequirement, ApplicationPhoto,
    PhotoVerification, ProgramDocument, ProgramDocumentRevision)
from programs.testsupport import application_fixture
from . import photo_invalidation as adapter, generation_services as generation
from .generation_models import ProgramSourceState, SourceInvalidation, SourceMutationBatch
from .test_source_writers import SourceHelpers
from .durable_testsupport import DurableHelpers


class PhotoHelpers(SourceHelpers):
    def setup_photo(self):
        self.setup_foundation()
        seed_statuses()
        self.member = create_member('FICTIONAL-PHOTO-G18')
        self.member.refresh_from_db()
        self.application = application_fixture(self.program, self.member)
        self.requirement = ProgramRequirement.objects.create(program=self.program, kind='document',
            label='Fictional supporting evidence', is_active=True, is_required=True)
        upload = pdf()
        self.document = ProgramDocument.objects.create(application=self.application, requirement=self.requirement,
            label=self.requirement.label, file=upload, content_type=upload.content_type, size=upload.size)
        self.case = AssistanceCase.objects.create(application=self.application,
            eligibility=EligibilityStatus.objects.get(pk='eligible'), eligibility_label='Eligible',
            review_notes='Fictional review', reviewed_at=timezone.now(), reviewed_by=self.officer,
            member_version=self.member.version, program_version=self.program.version)
        from documents.models import DocumentType
        self.reusable_type = DocumentType.objects.create(name='Fictional reusable source')
        self.register()

    def review(self, *, expected='current', **values):
        self.application.refresh_from_db()
        token = self.expected() if expected == 'current' else expected
        return workflow.review_photo(self.application.pk, user=self.officer, source_expected=token,
            data={'version': self.application.version, 'photo_id': self.application.current_photo_id,
                'outcome': 'VERIFIED', 'confirm': True, 'reason': 'Fictional manual verification',
                'category': 'Fictional clarity', **values})

    def correct(self, *, files=None, expected='current', **values):
        self.application.refresh_from_db()
        token = self.expected() if expected == 'current' else expected
        return workflow.correct_application(self.application.pk, user=self.officer, source_expected=token,
            data={'version': self.application.version, 'reason': 'Fictional assisted correction', **values},
            files=files if files is not None else MultiValueDict())

    def replacements(self):
        return MultiValueDict({'calendar_photo': [image_upload()], f'requirement_{self.requirement.pk}': [pdf()]})

    def file_hashes(self):
        return {str(p.relative_to(settings.MEDIA_ROOT)): sha256(p.read_bytes()).hexdigest()
                for p in Path(settings.MEDIA_ROOT).rglob('*') if p.is_file()}

    def snapshot(self):
        return {model._meta.label: list(model.objects.order_by('pk').values()) for model in
            (ProgramApplication, ApplicationPhoto, PhotoVerification, ProgramDocument, ProgramDocumentRevision,
             AssistanceCase, ProgramLog, AssistanceLog, ProgramSourceState, SourceMutationBatch, SourceInvalidation)}

    def rollback(self, operation, target, replacement=None):
        before, files = self.snapshot(), self.file_hashes()
        context = (patch(target, replacement) if replacement is not None else
                   patch(target, side_effect=ValidationError('Fictional audit failure')))
        with context, self.assertRaises(ValidationError):
            operation()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(files, self.file_hashes())


class PhotoWriterTests(PhotoHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_photo()

    def test_verified_review_retains_native_records_and_invalidates_case(self):
        files = self.file_hashes()
        review = self.review()
        self.application.refresh_from_db(); self.case.refresh_from_db()
        self.assertEqual((self.application.status, self.case.eligibility_id, self.case.decision),
                         ('PHOTO_VERIFIED', 'review', 'pending'))
        batch = ProgramSourceState.objects.get(program=self.program).last_invalidation.batch
        self.assertEqual({r['model'] for r in batch.source_audits},
                         {'programs.programlog', 'assistance.assistancelog', 'programs.photoverification'})
        self.assertIn(str(review.pk), [r['pk'] for r in batch.source_audits])
        self.assertEqual(files, self.file_hashes())
        self.assert_transition(2)

    def test_needs_resubmission_requires_replacement_and_keeps_old_photo(self):
        old, files = self.application.current_photo_id, self.file_hashes()
        self.review(outcome='NEEDS_RESUBMISSION')
        with self.assertRaises(ValidationError):
            self.correct()
        self.correct(files=MultiValueDict({'calendar_photo': [image_upload()]}))
        self.application.refresh_from_db()
        self.assertNotEqual(self.application.current_photo_id, old)
        self.assertEqual(ApplicationPhoto.objects.get(pk=old).reviews.first().outcome, 'NEEDS_RESUBMISSION')
        self.assertTrue(files.items() <= self.file_hashes().items())
        self.assert_transition(3)

    def test_rejected_review_cannot_reopen_through_correction(self):
        self.review(outcome='REJECTED')
        with self.assertRaises(ValidationError):
            self.correct(files=self.replacements())
        self.assert_transition(2)

    def test_confirmation_reason_and_category_preserved(self):
        for values in ({'confirm': False}, {'reason': ''}, {'outcome': 'REJECTED', 'category': ''}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.review(**values)
        self.assert_transition(1)

    def test_stale_business_version_and_photo_id_rejected(self):
        for values in ({'version': 999}, {'photo_id': '00000000-0000-0000-0000-000000000001'}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.review(**values)
        self.assert_transition(1)

    def test_stale_and_incomplete_generation_tokens_rejected(self):
        for expected in (None, {}, {**self.expected(), 'extra': self.token()}):
            with self.subTest(expected=expected), self.assertRaises(ValidationError):
                self.review(expected=expected)
        old = self.expected()
        self.review()
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION'):
            self.correct(expected=old)
        self.assert_transition(2)

    def test_missing_source_state_rejected(self):
        token = self.expected()
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM ewaf_programsourcestate WHERE program_id=%s', [self.program.pk.hex])
        with self.assertRaisesMessage(ValidationError, 'SOURCE_STATE_NOT_INITIALIZED'):
            self.review(expected=token)

    def test_missing_current_photo_blocks_review_and_unreplaced_correction(self):
        photo = self.application.current_photo
        photo.file.storage.delete(photo.file.name)
        with self.assertRaises(ValidationError):
            self.review()
        with self.assertRaisesMessage(ValidationError, 'PHOTO_MISSING'):
            self.correct()
        self.assert_transition(1)

    def test_missing_current_document_rejected_without_retaining_review(self):
        self.document.file.storage.delete(self.document.file.name)
        with self.assertRaisesMessage(ValidationError, 'DOCUMENT_MISSING'):
            self.review()
        self.assert_transition(1)

    def test_inactive_member_and_unauthorized_policy_rejected(self):
        type(self.member).objects.filter(pk=self.member.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            self.review()
        type(self.member).objects.filter(pk=self.member.pk).update(is_active=True)
        Program.objects.filter(pk=self.program.pk).update(policy_authorized_at=None)
        with self.assertRaises(ValidationError):
            self.review()
        self.assert_transition(1)

    def test_fresh_permission_recheck_and_no_cached_superuser_bypass(self):
        expected = self.expected()
        get_user_model().objects.filter(pk=self.officer.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied):
            self.review(expected=expected)
        self.assertEqual(ProgramSourceState.objects.get(program=self.program).generation, 1)

    def test_missing_program_audit_rolls_back_review_and_case(self):
        self.rollback(self.review, 'programs.services.record_log', lambda *a, **k: None)

    def test_duplicate_native_audit_rolls_back(self):
        original = programs.record_log
        def duplicate(*a, **k):
            original(*a, **k)
            return original(*a, **k)
        self.rollback(self.review, 'programs.services.record_log', duplicate)

    def test_forged_native_review_link_rolls_back(self):
        original = programs.record_log
        def forged(*a, **k):
            k['changes']['photo_review']['after']['review'] = 1234567
            return original(*a, **k)
        self.rollback(self.review, 'programs.services.record_log', forged)

    def test_duplicate_photo_review_rejected(self):
        original = PhotoVerification.objects.create
        def duplicate(**kwargs):
            original(**kwargs)
            return original(**kwargs)
        self.rollback(self.review, 'programs.workflow.PhotoVerification.objects.create', duplicate)

    def test_photo_review_wrong_actor_rejected(self):
        original = PhotoVerification.objects.create
        def forged(**kwargs):
            kwargs['reviewer'] = None
            return original(**kwargs)
        self.rollback(self.review, 'programs.workflow.PhotoVerification.objects.create', forged)

    def test_missing_case_audit_rejected(self):
        self.rollback(self.review, 'assistance.services.record_log', lambda *a, **k: None)

    def test_duplicate_case_audit_rejected(self):
        original = assistance.record_log
        def duplicate(*a, **k):
            original(*a, **k)
            return original(*a, **k)
        self.rollback(self.review, 'assistance.services.record_log', duplicate)

    def test_cross_program_native_audit_rejected(self):
        from programs.tests import create_program
        other = create_program()
        original = programs.record_log
        def foreign(program, *args, **kwargs):
            return original(other, *args, **kwargs)
        self.rollback(self.review, 'programs.services.record_log', foreign)

    def test_cross_application_photo_review_rejected(self):
        member = create_member('FICTIONAL-FOREIGN-REVIEW')
        other = application_fixture(self.program, member)
        original = PhotoVerification.objects.create
        def foreign(**kwargs):
            kwargs['photo'] = other.current_photo
            return original(**kwargs)
        self.rollback(self.review, 'programs.workflow.PhotoVerification.objects.create', foreign)

    def test_case_without_invalidation_is_rejected(self):
        self.rollback(self.review, 'programs.workflow.invalidate_case', lambda *a, **k: None)

    def test_audit_and_cas_failure_roll_back_complete_review(self):
        for target in ('ewaf.generation_services._persist', 'ewaf.generation_services._cas_source',
                       'ewaf.source_invalidation._final_validate'):
            with self.subTest(target=target):
                self.rollback(self.review, target)

    def test_repeated_same_outcome_retains_distinct_audit_and_generation(self):
        first = self.review()
        second = self.review()
        self.assertNotEqual(first.pk, second.pk)
        self.assert_transition(3)

    def test_existing_native_hashes_unchanged_and_new_evidence_hashes_replay(self):
        self.correct(files=self.replacements())
        batch = ProgramSourceState.objects.get(program=self.program).last_invalidation.batch
        for model in (ProgramLog, AssistanceLog):
            row = model.objects.latest('pk')
            expected = generation.digest({'version': 'g18-native-audit-1', 'model': row._meta.label_lower,
                'fields': {f.attname: getattr(row, f.attname) for f in row._meta.concrete_fields}})
            ref = next(r for r in batch.source_audits if r['model'] == row._meta.label_lower)
            self.assertEqual(ref['digest'], expected)
        generation._native_audits(batch.source_audits, required=True)
        revision = ProgramDocumentRevision.objects.get(document=self.document)
        # Privileged tampering is outside writer coverage, but retained reference
        # validation must detect it rather than silently reinterpret history.
        ProgramDocumentRevision.objects.filter(pk=revision.pk).update(reason='Fictional forged revision')
        with self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT_CHANGED'):
            generation._native_audits(batch.source_audits, required=True)

    def test_review_then_restored_status_does_not_restore_generation(self):
        old = self.expected()
        self.review(outcome='NEEDS_RESUBMISSION')
        self.review(outcome='VERIFIED')
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION'):
            self.review(expected=old)
        self.assert_transition(3)

    def test_correction_replaces_document_and_photo_without_overwriting_history(self):
        old_files = self.file_hashes()
        old_photo, old_document = self.application.current_photo_id, self.document.file.name
        reference = self.application.public_reference
        self.correct(files=self.replacements())
        self.application.refresh_from_db(); self.document.refresh_from_db()
        self.assertNotEqual(self.document.file.name, old_document)
        self.assertNotEqual(self.application.current_photo_id, old_photo)
        self.assertEqual(ProgramDocumentRevision.objects.get(document=self.document).file.name, old_document)
        self.assertEqual(self.application.public_reference, reference)
        self.assertTrue(old_files.items() <= self.file_hashes().items())
        batch = ProgramSourceState.objects.get(program=self.program).last_invalidation.batch
        self.assertEqual({r['model'] for r in batch.source_audits}, {'programs.programlog',
            'assistance.assistancelog', 'programs.photoverification', 'programs.programdocumentrevision'})
        self.assert_transition(2)

    def test_correction_without_replacement_retains_all_files(self):
        files = self.file_hashes()
        self.correct()
        self.assertEqual(files, self.file_hashes())
        self.assertFalse(ProgramDocumentRevision.objects.exists())
        self.assert_transition(2)

    def test_no_existing_case_does_not_create_one(self):
        self.case.delete()  # Fictional fixture variant, not a writer integration.
        self.review()
        self.assertFalse(AssistanceCase.objects.exists())
        self.assertFalse(AssistanceLog.objects.exists())
        self.assert_transition(2)

    def test_new_program_document_does_not_fabricate_prior_revision(self):
        requirement = ProgramRequirement.objects.create(program=self.program, label='Fictional new evidence',
            kind='document', is_required=True)
        self.correct(files=MultiValueDict({f'requirement_{requirement.pk}': [pdf()]}))
        self.assertEqual(ProgramDocument.objects.filter(application=self.application).count(), 2)
        self.assertFalse(ProgramDocumentRevision.objects.exists())
        self.assert_transition(2)

    def test_reused_membership_file_retained_after_replacement_and_rollback(self):
        from documents.models import DocumentType, MembershipDocumentRequirement, MembershipApplicationDocument, DocumentVerification
        from documents.services import file_digest
        # The guarded reference was prepared before disposable writer registration.
        kind = self.reusable_type
        requirement = MembershipDocumentRequirement.objects.create(document_type=kind)
        upload = pdf()
        source = MembershipApplicationDocument.objects.create(application=self.member.application,
            requirement=requirement, label='Fictional source', file=upload, content_type='application/pdf', size=upload.size)
        verified = DocumentVerification.objects.create(document=source, verified=True, member_version=self.member.version,
            file_digest=file_digest(source), reason='Fictional verified evidence', reviewer=self.officer,
            reviewer_label=self.officer.username)
        ProgramRequirement.objects.filter(pk=self.requirement.pk).update(reusable_document_type=kind)
        ProgramDocument.objects.filter(pk=self.document.pk).update(file=source.file.name,
            source_document=source, source_verification=verified, size=source.size, content_type=source.content_type)
        before = self.file_hashes()
        self.rollback(lambda: self.correct(files=self.replacements()), 'ewaf.source_invalidation._final_validate')
        self.correct(files=self.replacements())
        revision = ProgramDocumentRevision.objects.get(document=self.document)
        self.assertEqual(revision.source_document_id, source.pk)
        self.assertEqual(revision.source_verification_id, verified.pk)
        self.assertEqual(revision.file.name, source.file.name)
        self.assertTrue(before.items() <= self.file_hashes().items())
        self.assert_transition(2)

    def test_final_authorization_failure_preserves_files_and_audits(self):
        from .source_invalidation import _actor
        calls = []
        def revoke(user):
            calls.append(True)
            if len(calls) == 2:
                raise PermissionDenied('Fictional final authority failure')
            return _actor(user)
        before, files = self.snapshot(), self.file_hashes()
        with patch('ewaf.source_invalidation._actor', revoke), self.assertRaises(PermissionDenied):
            self.correct(files=self.replacements())
        self.assertEqual(before, self.snapshot())
        self.assertEqual(files, self.file_hashes())

    def test_closed_correction_deadline_and_final_status_rejected(self):
        Program.objects.filter(pk=self.program.pk).update(resubmission_closes_at=timezone.now() - timedelta(seconds=1))
        with self.assertRaises(ValidationError):
            self.correct()
        Program.objects.filter(pk=self.program.pk).update(resubmission_closes_at=None)
        ProgramApplication.objects.filter(pk=self.application.pk).update(status='CLOSED')
        with self.assertRaises(ValidationError):
            self.correct()
        self.assert_transition(1)

    def test_correction_stale_version_and_invalid_upload_rejected(self):
        with self.assertRaises(ValidationError):
            self.correct(version=999)
        with self.assertRaises(ValidationError):
            self.correct(files=MultiValueDict({'calendar_photo': [pdf()]}))
        self.assert_transition(1)

    def test_missing_document_revision_cleans_new_files(self):
        self.rollback(lambda: self.correct(files=self.replacements()),
                      'programs.workflow.retain_document_revision', lambda *a, **k: None)

    def test_duplicate_document_revision_cleans_new_files(self):
        original = workflow.retain_document_revision
        def duplicate(*a, **k):
            original(*a, **k)
            return original(*a, **k)
        self.rollback(lambda: self.correct(files=self.replacements()), 'programs.workflow.retain_document_revision', duplicate)

    def test_forged_document_revision_rejected(self):
        original = ProgramDocumentRevision.objects.create
        def forged(**kwargs):
            kwargs['size'] += 1
            return original(**kwargs)
        self.rollback(lambda: self.correct(files=self.replacements()),
                      'programs.workflow.ProgramDocumentRevision.objects.create', forged)

    def test_correction_native_and_generation_failures_clean_only_new_files(self):
        for target in ('programs.services.record_log', 'assistance.services.record_log',
                       'ewaf.generation_services._persist', 'ewaf.generation_services._cas_source',
                       'ewaf.source_invalidation._final_validate'):
            with self.subTest(target=target):
                self.rollback(lambda: self.correct(files=self.replacements()), target)

    def test_initial_pending_review_omission_rolls_back_replacement(self):
        original = PhotoVerification.objects.create
        def omit_pending(**kwargs):
            return None if kwargs['outcome'] == 'PENDING' else original(**kwargs)
        self.rollback(lambda: self.correct(files=self.replacements()),
                      'programs.workflow.PhotoVerification.objects.create', omit_pending)

    def test_current_photo_from_another_application_rejected(self):
        member = create_member('FICTIONAL-FOREIGN-PHOTO')
        other = application_fixture(self.program, member)
        ProgramApplication.objects.filter(pk=self.application.pk).update(current_photo=other.current_photo)
        with self.assertRaisesMessage(ValidationError, 'PHOTO_MISSING_OR_FOREIGN'):
            self.review()
        self.assert_transition(1)

    def test_historical_photo_tampering_during_mutation_rejected(self):
        original = programs.record_log
        def tamper(*a, **k):
            ApplicationPhoto.objects.filter(pk=self.application.current_photo_id).update(reason='Forged history')
            return original(*a, **k)
        self.rollback(self.review, 'programs.services.record_log', tamper)

    def test_storage_collision_does_not_overwrite_retained_photo(self):
        old_photo = self.application.current_photo
        before = self.file_hashes()
        field = ApplicationPhoto._meta.get_field('file')
        with patch.object(field, 'generate_filename', return_value=old_photo.file.name):
            self.correct(files=MultiValueDict({'calendar_photo': [image_upload()]}))
        self.application.refresh_from_db()
        self.assertNotEqual(old_photo.file.name, self.application.current_photo.file.name)
        self.assertTrue(before.items() <= self.file_hashes().items())

    def test_overwriting_storage_fails_closed(self):
        storage = ApplicationPhoto._meta.get_field('file').storage
        with patch.object(storage, '_allow_overwrite', True), self.assertRaisesMessage(ValidationError, 'NONOVERWRITING'):
            self.correct(files=self.replacements())
        self.assert_transition(1)

    def test_unregistered_workflow_and_split_locks_have_no_generation_queries(self):
        self.application.refresh_from_db()
        with patch.object(authority_services, '_session', None), CaptureQueriesContext(connection) as queries:
            workflow.review_photo(self.application.pk, user=self.officer, data={'version': self.application.version,
                'photo_id': self.application.current_photo_id, 'outcome': 'VERIFIED', 'reason': 'Fictional review', 'confirm': True})
        locks = [q['sql'] for q in queries if 'FOR UPDATE' in q['sql']]
        self.assertFalse(any('JOIN' in sql for sql in locks))
        self.assertFalse(any('ewaf_authoritygeneration' in q['sql'] for q in queries))
        self.assert_transition(1)

    def test_token_cannot_activate_and_outer_transaction_rejected(self):
        expected = self.expected()
        with patch.object(authority_services, '_session', None), self.assertRaises(PermissionDenied):
            self.review(expected=expected)
        with transaction.atomic(), self.assertRaisesMessage(ValidationError, 'top-level'):
            self.correct(expected=expected)

    def test_sql_orders_plain_application_member_and_photo(self):
        expected = self.expected()
        with CaptureQueriesContext(connection) as queries:
            self.correct(files=self.replacements(), expected=expected)
        locks = [q['sql'] for q in queries if 'FOR UPDATE' in q['sql']]
        tables = ('programs_programtermslock', 'ewaf_authoritygeneration', 'programs_program',
            'ewaf_programsourcestate', 'programs_programapplication', 'members_member',
            'assistance_eligibilitystatus', 'programs_programrequirement', 'documents_membershipapplicationdocument',
            'documents_documentverification', 'programs_programdocument', 'programs_applicationphoto',
            'programs_photoverification', 'assistance_assistancecase')
        positions = [next(i for i, sql in enumerate(locks) if f'FROM `{table}`' in sql) for table in tables]
        self.assertEqual(positions, sorted(set(positions)))
        self.assertTrue(all('JOIN' not in sql for sql in locks if 'FROM `programs_programapplication`' in sql))
        print('Gate 2D-2B actual first SQL lock order:', ' -> '.join(tables))

    def test_original_joined_query_sql_confirms_photo_is_in_locking_select(self):
        # Execute the exact prior helper query on fictional rows as baseline SQL
        # evidence. This is not a supported writer or a deadlock-free claim.
        with transaction.atomic(), CaptureQueriesContext(connection) as queries:
            ProgramApplication.objects.select_for_update().select_related('current_photo').get(pk=self.application.pk)
        sql = next(q['sql'] for q in queries if 'FOR UPDATE' in q['sql'])
        self.assertIn('JOIN `programs_applicationphoto`', sql)
        self.assertIn('FOR UPDATE', sql)
        print('Gate 2D-2B baseline SQL: Application LEFT OUTER JOIN ApplicationPhoto FOR UPDATE confirmed')


class PhotoConcurrencyTests(PhotoHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_photo()

    def race(self, operation, fail_first=False):
        entered, release, attempted = Event(), Event(), Event()
        original, boundary = generation._invalidate, generation.durable_services._boundary
        calls = []
        def hold(*args, **kwargs):
            calls.append(True)
            if len(calls) == 1:
                entered.set()
                if not release.wait(20):
                    raise RuntimeError('Fictional timeout')
                if fail_first:
                    raise ValidationError('Fictional first writer rollback')
            return original(*args, **kwargs)
        def signal():
            if entered.is_set():
                attempted.set()
            return boundary()
        def act():
            try:
                operation()
                return 'committed'
            except ValidationError as exc:
                return str(exc)
        with patch.object(generation, '_invalidate', hold), patch.object(generation.durable_services, '_boundary', signal):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(worker, act)
                try:
                    self.assertTrue(entered.wait(10))
                    second = pool.submit(worker, act)
                    self.assertTrue(attempted.wait(10))
                    with self.assertRaises(TimeoutError):
                        second.result(.25)
                finally:
                    release.set()
                a, b = first.result(30), second.result(30)
        self.assertNotEqual(a[0], b[0])
        if fail_first:
            self.assertIn('first writer rollback', a[1]); self.assertEqual(b[1], 'committed')
        else:
            self.assertEqual(a[1], 'committed'); self.assertIn('STALE_GENERATION', b[1])
        print('Gate 2D-2B MySQL writer connection IDs:', a[0], b[0], 'first rollback:', fail_first)
        self.assert_transition(2)

    def test_two_reviewers_have_one_generation_winner(self):
        expected = self.expected()
        self.race(lambda: self.review(expected=expected))

    def test_two_corrections_preserve_old_files_and_one_replacement(self):
        expected, files = self.expected(), self.file_hashes()
        self.race(lambda: self.correct(files=self.replacements(), expected=expected))
        self.assertTrue(files.items() <= self.file_hashes().items())
        self.assertEqual(len(self.file_hashes()), len(files) + 2)

    def test_failed_correction_allows_waiter_without_orphan_files(self):
        expected, files = self.expected(), self.file_hashes()
        self.race(lambda: self.correct(files=self.replacements(), expected=expected), fail_first=True)
        self.assertTrue(files.items() <= self.file_hashes().items())
        self.assertEqual(len(self.file_hashes()), len(files) + 2)

    def test_member_wait_does_not_lock_photo_before_member(self):
        # Hold M on one real connection. While the integrated writer waits for M,
        # that same blocker must still be able to acquire Photo. The old joined
        # A+Photo query at that position would create the M/Photo cycle.
        from members.models import Member
        held, attempted, release = Event(), Event(), Event()
        expected = self.expected()
        original = Member.objects.select_for_update
        def signal(*args, **kwargs):
            attempted.set()
            return original(*args, **kwargs)
        def blocker():
            with transaction.atomic():
                Member.objects.select_for_update().get(pk=self.member.pk)
                held.set()
                if not release.wait(20):
                    raise RuntimeError('Fictional timeout')
                ApplicationPhoto.objects.select_for_update(nowait=True).get(pk=self.application.current_photo_id)
            return 'photo acquired while holding member'
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(worker, blocker)
            self.assertTrue(held.wait(10))
            with patch.object(Member.objects, 'select_for_update', signal):
                second = pool.submit(worker, lambda: self.review(expected=expected).outcome)
                try:
                    self.assertTrue(attempted.wait(10))
                    with self.assertRaises(TimeoutError):
                        second.result(.25)
                finally:
                    release.set()
                a, b = first.result(30), second.result(30)
        self.assertNotEqual(a[0], b[0])
        self.assertEqual(a[1], 'photo acquired while holding member')
        self.assertEqual(b[1], 'VERIFIED')
        print('Gate 2D-2B Member/Photo lock probe connection IDs:', a[0], b[0])


class PhotoHistoryTests(PhotoHelpers, DurableHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_durable()
        self.register()

    def test_correction_preserves_prior_durable_graph_and_binding_digests(self):
        from .durable_services import inspect_development_history, require_operational_result
        request = self.request_run(); run = self.process(request)
        expected = self.token()
        with generation._fence(self.officer, [self.program.pk]) as (_, authority, _, states):
            state = states[self.program.pk]
            rb = generation._bind_request(request, run.snapshot, state=state, authority=authority,
                expected=expected, valid_until=timezone.now() + timedelta(minutes=2))
            run_binding = generation._bind_run(run, state=state, authority=authority)
        before = run.digest, run.snapshot, rb.digest, run_binding.digest
        # Fixture-only transition into an already supported correction state.
        ProgramApplication.objects.filter(pk=self.application.pk).update(status='ELIGIBILITY_REVIEW')
        self.correct(**{f'requirement_{self.relevance_requirement.pk}': 'Fictional corrected description'})
        run.refresh_from_db(); rb.refresh_from_db(); run_binding.refresh_from_db()
        rb.full_clean(); run_binding.full_clean()
        self.assertEqual(before, (run.digest, run.snapshot, rb.digest, run_binding.digest))
        self.assertFalse(inspect_development_history(run.pk, program_id=self.program.pk, user=self.officer)['operational_ready'])
        with self.assertRaises(ValidationError):
            require_operational_result()
        self.assert_transition(2)
