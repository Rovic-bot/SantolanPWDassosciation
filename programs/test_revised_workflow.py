from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from announcements.tests import image_upload
from announcements.models import Announcement
from announcements.program_publication import process_closed_program
from assistance.models import AssistanceCase
from assistance.services import review_eligibility, decide_assistance
from assistance.tests import review_data, decision_data
from documents.models import DocumentType, MembershipDocumentRequirement, MembershipApplicationDocument
from documents.services import verify_document
from members.tests import create_member
from membership.tests import pdf, grant
from .models import ProgramApplication, ProgramRequirement, PhotoVerification, ProgramCodeCounter, ReferenceCounter
from .services import verify_member, submit_application, save_program
from .workflow import review_photo, correct_application, allocate_reference
from .tests import create_program, program_data, verification
from .testsupport import private_media, close_non_ewaf_program


class RevisedWorkflowTests(TestCase):
    def setUp(self):
        self.media = private_media(self)
        self.admin = get_user_model().objects.create_superuser('revised_admin')
        self.member = create_member('REVISED-001')
        self.program = create_program(eligible_disability_types=[])

    def submit(self, files=None):
        self.program.refresh_from_db()
        verified = verify_member(self.program.pk, **verification(self.member, self.program))
        return submit_application(self.program.pk, grant=verified, data={'version': self.program.version},
            files=files if files is not None else MultiValueDict({'calendar_photo': [image_upload()]}))

    def photo(self, app, outcome='VERIFIED', **overrides):
        app.refresh_from_db()
        return review_photo(app.pk, user=self.admin, data={'version': app.version,
            'photo_id': app.current_photo_id, 'outcome': outcome, 'category': 'Evidence clarity',
            'reason': 'Manual review against the approved program instructions.', 'confirm': True, **overrides})

    def correct(self, app, files=None, **overrides):
        app.refresh_from_db()
        return correct_application(app.pk, user=self.admin, data={'version': app.version,
            'reason': 'Help Desk assisted correction.', **overrides}, files=files or MultiValueDict())

    def test_submission_is_not_photo_verification_eligibility_or_selection(self):
        app = self.submit()
        self.assertEqual(app.status, 'PENDING_PHOTO_VERIFICATION')
        self.assertRegex(app.public_reference, r'^SPWDA-\d{4}-PRG\d{6}-\d{10}$')
        self.assertEqual(app.photos.count(), 1)
        self.assertEqual(app.current_photo.reviews.get().outcome, 'PENDING')
        self.assertFalse(AssistanceCase.objects.exists())
        with self.assertRaisesMessage(ValidationError, 'Photo Verification'):
            review_eligibility(app.pk, user=self.admin, data=review_data(app))
        self.photo(app)
        app.refresh_from_db()
        self.assertEqual(app.status, 'PHOTO_VERIFIED')
        review_eligibility(app.pk, user=self.admin, data=review_data(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'ELIGIBLE')
        with self.assertRaisesMessage(ValidationError, 'period closes'):
            decide_assistance(app.pk, user=self.admin, data=decision_data(app))
        close_non_ewaf_program(self.program)
        decide_assistance(app.pk, user=self.admin, data=decision_data(app))
        app.refresh_from_db()
        self.assertEqual(app.status, 'SELECTED')

    def test_calendar_photo_required_and_invalid_files_rejected(self):
        for files in (MultiValueDict(), MultiValueDict({'calendar_photo': [pdf()]}),
                      MultiValueDict({'calendar_photo': [image_upload(), image_upload()]})):
            with self.assertRaises(ValidationError):
                self.submit(files)
        self.assertFalse(ProgramApplication.objects.exists())

    def test_reference_is_immutable_unique_and_retry_does_not_allocate_twice(self):
        app = self.submit()
        self.assertEqual(self.submit().pk, app.pk)
        self.assertEqual(ReferenceCounter.objects.get().value, 1)
        self.assertEqual(ProgramCodeCounter.objects.get().value, 1)
        app.public_reference = 'CHANGED'
        with self.assertRaises(ValidationError):
            app.save()
        second = create_program()
        with transaction.atomic():
            value = allocate_reference(second)
        self.assertNotEqual(value, ProgramApplication.objects.get().public_reference)

    def test_reference_and_photo_are_not_public_status_credentials(self):
        app = self.submit()
        for route in ('programs:status', 'programs:qr'):
            response = self.client.get(reverse(route, args=[app.status_token]))
            self.assertEqual(response.status_code, 410)
            self.assertNotIn(app.public_reference, response.content.decode())
            self.assertNotIn(self.member.full_name, response.content.decode())
        photo_url = reverse('programs:photo', args=[app.pk, app.current_photo_id])
        self.assertEqual(self.client.get(photo_url).status_code, 302)
        viewer = get_user_model().objects.create_user('viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'programs.view_program', 'programs.view_programapplication')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(photo_url).status_code, 403)
        self.client.force_login(self.admin)
        response = self.client.get(photo_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(b''.join(response.streaming_content))

    def test_photo_permission_reason_confirmation_stale_and_audit_rollback(self):
        app = self.submit()
        for values in ({'confirm': False}, {'reason': ''}, {'version': 99}, {'photo_id': 'invalid'}):
            with self.assertRaises(ValidationError):
                self.photo(app, **values)
        with patch('programs.services.record_log', side_effect=RuntimeError('audit')):
            with self.assertRaises(RuntimeError):
                self.photo(app)
        self.assertEqual(PhotoVerification.objects.count(), 1)
        app.refresh_from_db()
        self.assertEqual(app.status, 'PENDING_PHOTO_VERIFICATION')
        with self.assertRaises(PermissionDenied):
            review_photo(app.pk, user=get_user_model().objects.create_user('restricted', is_staff=True), data={})

    def test_needs_resubmission_preserves_reference_and_every_photo(self):
        app = self.submit()
        reference, original = app.public_reference, app.current_photo_id
        self.photo(app, 'NEEDS_RESUBMISSION')
        with self.assertRaises(ValidationError):
            self.correct(app)
        revised = self.correct(app, MultiValueDict({'calendar_photo': [image_upload()]}))
        self.assertEqual(revised.public_reference, reference)
        self.assertEqual(revised.status, 'PENDING_PHOTO_VERIFICATION')
        self.assertNotEqual(revised.current_photo_id, original)
        self.assertEqual(revised.photos.count(), 2)
        self.assertEqual(revised.photos.get(pk=original).reviews.first().outcome, 'NEEDS_RESUBMISSION')
        self.photo(revised)

    def test_rejection_reason_category_required_and_rejected_application_cannot_continue(self):
        app = self.submit()
        with self.assertRaises(ValidationError):
            self.photo(app, 'REJECTED', category='')
        self.photo(app, 'REJECTED')
        app.refresh_from_db()
        self.assertEqual(app.status, 'VERIFICATION_FAILED')
        with self.assertRaises(ValidationError):
            self.correct(app, MultiValueDict({'calendar_photo': [image_upload()]}))

    def test_missing_or_changed_photo_blocks_downstream_processing(self):
        app = self.submit()
        self.photo(app)
        self.member.version += 1
        self.member.save()
        with self.assertRaises(ValidationError):
            review_eligibility(app.pk, user=self.admin, data=review_data(app))
        self.photo(app)
        app.current_photo.file.storage.delete(app.current_photo.file.name)
        with self.assertRaises(ValidationError):
            review_eligibility(app.pk, user=self.admin, data=review_data(app))

    def test_correctable_information_remains_needs_information(self):
        requirement = ProgramRequirement.objects.create(program=self.program, label='Optional details', kind='text', is_required=False)
        app = self.submit()
        self.photo(app)
        review_eligibility(app.pk, user=self.admin, data=review_data(app, eligibility='review', other_requirements='review'))
        app.refresh_from_db()
        self.assertEqual(app.status, 'NEEDS_INFORMATION')
        self.correct(app, **{f'requirement_{requirement.pk}': 'Corrected information'})
        self.assertTrue(app.assistance_history.filter(action='evidence_invalidated').exists())

    def test_no_universal_disability_gate_and_program_policies_locked(self):
        self.member.disability_type = None
        self.member.save()
        self.submit()
        with self.assertRaises(ValidationError):
            save_program(pk=self.program.pk, user=self.admin, data=program_data(
                eligible_disability_types=[], selection_method='Changed after seeing applicants.'))

    def test_legacy_reference_search_survives_frozen_policy_upgrade(self):
        legacy = self.program
        legacy.policy_authorized_at = None
        legacy.photo_instructions = legacy.selection_method = ''
        legacy.save()
        app = ProgramApplication.objects.create(program=legacy, member=self.member, public_reference='SPA-RETAINED',
            legacy_status='under_review', status='NEEDS_INFORMATION')
        with self.assertRaises(ValidationError):
            save_program(pk=legacy.pk, user=self.admin, data=program_data(eligible_disability_types=[]))
        legacy.refresh_from_db()
        self.assertFalse(legacy.photo_instructions)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('programs:applications', args=[legacy.pk]), {'q': 'SPA-RETAINED'})
        self.assertContains(response, app.public_reference)
        app.refresh_from_db()
        self.assertIsNone(app.current_photo_id)

    def test_stage_eight_and_nine_legacy_mutations_disabled(self):
        from ewaf.services import generate_ranking, save_input, save_configuration
        app = self.submit()
        for callback in (lambda: generate_ranking(self.program.pk, user=self.admin, configuration=None, version=0),
                         lambda: save_input(app.pk, user=self.admin, data={}),
                         lambda: save_configuration(user=self.admin, data={}),
                         lambda: process_closed_program(self.program.pk)):
            with self.assertRaises(ValidationError):
                callback()
        self.assertFalse(Announcement.objects.filter(program=self.program).exists())

    def test_private_legacy_result_rows_never_reach_public_announcements(self):
        item = Announcement.objects.create(title='Legacy result', content='Private retained result', program=self.program,
            status='published', published_at=timezone.now())
        self.assertEqual(self.client.get(reverse('announcements:detail', args=[item.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('core:announcements')), 'Private retained result')

    def test_verified_internal_document_reused_then_revocation_blocks_selection(self):
        kind = DocumentType.objects.create(name='Synthetic proof')
        required = MembershipDocumentRequirement.objects.create(document_type=kind)
        upload = pdf()
        document = MembershipApplicationDocument.objects.create(application=self.member.application, requirement=required,
            label='Synthetic proof', file=upload, content_type='application/pdf', size=upload.size)
        requirement = ProgramRequirement.objects.create(program=self.program, label='Reusable proof', kind='document', reusable_document_type=kind)
        values = dict(user=self.admin, member_version=self.member.version, expires_on=None, reason='Manual verification.')
        verify_document(document.pk, verified=True, **values)
        app = self.submit()
        self.assertEqual(app.documents.get().source_document, document)
        self.photo(app)
        review_eligibility(app.pk, user=self.admin, data=review_data(app, **{f'check_{requirement.pk}': 'pass'}))
        close_non_ewaf_program(self.program)
        verify_document(document.pk, verified=False, **values)
        with self.assertRaisesMessage(ValidationError, 'renewed verification'):
            decide_assistance(app.pk, user=self.admin, data=decision_data(app))
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('members:detail', args=[self.member.pk])).status_code, 200)

    def test_photo_and_correction_routes_enforce_csrf_and_render(self):
        app = self.submit()
        self.client.force_login(self.admin)
        for route, args in [('programs:photo_queue', []), ('programs:photo_review', [app.pk]), ('programs:correction', [app.pk])]:
            self.assertEqual(self.client.get(reverse(route, args=args)).status_code, 200)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(client.post(reverse('programs:photo_review', args=[app.pk]), {}).status_code, 403)
        self.assertEqual(client.post(reverse('programs:correction', args=[app.pk]), {}).status_code, 403)

    def test_help_desk_document_replacement_retains_auditable_private_original(self):
        requirement = ProgramRequirement.objects.create(program=self.program, label='Required proof', kind='document')
        app = self.submit(MultiValueDict({'calendar_photo': [image_upload()], f'requirement_{requirement.pk}': [pdf()]}))
        original = app.documents.get().file.name
        self.correct(app, MultiValueDict({f'requirement_{requirement.pk}': [pdf()]}))
        document = app.documents.get()
        revision = document.revisions.get()
        self.assertEqual(revision.file.name, original)
        self.assertNotEqual(document.file.name, original)
        self.assertEqual(revision.actor, self.admin)
        route = reverse('programs:document_revision', args=[self.program.pk, app.pk, document.pk, revision.pk])
        self.assertEqual(self.client.get(route).status_code, 302)
        self.client.force_login(self.admin)
        response = self.client.get(route)
        self.assertEqual(response.status_code, 200)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(b''.join(response.streaming_content))
