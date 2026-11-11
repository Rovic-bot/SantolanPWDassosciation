from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connections, IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from members.tests import create_member
from members.models import DisabilityType
from membership.tests import grant as grant_permissions, pdf
from announcements.tests import image_upload
from .testsupport import private_media
from .forms import ProgramForm, ApplicationForm
from .models import Program, ProgramRequirement, ProgramApplication, ProgramDocument, ProgramLog, VerificationWindow
from .services import (save_program, save_requirement, change_publication, verify_member, submit_application,
                       change_application, reserve_verification, grant_valid, VERIFICATION_FAILED)


def program_data(**overrides):
    now = timezone.now().replace(second=0, microsecond=0)
    return {'name': 'Synthetic assistance program', 'description': 'Test program details.', 'assistance_type': 'Food & Nutrition',
            'registration_opens_at': now - timedelta(days=1), 'registration_closes_at': now + timedelta(days=1),
            'starts_at': None, 'ends_at': None, 'slots': 1, 'budget': None, 'amount': None,
            'ewaf_applicable': False, 'selection_method': 'Synthetic authorized external committee decision.', 'photo_instructions': 'Synthetic policy: photo holding this month’s calendar.', 'resubmission_closes_at': None,
            'benefit': '', 'requirements': 'Read all instructions.', 'eligible_disability_types': [DisabilityType.objects.get_or_create(name='Visual Disability')[0].pk], 'version': 0, 'notes': 'Reviewed correction.', **overrides}


def create_program(**overrides):
    data = program_data(**overrides)
    data.pop('notes')
    types = data.pop('eligible_disability_types')
    item = Program.objects.create(**data, status='published', published_at=timezone.now(), policy_authorized_at=timezone.now())
    item.eligible_disability_types.set(types)
    return item


def verification(member, program):
    return {'version': program.version, 'control_number': member.control_number, 'full_name': member.full_name,
            'birthdate': date.fromisoformat(member.birthdate) if isinstance(member.birthdate, str) else member.birthdate,
            'contact_number': member.contact_number}


class ProgramTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.admin = get_user_model().objects.create_superuser('program_admin', password='test-only-password')
        self.viewer = get_user_model().objects.create_user('program_viewer', is_staff=True)
        grant_permissions(self.viewer, 'accounts.access_dashboard', 'programs.view_program')
        self.member = create_member('PROGRAM-001')
        self.member.refresh_from_db()
        self.program = create_program()
        self.verify_url = reverse('programs:verify', args=[self.program.pk])
        self.apply_url = reverse('programs:apply', args=[self.program.pk])
        self.detail = reverse('programs:detail', args=[self.program.pk])
        self.manage = reverse('programs:manage_detail', args=[self.program.pk])

    def verified(self, member=None):
        self.program.refresh_from_db()
        return verify_member(self.program.pk, **verification(member or self.member, self.program))

    def submit(self, **kwargs):
        files = kwargs.pop('files', MultiValueDict())
        files.setlist('calendar_photo', [image_upload()])
        return submit_application(self.program.pk, grant=kwargs.pop('grant', None) or self.verified(),
                                  data=kwargs.pop('data', {'version': self.program.version}),
                                  files=files, **kwargs)

    def requirement(self, **kwargs):
        return ProgramRequirement.objects.create(program=self.program, label='Supporting document', kind='document', **kwargs)

    def test_draft_creation_optional_fields_and_forged_state(self):
        item = save_program(user=self.admin, data=program_data(status='published', created_by=self.viewer.pk))
        self.assertEqual(item.status, 'draft')
        self.assertIsNone(item.starts_at)
        self.assertIsNone(item.budget)
        self.assertEqual(item.created_by, self.admin)
        self.assertTrue(item.history.filter(action='created').exists())
        self.assertEqual(self.client.get(reverse('programs:detail', args=[item.pk])).status_code, 404)

    def test_program_forms_exclude_removed_financial_fields_and_keep_instructions(self):
        for instance in (Program(), self.program):
            with self.subTest(adding=instance._state.adding):
                form = ProgramForm(instance=instance)
                self.assertNotIn('budget', form.fields)
                self.assertIn('slots', form.fields)
                self.assertNotIn('amount', form.fields)
                self.assertNotIn('benefit', form.fields)
                self.assertIn('requirements', form.fields)
                self.assertIn('eligible_disability_types', form.fields)

    def test_create_and_edit_pages_do_not_render_budget_input(self):
        self.client.force_login(self.admin)
        for url in (reverse('programs:create'), reverse('programs:edit', args=[self.program.pk])):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'name="budget"')
                self.assertNotContains(response, 'id_budget')
                self.assertContains(response, 'name="slots"')
                self.assertNotContains(response, 'name="amount"')
                self.assertNotContains(response, 'name="benefit"')

    def test_create_ignores_forged_budget_post(self):
        self.client.force_login(self.admin)
        for forged in ('12345.67', '-1', 'not-a-number', ''):
            with self.subTest(forged=forged):
                data = {key: value for key, value in program_data(budget=forged).items() if value is not None}
                before = set(Program.objects.values_list('pk', flat=True))
                response = self.client.post(reverse('programs:create'), data)
                self.assertEqual(response.status_code, 302)
                item = Program.objects.exclude(pk__in=before).get()
                self.assertIsNone(item.budget)
                self.assertEqual(item.status, 'draft')
                self.assertNotIn('budget', item.history.get(action='created').changes)

    def test_edit_without_budget_preserves_historical_values(self):
        for historical in (None, Decimal('0.00'), Decimal('12345.67'), Decimal('999999999999.99')):
            with self.subTest(historical=historical):
                item = create_program(budget=historical)
                # Initial draft configuration remains editable under G06-B1B.1.
                Program.objects.filter(pk=item.pk).update(status='draft', published_at=None)
                data = program_data(version=item.version, name='Synthetic revised program', slots=4, amount='2500.50')
                data.pop('budget')
                save_program(user=self.admin, pk=item.pk, data=data)
                item.refresh_from_db()
                self.assertEqual(item.budget, historical)
                self.assertEqual(item.name, 'Synthetic revised program')
                self.assertEqual(item.slots, 4)
                self.assertIsNone(item.amount)
                self.assertNotIn('budget', item.history.get(action='updated').changes)

    def test_edit_ignores_forged_budget_post_and_preserves_history(self):
        self.client.force_login(self.admin)
        self.program.budget = Decimal('12345.67')
        self.program.save(update_fields=['budget'])
        old_log = ProgramLog.objects.create(program=self.program, action='updated', notes='Synthetic historical budget.',
            changes={'budget': {'before': '10000.00', 'after': '12345.67'}})
        original_log = ProgramLog.objects.filter(pk=old_log.pk).values().get()
        for forged in ('98765.43', '0', '', '-1', 'not-a-number', '99999999999999999999'):
            with self.subTest(forged=forged):
                data = {key: value for key, value in program_data(budget=forged, version=self.program.version).items()
                        if value is not None}
                # This test changes only a forged budget field. Crossing a wall-
                # clock minute must not accidentally propose new protected terms.
                data.update(registration_opens_at=self.program.registration_opens_at,
                            registration_closes_at=self.program.registration_closes_at)
                response = self.client.post(reverse('programs:edit', args=[self.program.pk]), data)
                self.assertEqual(response.status_code, 302)
                self.program.refresh_from_db()
                self.assertEqual(self.program.budget, Decimal('12345.67'))
                self.assertEqual(ProgramLog.objects.filter(pk=old_log.pk).values().get(), original_log)
                for log in self.program.history.exclude(pk=old_log.pk):
                    self.assertNotIn('budget', log.changes)

    def test_forged_budget_cannot_fill_previously_null_budget(self):
        save_program(user=self.admin, pk=self.program.pk, data=program_data(budget='12345.67'))
        self.program.refresh_from_db()
        self.assertIsNone(self.program.budget)

    def test_budget_removal_preserves_existing_application_and_requirements(self):
        self.program.budget = Decimal('12345.67')
        self.program.save(update_fields=['budget'])
        self.requirement(is_required=False)
        application = self.submit()
        original_application = ProgramApplication.objects.filter(pk=application.pk).values().get()
        original_requirements = list(self.program.configured_requirements.values())
        original_history = list(self.program.history.values())
        self.program.refresh_from_db()
        data = program_data(version=self.program.version)
        data.pop('budget')
        save_program(user=self.admin, pk=self.program.pk, data=data)
        self.program.refresh_from_db()
        self.assertEqual(self.program.budget, Decimal('12345.67'))
        self.assertEqual(ProgramApplication.objects.filter(pk=application.pk).values().get(), original_application)
        self.assertEqual(list(self.program.configured_requirements.values()), original_requirements)
        for log in original_history:
            self.assertEqual(ProgramLog.objects.filter(pk=log['id']).values().get(), log)

    def test_publication_lifecycle_retains_applications(self):
        application = self.submit()
        for action, code in [('cancelled', 200), ('draft', 404), ('published', 200), ('archived', 404)]:
            self.program = change_publication(self.program.pk, user=self.admin, version=self.program.version,
                                              action=action, notes='Reviewed publication.')
            self.assertEqual(self.client.get(self.detail).status_code, code)
            self.assertTrue(ProgramApplication.objects.filter(pk=application.pk).exists())
            if action != 'published':
                with self.assertRaises(ValidationError):
                    self.verified()
        self.assertEqual(ProgramLog.objects.filter(application__isnull=True).count(), 4)

    def test_schedule_and_numeric_validation(self):
        for changes in [{'registration_closes_at': self.program.registration_opens_at}, {'slots': 0},
                        {'starts_at': timezone.now(), 'ends_at': timezone.now()-timedelta(days=1)},
                        {'ends_at': self.program.registration_closes_at - timedelta(minutes=1)}]:
            with self.subTest(changes=changes):
                self.assertFalse(ProgramForm(program_data(**changes)).is_valid())
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Program.objects.filter(pk=self.program.pk).update(slots=0)

    def test_disability_mismatch_stops_verification_and_direct_submission(self):
        old_grant = self.verified()
        self.client.post(self.verify_url, verification(self.member, self.program))
        other = DisabilityType.objects.create(name='Synthetic unmatched type')
        self.program.eligible_disability_types.set([other])
        response = self.client.post(self.verify_url, verification(self.member, self.program))
        self.assertContains(response, 'You cannot proceed with this application because')
        self.assertContains(response, 'target disability types')
        self.assertNotIn('program_verification', self.client.session)
        self.assertRedirects(self.client.post(self.apply_url, {'version': self.program.version}), self.verify_url)
        with self.assertRaisesMessage(ValidationError, 'You cannot proceed with this application because'):
            self.submit(grant=old_grant)
        self.assertFalse(ProgramApplication.objects.exists())
        self.assertFalse(ProgramLog.objects.filter(action='submitted').exists())

    def test_disability_mismatch_feedback_requires_verified_identity(self):
        other = DisabilityType.objects.create(name='Synthetic unmatched type')
        self.program.eligible_disability_types.set([other])
        data = {**verification(self.member, self.program), 'full_name': 'Incorrect name'}
        response = self.client.post(self.verify_url, data)
        self.assertContains(response, 'Unable to verify membership')
        self.assertNotContains(response, 'target disability types')

    def test_legacy_screening_keeps_unclear_records_separate_from_mismatches(self):
        from .services import require_disability
        for changes in ('missing', 'inactive'):
            with self.subTest(changes=changes):
                member = create_member('SCREENING-' + changes)
                if changes == 'missing':
                    member.disability_type = None
                else:
                    member.disability_type = DisabilityType.objects.create(name='Synthetic historical type', is_active=False)
                with self.assertRaises(ValidationError) as error:
                    require_disability(self.program, member)
                self.assertEqual(error.exception.code, 'needs_information')
                self.assertIn('need clarification', error.exception.message)

    def test_generic_mismatch_all_fields_and_inactive_members(self):
        for field, value in [('control_number', 'UNKNOWN'), ('full_name', 'Wrong Name'), ('birthdate', date(2000, 1, 1)),
                             ('contact_number', '09999999999')]:
            data = {**verification(self.member, self.program), field: value}
            with self.subTest(field=field), self.assertRaisesMessage(ValidationError, VERIFICATION_FAILED):
                verify_member(self.program.pk, **data)
        self.member.is_active = False
        self.member.save()
        with self.assertRaisesMessage(ValidationError, VERIFICATION_FAILED):
            self.verified()
        self.member.archived_at = timezone.now()
        self.member.save()
        with self.assertRaisesMessage(ValidationError, VERIFICATION_FAILED):
            self.verified()

    def test_conservative_normalization_and_mysql_collation(self):
        data = {**verification(self.member, self.program), 'full_name': '  SAMPLE   applicant  ', 'contact_number': '+63 (917) 000-0000'}
        self.assertEqual(verify_member(self.program.pk, **data)['member'], self.member.pk)
        for changes in [{'full_name': 'Sámple Applicant'}, {'contact_number': 'phone09170000000'}]:
            with self.assertRaisesMessage(ValidationError, VERIFICATION_FAILED):
                verify_member(self.program.pk, **{**data, **changes})
        self.member.control_number = 'PÁ-001'
        self.member.save()
        with self.assertRaisesMessage(ValidationError, VERIFICATION_FAILED):
            verify_member(self.program.pk, **{**verification(self.member, self.program), 'control_number': 'PA-001'})

    def test_registration_time_boundaries(self):
        for moment, available in [(self.program.registration_opens_at, True), (self.program.registration_closes_at, False)]:
            # Publication must precede the artificially frozen opening time.
            Program.objects.filter(pk=self.program.pk).update(published_at=self.program.registration_opens_at-timedelta(days=1))
            with patch('django.utils.timezone.now', return_value=moment):
                if available:
                    self.assertTrue(self.verified())
                else:
                    with self.assertRaises(ValidationError):
                        self.verified()

    def test_grant_expiry_scope_and_stale_program(self):
        verified = self.verified()
        for invalid in [None, {}, {**verified, 'expires': 0}, {**verified, 'program': 'other'}, {**verified, 'version': 99}]:
            with self.subTest(grant=invalid), self.assertRaises(ValidationError):
                submit_application(self.program.pk, grant=invalid, data={'version': 0}, files=MultiValueDict())
        self.assertFalse(grant_valid(verified, create_program()))
        # A no-op save now preserves the historical program version. Use an
        # authorized lifecycle change to exercise stale verification instead.
        withdrawn = change_publication(self.program.pk, user=self.admin, version=self.program.version,
                                       action='draft', notes='Synthetic withdrawal.')
        restored = change_publication(self.program.pk, user=self.admin, version=withdrawn.version,
                                      action='published', notes='Synthetic restoration.')
        self.assertTrue(restored.registration_available)
        self.assertFalse(grant_valid(verified, restored))
        with self.assertRaises(ValidationError):
            self.submit(grant=verified)

    def test_member_change_or_deactivation_after_verification_blocks_submission(self):
        verified = self.verified()
        self.member.version += 1
        self.member.save()
        with self.assertRaises(ValidationError):
            self.submit(grant=verified)
        verified = self.verified()
        self.member.is_active = False
        self.member.save()
        with self.assertRaises(ValidationError):
            self.submit(grant=verified)

    def test_slots_do_not_limit_applications_and_duplicates_are_idempotent(self):
        first = self.submit()
        second = self.submit(grant=self.verified(create_member('PROGRAM-002')))
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(self.submit().pk, first.pk)
        self.assertEqual(ProgramApplication.objects.count(), 2)
        self.assertEqual(ProgramLog.objects.filter(action='submitted').count(), 2)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            ProgramApplication.objects.create(program=self.program, member=self.member, public_reference='SPWDA-DUPLICATE-TEST')

    def test_required_documents_questions_acknowledgements_and_snapshots(self):
        document = self.requirement()
        question = ProgramRequirement.objects.create(program=self.program, kind='text', label='Explain your request')
        acknowledgement = ProgramRequirement.objects.create(program=self.program, kind='acknowledgement', label='I have read the requirements')
        data = {'version': 0, f'requirement_{question.pk}': 'A private answer', f'requirement_{acknowledgement.pk}': 'on'}
        with self.assertRaises(ValidationError):
            self.submit(data=data)
        result = self.submit(data=data, files=MultiValueDict({f'requirement_{document.pk}': [pdf()]}))
        self.assertEqual(result.answers[str(question.pk)], 'A private answer')
        self.assertIs(result.answers[str(acknowledgement.pk)], True)
        self.assertEqual(result.documents.get().label, 'Supporting document')
        self.assertEqual(len(result.requirements_snapshot), 3)
        document.label = 'Replacement label'
        document.is_active = False
        document.save()
        self.program.requirements = 'New instructions'
        self.program.save()
        result.refresh_from_db()
        self.assertEqual(result.requirements_snapshot[0]['label'], 'Supporting document')
        self.assertEqual(result.program_snapshot['requirements'], 'Read all instructions.')

    def test_optional_inactive_requirements_and_no_requirements(self):
        self.requirement(is_required=False)
        self.requirement(is_active=False)
        item = self.submit()
        self.assertEqual(len(item.requirements_snapshot), 1)
        self.assertFalse(item.documents.exists())

    def test_upload_rejects_wrong_type_signature_size_extra_and_duplicates(self):
        doc = self.requirement()
        field = f'requirement_{doc.pk}'
        invalid_uploads = [SimpleUploadedFile('bad.exe', b'executable', 'application/octet-stream'),
                           SimpleUploadedFile('bad.pdf', b'not pdf', 'application/pdf'),
                           SimpleUploadedFile('empty.pdf', b'', 'application/pdf')]
        for upload in invalid_uploads:
            with self.subTest(upload=upload.name), self.assertRaises(ValidationError):
                self.submit(files=MultiValueDict({field: [upload]}))
        for files in [MultiValueDict({field: [pdf(), pdf()]}), MultiValueDict({field: [pdf()], 'extra': [pdf()]})]:
            with self.assertRaises(ValidationError):
                self.submit(files=files)
        with override_settings(MEMBERSHIP_FILE_MAX_BYTES=10), self.assertRaises(ValidationError):
            self.submit(files=MultiValueDict({field: [pdf()]}))
        with override_settings(MEMBERSHIP_TOTAL_MAX_BYTES=10), self.assertRaises(ValidationError):
            self.submit(files=MultiValueDict({field: [pdf()]}))
        self.assertFalse(ProgramApplication.objects.exists())

    def test_failed_audit_rolls_back_application_and_removes_files(self):
        doc = self.requirement()
        with patch('programs.services.record_log', side_effect=RuntimeError('audit unavailable')), self.assertRaises(RuntimeError):
            self.submit(files=MultiValueDict({f'requirement_{doc.pk}': [pdf()]}))
        self.assertFalse(ProgramApplication.objects.exists())
        self.assertFalse(ProgramDocument.objects.exists())
        self.assertFalse([p for p in Path(self.media.name).rglob('*') if p.is_file()])

    def test_requirement_configuration_version_limits_and_rollback(self):
        Program.objects.filter(pk=self.program.pk).update(status='draft', published_at=None)
        data = {'label': 'Test proof', 'kind': 'document', 'is_active': True, 'is_required': True, 'position': 0,
                'version': self.program.version, 'notes': 'Configure proof.'}
        item = save_requirement(self.program.pk, user=self.admin, data=data)
        self.program.refresh_from_db()
        self.assertEqual(self.program.version, 1)
        with self.assertRaises(ValidationError):
            save_requirement(self.program.pk, user=self.admin, data=data)
        with override_settings(DATA_UPLOAD_MAX_NUMBER_FILES=1), self.assertRaises(ValidationError):
            save_requirement(self.program.pk, user=self.admin, data={**data, 'version': 1})
        with patch('programs.services.record_log', side_effect=RuntimeError('audit unavailable')), self.assertRaises(RuntimeError):
            save_requirement(self.program.pk, user=self.admin, data={**data, 'version': 1, 'label': 'Changed'}, requirement_id=item.pk)
        item.refresh_from_db()
        self.assertEqual(item.label, 'Test proof')

    def test_requirement_change_is_frozen_and_existing_grant_remains_valid(self):
        verified = self.verified()
        with self.assertRaises(ValidationError):
            save_requirement(self.program.pk, user=self.admin, data={'version': 0, 'label': 'New question', 'kind': 'text',
                'is_active': True, 'is_required': True, 'position': 0, 'notes': 'New requirement.'})
        self.assertFalse(self.program.configured_requirements.exists())
        self.assertIsNotNone(self.submit(grant=verified))

    def test_application_status_history_stale_and_cancelled_restoration(self):
        item = self.submit()
        with self.assertRaises(ValidationError):
            change_application(item.pk, user=self.admin, version=item.version, status='ELIGIBLE', notes='Forged shortcut.')
        closed = change_application(item.pk, user=self.admin, version=item.version, status='CLOSED', notes='Authorized closure.')
        self.assertEqual(closed.status, 'CLOSED')
        self.assertEqual(closed.history.count(), 2)
        with self.assertRaises(ValidationError):
            change_application(item.pk, user=self.admin, version=item.version, status='PHOTO_VERIFIED', notes='Forged restoration.')

    def test_program_cancelled_blocks_review_and_status_changes_require_reasons(self):
        item = self.submit()
        change_publication(self.program.pk, user=self.admin, version=0, action='cancelled', notes='Closed.')
        with self.assertRaises(ValidationError):
            change_application(item.pk, user=self.admin, version=0, status='under_review', notes='Attempt review.')
        with self.assertRaises(ValidationError):
            change_application(item.pk, user=self.admin, version=0, status='CLOSED', notes=' ')

    def test_mutations_require_permissions_even_when_called_directly(self):
        item = self.submit()
        for user in [AnonymousUser(), self.viewer]:
            for action in [lambda: save_program(user=user, data=program_data()),
                           lambda: change_publication(self.program.pk, user=user, version=0, action='draft', notes='Test'),
                           lambda: save_requirement(self.program.pk, user=user, data={}),
                           lambda: change_application(item.pk, user=user, version=0, status='under_review', notes='Test')]:
                with self.assertRaises(PermissionDenied):
                    action()

    def test_live_edit_and_configuration_need_publish_permission(self):
        grant_permissions(self.viewer, 'programs.change_program', 'programs.configure_program')
        self.client.force_login(self.viewer)
        for route in ['programs:edit', 'programs:requirement_add']:
            self.assertEqual(self.client.get(reverse(route, args=[self.program.pk])).status_code, 403)
        with self.assertRaises(PermissionDenied):
            save_program(user=self.viewer, data=program_data(), pk=self.program.pk)
        with self.assertRaises(PermissionDenied):
            save_requirement(self.program.pk, user=self.viewer, data={})

    def test_private_routes_and_separate_application_document_history_permissions(self):
        doc = self.requirement()
        item = self.submit(files=MultiValueDict({f'requirement_{doc.pk}': [pdf()]}))
        detail = reverse('programs:application_detail', args=[self.program.pk, item.pk])
        download = reverse('programs:document', args=[self.program.pk, item.pk, item.documents.get().pk])
        for url in [self.manage, detail, download, reverse('programs:applications', args=[self.program.pk])]:
            self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.manage).status_code, 200)
        self.assertEqual(self.client.get(detail).status_code, 403)
        grant_permissions(self.viewer, 'programs.view_programapplication')
        response = self.client.get(detail)
        self.assertContains(response, 'Document access requires a separate permission.')
        self.assertNotContains(response, 'Verified member submitted a program application.')
        self.assertEqual(self.client.get(download).status_code, 403)
        grant_permissions(self.viewer, 'programs.view_programdocument')
        response = self.client.get(download)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        b''.join(response.streaming_content)
        self.assertEqual(item.history.filter(action='document_downloaded').count(), 1)

    def test_document_scope_missing_file_and_protected_history(self):
        req = self.requirement()
        item = self.submit(files=MultiValueDict({f'requirement_{req.pk}': [pdf()]}))
        doc = item.documents.get()
        self.client.force_login(self.admin)
        other = create_program()
        self.assertEqual(self.client.get(reverse('programs:document', args=[other.pk, item.pk, doc.pk])).status_code, 404)
        doc.file.storage.delete(doc.file.name)
        self.assertEqual(self.client.get(reverse('programs:document', args=[self.program.pk, item.pk, doc.pk])).status_code, 404)
        with self.assertRaises(ProtectedError):
            self.program.delete()
        with self.assertRaises(ProtectedError):
            self.member.delete()
        with self.assertRaises(ProtectedError):
            item.delete()

    def test_two_step_flow_session_receipt_privacy_and_retry(self):
        self.assertRedirects(self.client.get(self.apply_url), self.verify_url)
        response = self.client.post(self.verify_url, verification(self.member, self.program))
        self.assertRedirects(response, self.apply_url)
        self.assertNotContains(self.client.get(self.apply_url), self.member.full_name)
        response = self.client.post(self.apply_url, {'version': 0, 'calendar_photo': image_upload()})
        receipt = reverse('programs:submitted', args=[self.program.pk])
        self.assertRedirects(response, receipt, fetch_redirect_response=False)
        self.assertNotContains(self.client.get(receipt, follow=True), self.member.control_number)
        self.assertNotContains(self.client.get(receipt, follow=True), self.member.full_name)
        self.assertRedirects(Client().get(receipt), self.detail)
        self.client.post(self.verify_url, verification(self.member, self.program))
        self.assertRedirects(self.client.get(self.apply_url), receipt, fetch_redirect_response=False)
        self.assertEqual(ProgramApplication.objects.count(), 1)

    def test_failed_reverification_clears_previous_grant(self):
        self.client.post(self.verify_url, verification(self.member, self.program))
        self.client.post(self.verify_url, {**verification(self.member, self.program), 'full_name': 'wrong'})
        self.assertNotIn('program_verification', self.client.session)
        self.assertRedirects(self.client.get(self.apply_url), self.verify_url)

    def test_public_html_privacy_xss_budget_and_no_generic_admin(self):
        self.program.description = '<script>alert(1)</script>'
        self.program.budget = 9876543
        self.program.save()
        self.submit()
        response = self.client.get(self.detail)
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, self.member.full_name)
        self.assertNotContains(response, '9876543')
        self.assertEqual(self.client.get('/media/programs/test.pdf').status_code, 404)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get('/admin/programs/program/').status_code, 404)

    def test_csrf_and_get_cannot_mutate(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        self.assertEqual(strict.post(self.manage, {'action': 'draft'}).status_code, 403)
        self.assertEqual(strict.post(self.verify_url, verification(self.member, self.program)).status_code, 403)
        self.client.force_login(self.admin)
        self.client.get(self.manage, {'action': 'draft'})
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'published')

    @override_settings(PROGRAM_VERIFICATION_MEMBER_LIMIT=2, PROGRAM_VERIFICATION_ADDRESS_LIMIT=4)
    def test_rate_limits_hmac_expiry_and_cleanup(self):
        for _ in range(2):
            self.assertTrue(reserve_verification('PROGRAM-001', '127.0.0.1'))
        self.assertFalse(reserve_verification('PROGRAM-001', '127.0.0.2'))
        self.assertTrue(all(len(key) == 64 and 'PROGRAM' not in key for key in VerificationWindow.objects.values_list('key', flat=True)))
        VerificationWindow.objects.update(started_at=timezone.now()-timedelta(hours=2))
        self.assertTrue(reserve_verification('NEW', '127.0.0.3'))
        call_command('purge_program_verification_windows', verbosity=0)
        self.assertEqual(VerificationWindow.objects.count(), 2)
        self.assertEqual(self.program.history.count(), 0)

    @override_settings(PROGRAM_VERIFICATION_MEMBER_LIMIT=1)
    def test_rate_limited_response(self):
        data = verification(self.member, self.program)
        self.client.post(self.verify_url, data)
        response = self.client.post(self.verify_url, data)
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)

    def test_search_filters_pagination_and_member_history(self):
        application = self.submit()
        self.client.force_login(self.admin)
        url = reverse('programs:applications', args=[self.program.pk])
        self.assertContains(self.client.get(url, {'q': 'PROGRAM-001'}), self.member.full_name)
        self.assertNotContains(self.client.get(url, {'status': 'CLOSED'}), self.member.full_name)
        self.assertContains(self.client.get(reverse('members:detail', args=[self.member.pk])), reverse('programs:application_detail', args=[self.program.pk, application.pk]))
        for index in range(21):
            create_program(name=f'Additional {index}')
        response = self.client.get(reverse('programs:manage_list'))
        self.assertEqual(response.context['page_obj'].paginator.num_pages, 2)
        self.assertEqual(self.client.get(reverse('programs:list')).context['page_obj'].paginator.num_pages, 4)

    def test_all_admin_pages_render_and_future_publication_hidden(self):
        self.client.force_login(self.admin)
        item = self.submit()
        req = self.requirement(is_required=False)
        for name, args in [('programs:create', []), ('programs:edit', [self.program.pk]),
                           ('programs:requirement_add', [self.program.pk]), ('programs:requirement_edit', [self.program.pk, req.pk]),
                           ('programs:application_detail', [self.program.pk, item.pk])]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200)
        self.program.published_at = timezone.now() + timedelta(days=1)
        self.program.save()
        self.assertEqual(self.client.get(self.detail).status_code, 404)

    def test_status_audit_failure_rolls_back(self):
        item = self.submit()
        with patch('programs.services.record_log', side_effect=RuntimeError('audit failed')), self.assertRaises(RuntimeError):
            change_application(item.pk, user=self.admin, version=0, status='CLOSED', notes='Cancel.')
        item.refresh_from_db()
        self.assertEqual(item.status, 'PENDING_PHOTO_VERIFICATION')


class ProgramConcurrencyTests(TransactionTestCase):
    def setUp(self):
        private_media(self)
        self.program = create_program()
        self.member = create_member('CONCURRENT-PROGRAM')
        self.member.refresh_from_db()

    def test_simultaneous_submissions_create_one_application_and_audit(self):
        verified = verify_member(self.program.pk, **verification(self.member, self.program))
        barrier = Barrier(2)
        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return submit_application(self.program.pk, grant=verified, data={'version': 0}, files=MultiValueDict({'calendar_photo': [image_upload()]})).pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
        self.assertEqual(results[0], results[1])
        self.assertEqual(ProgramApplication.objects.count(), 1)
        self.assertEqual(ProgramLog.objects.filter(action='submitted').count(), 1)

    def test_requirement_edit_and_submission_cannot_mix_snapshots(self):
        admin = get_user_model().objects.create_superuser('concurrency_admin')
        verified = verify_member(self.program.pk, **verification(self.member, self.program))
        barrier = Barrier(2)
        def worker(edit):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                if edit:
                    try:
                        return save_requirement(self.program.pk, user=admin, data={'version': 0, 'label': 'New required proof',
                            'kind': 'document', 'is_active': True, 'is_required': True, 'position': 0, 'notes': 'Configure proof.'})
                    except ValidationError:
                        return None
                try:
                    return submit_application(self.program.pk, grant=verified, data={'version': 0}, files=MultiValueDict({'calendar_photo': [image_upload()]}))
                except ValidationError:
                    return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, edit) for edit in (True, False)]
            results = [future.result(timeout=30) for future in futures]
        self.assertEqual(ProgramRequirement.objects.count(), 0 if results[1] else 1)
        if results[1]:
            self.assertEqual(ProgramApplication.objects.get().requirements_snapshot, [])
        else:
            self.assertFalse(ProgramApplication.objects.exists())
