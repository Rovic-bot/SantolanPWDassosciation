"""G06-B1A: synthetic records only, on a disposable MySQL test database."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, connections
from django.db.migrations.executor import MigrationExecutor
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from membership.tests import grant
from .approval_services import record_pdao_approval
from .models import PDAOApprovalRecord, Program, ProgramLog
from .tests import create_program


RECORD_PERMISSIONS = ('accounts.access_dashboard', 'programs.view_program',
                      'programs.view_pdaoapprovalrecord', 'programs.record_pdaoapprovalrecord')


def approval_data(**overrides):
    return {'kind': 'official', 'approval_date': str(timezone.localdate()),
            'signatory': 'Synthetic PDAO signatory', 'manual_confirmation': True,
            'reason': 'Synthetic physical letter checked at the office.',
            'expected_version': 0, 'expected_program_version': 0, **overrides}


class PDAOApprovalTests(TestCase):
    def setUp(self):
        self.program = create_program(budget=Decimal('12345.67'))
        self.officer = get_user_model().objects.create_user('synthetic_secretary', is_staff=True)
        grant(self.officer, *RECORD_PERMISSIONS)
        self.url = reverse('programs:pdao_history', args=[self.program.pk])

    def record(self, **overrides):
        return record_pdao_approval(self.program.pk, user=self.officer, data=approval_data(**overrides))

    def test_authorized_secretary_records_official_approval_and_audit(self):
        entry = self.record()
        self.assertEqual(entry.version, 1)
        self.assertEqual(entry.approval_date, timezone.localdate())
        self.assertEqual(entry.signatory, 'Synthetic PDAO signatory')
        self.assertEqual(entry.recorded_by, self.officer)
        self.assertEqual(entry.recorded_by_label, self.officer.username)
        self.assertTrue(entry.manual_confirmation)
        self.assertIsNotNone(entry.recorded_at)
        self.assertEqual(entry.audit_entry.action, 'pdao_recorded')
        self.assertEqual(entry.audit_entry.actor, self.officer)
        self.assertEqual(entry.audit_entry.program, self.program)
        self.assertEqual(entry.audit_entry.changes['pdao_record_version'], {'before': 0, 'after': 1})

    def test_each_permission_required_for_service_and_post(self):
        for missing in RECORD_PERMISSIONS:
            with self.subTest(missing=missing):
                user = get_user_model().objects.create_user('synthetic_' + missing, is_staff=True)
                grant(user, *(permission for permission in RECORD_PERMISSIONS if permission != missing))
                with self.assertRaises(PermissionDenied):
                    record_pdao_approval(self.program.pk, user=user, data=approval_data())
                self.client.force_login(user)
                self.assertEqual(self.client.post(self.url, approval_data()).status_code, 403)
        self.assertFalse(PDAOApprovalRecord.objects.exists())
        self.assertFalse(ProgramLog.objects.filter(action='pdao_recorded').exists())

    def test_anonymous_inactive_and_nonstaff_cannot_record(self):
        for user in (AnonymousUser(), self.officer):
            if user == self.officer:
                user.is_staff = False
            with self.assertRaises(PermissionDenied):
                record_pdao_approval(self.program.pk, user=user, data=approval_data())
        self.officer.is_staff = True
        self.officer.is_active = False
        with self.assertRaises(PermissionDenied):
            self.record()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_view_permission_is_separate_and_history_is_private(self):
        self.record()
        viewer = get_user_model().objects.create_user('synthetic_history_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'programs.view_program')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        detail_url = reverse('programs:manage_detail', args=[self.program.pk])
        self.assertNotContains(self.client.get(detail_url), self.url)
        grant(viewer, 'programs.view_pdaoapprovalrecord')
        response = self.client.get(self.url)
        self.assertContains(response, 'Synthetic PDAO signatory')
        self.assertNotContains(response, 'name="manual_confirmation"')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertContains(self.client.get(detail_url), self.url)
        self.assertEqual(self.client.post(self.url, approval_data()).status_code, 403)
        public = self.client.get(reverse('programs:detail', args=[self.program.pk]))
        self.assertNotContains(public, 'Synthetic PDAO signatory')
        self.assertNotContains(public, self.url)

    def test_required_fields_and_manual_confirmation(self):
        for changes in ({'approval_date': ''}, {'signatory': ''}, {'signatory': ' \t\n'},
                        {'manual_confirmation': False}, {'manual_confirmation': ''},
                        {'kind': 'approved'}, {'reason': '  '}, {'expected_version': -1},
                        {'expected_program_version': ''},
                        {'approval_date': str(timezone.localdate() + timedelta(days=1))}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValidationError):
                    self.record(**changes)
        self.assertFalse(PDAOApprovalRecord.objects.exists())
        self.assertFalse(ProgramLog.objects.filter(action='pdao_recorded').exists())

    def test_legacy_attestation_keeps_unknown_metadata_blank(self):
        entry = self.record(kind='legacy', approval_date='', signatory='',
                            reason='Synthetic prior approval attested; letter missing, replacement requested.')
        self.assertIsNone(entry.approval_date)
        self.assertEqual(entry.signatory, '')
        self.assertEqual(entry.kind, 'legacy')
        self.client.force_login(self.officer)
        response = self.client.get(self.url)
        self.assertContains(response, 'Unknown — not recorded', count=2)
        self.assertContains(response, 'This is not an official letter record.')
        self.assertContains(response, 'replacement approval being obtained')

    def test_legacy_requires_explicit_confirmation_and_can_retain_known_metadata(self):
        with self.assertRaises(ValidationError):
            self.record(kind='legacy', approval_date='', signatory='', manual_confirmation=False)
        entry = self.record(kind='legacy', approval_date='', signatory='Known synthetic signatory')
        self.assertIsNone(entry.approval_date)
        self.assertEqual(entry.signatory, 'Known synthetic signatory')

    def test_new_record_retains_old_attestation_and_independent_sequence(self):
        first = self.record(kind='legacy', approval_date='', signatory='')
        original = PDAOApprovalRecord.objects.filter(pk=first.pk).values().get()
        second = self.record(expected_version=1, reason='Synthetic replacement letter obtained.')
        self.assertEqual(second.version, 2)
        self.assertEqual(list(self.program.pdao_approval_records.values_list('version', flat=True)), [2, 1])
        self.assertEqual(PDAOApprovalRecord.objects.filter(pk=first.pk).values().get(), original)
        self.assertEqual(ProgramLog.objects.filter(action='pdao_recorded').count(), 2)

    def test_legacy_rejected_without_previous_publication(self):
        for status in ('draft', 'archived'):
            with self.subTest(status=status):
                self.program.status = status
                self.program.published_at = None
                self.program.save(update_fields=['status', 'published_at'])
                before = Program.objects.filter(pk=self.program.pk).values().get()
                with self.assertRaisesMessage(ValidationError, 'previously published'):
                    self.record(kind='legacy', approval_date='', signatory='')
                self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), before)
        self.assertFalse(PDAOApprovalRecord.objects.exists())
        self.assertFalse(ProgramLog.objects.filter(action='pdao_recorded').exists())

    def test_forged_publication_post_cannot_enable_legacy_attestation(self):
        self.program.status = 'draft'
        self.program.published_at = None
        self.program.save(update_fields=['status', 'published_at'])
        self.client.force_login(self.officer)
        response = self.client.post(self.url, approval_data(
            kind='legacy', approval_date='', signatory='', status='published',
            published_at=str(timezone.now() - timedelta(days=1))))
        self.assertContains(response, 'Legacy attestations require a previously published program.')
        self.assertFalse(PDAOApprovalRecord.objects.exists())
        self.assertFalse(ProgramLog.objects.filter(action='pdao_recorded').exists())
        self.program.refresh_from_db()
        self.assertIsNone(self.program.published_at)
        self.assertEqual(self.program.status, 'draft')

    def test_future_publication_is_not_previous_publication(self):
        now = timezone.now()
        self.program.published_at = now + timedelta(seconds=1)
        self.program.save(update_fields=['published_at'])
        with patch('programs.approval_services.timezone.now', return_value=now):
            with self.assertRaisesMessage(ValidationError, 'previously published'):
                self.record(kind='legacy', approval_date='', signatory='')
            self.assertFalse(PDAOApprovalRecord.objects.exists())
            self.assertFalse(ProgramLog.objects.filter(action='pdao_recorded').exists())
            self.program.published_at = now
            self.program.save(update_fields=['published_at'])
            self.assertEqual(self.record(kind='legacy', approval_date='', signatory='').kind, 'legacy')

    def test_previous_publication_allows_explicit_legacy_attestation_after_withdrawal(self):
        from .services import change_publication
        admin = get_user_model().objects.create_superuser('synthetic_publication_admin')
        for status in ('published', 'draft', 'cancelled', 'archived'):
            with self.subTest(status=status):
                program = create_program()
                program.status = 'draft'
                program.published_at = None
                program.save(update_fields=['status', 'published_at'])
                program = change_publication(program.pk, user=admin, version=program.version,
                                             action='published', notes='Synthetic publication.')
                if status != 'published':
                    program = change_publication(program.pk, user=admin, version=program.version,
                                                 action=status, notes='Synthetic lifecycle change.')
                before = Program.objects.filter(pk=program.pk).values().get()
                self.assertIsNotNone(program.published_at)
                self.assertFalse(program.pdao_approval_records.exists())
                data = approval_data(kind='legacy', approval_date='', signatory='',
                                     expected_program_version=program.version, manual_confirmation=False)
                with self.assertRaises(ValidationError):
                    record_pdao_approval(program.pk, user=self.officer, data=data)
                self.assertFalse(program.pdao_approval_records.exists())
                data['manual_confirmation'] = True
                entry = record_pdao_approval(program.pk, user=self.officer, data=data)
                self.assertEqual(entry.kind, 'legacy')
                self.assertIsNone(entry.approval_date)
                self.assertEqual(entry.signatory, '')
                self.assertEqual(Program.objects.filter(pk=program.pk).values().get(), before)

    def test_official_approval_allowed_for_never_published_draft(self):
        self.program.status = 'draft'
        self.program.published_at = None
        self.program.policy_authorized_at = None
        self.program.save(update_fields=['status', 'published_at', 'policy_authorized_at'])
        before = Program.objects.filter(pk=self.program.pk).values().get()
        entry = self.record()
        self.assertEqual(entry.kind, 'official')
        self.assertEqual(entry.approval_date, timezone.localdate())
        self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), before)

    def test_model_validation_requires_matching_audit_program_actor_and_action(self):
        entry = self.record()
        entry.full_clean()
        original = PDAOApprovalRecord.objects.filter(pk=entry.pk).values().get()
        other_program = create_program()
        other_actor = get_user_model().objects.create_user('synthetic_other_recorder')
        for changes in ({'program': other_program}, {'actor': other_actor}, {'action': 'updated'}):
            with self.subTest(fields=list(changes)):
                values = {'program': self.program, 'actor': self.officer, 'action': 'pdao_recorded',
                          'notes': 'Synthetic mismatched audit.', **changes}
                entry.audit_entry = ProgramLog.objects.create(**values)
                with self.assertRaises(ValidationError) as caught:
                    entry.full_clean()
                self.assertIn('audit_entry', caught.exception.message_dict)
                self.assertEqual(PDAOApprovalRecord.objects.filter(pk=entry.pk).values().get(), original)

    def test_mismatched_audit_rolls_back_and_displays_validation_error(self):
        from .services import record_log

        def incorrect_audit(program, action, notes, **kwargs):
            return record_log(program, 'updated', notes, **kwargs)

        self.client.force_login(self.officer)
        with patch('programs.approval_services.record_log', side_effect=incorrect_audit):
            response = self.client.post(self.url, approval_data())
        self.assertContains(response, 'The audit entry must match this program, recording actor and PDAO recording action.')
        self.assertFalse(PDAOApprovalRecord.objects.exists())
        self.assertFalse(ProgramLog.objects.exists())
        self.assertEqual(self.record().version, 1)

    def test_forged_post_cannot_control_actor_program_version_budget_or_audit(self):
        other = create_program()
        self.client.force_login(self.officer)
        response = self.client.post(self.url, approval_data(
            program=str(other.pk), recorded_by='999999', recorded_at='2000-01-01', version='9000',
            audit_entry='999999', program_version_at_recording='9000', budget='0', approved_budget='999',
            status='archived', policy_authorized_at='2000-01-01'))
        self.assertRedirects(response, self.url)
        entry = PDAOApprovalRecord.objects.get()
        self.assertEqual(entry.program, self.program)
        self.assertEqual(entry.recorded_by, self.officer)
        self.assertEqual(entry.version, 1)
        self.assertEqual(entry.program_version_at_recording, 0)
        self.assertEqual(timezone.localdate(entry.recorded_at), timezone.localdate())
        self.program.refresh_from_db()
        self.assertEqual(self.program.budget, Decimal('12345.67'))
        self.assertEqual(self.program.status, 'published')
        self.assertFalse(other.pdao_approval_records.exists())

    def test_stale_approval_sequence_rejected_without_extra_audit(self):
        self.record()
        with self.assertRaisesMessage(ValidationError, 'history changed'):
            self.record()
        self.assertEqual(PDAOApprovalRecord.objects.count(), 1)
        self.assertEqual(ProgramLog.objects.filter(action='pdao_recorded').count(), 1)

    def test_stale_program_version_rejected_without_bumping_program(self):
        self.program.version = 1
        self.program.save(update_fields=['version'])
        with self.assertRaisesMessage(ValidationError, 'history changed'):
            self.record()
        self.record(expected_program_version=1)
        self.program.refresh_from_db()
        self.assertEqual(self.program.version, 1)

    def test_immutable_instance_queryset_and_bulk_history(self):
        entry = self.record()
        original = PDAOApprovalRecord.objects.filter(pk=entry.pk).values().get()
        entry.signatory = 'Attempted replacement'
        attempts = (lambda: entry.save(), lambda: entry.delete(),
                    lambda: PDAOApprovalRecord.objects.filter(pk=entry.pk).update(signatory='Changed'),
                    lambda: PDAOApprovalRecord.objects.all().delete(),
                    lambda: PDAOApprovalRecord.objects.bulk_update([entry], ['signatory']),
                    lambda: PDAOApprovalRecord.objects.bulk_create([entry], update_conflicts=True,
                                                                  update_fields=['signatory']))
        for operation in attempts:
            with self.assertRaises(ValidationError):
                operation()
        self.assertEqual(PDAOApprovalRecord.objects.filter(pk=entry.pk).values().get(), original)
        self.assertFalse(Permission.objects.filter(content_type__app_label='programs',
            codename__in=['change_pdaoapprovalrecord', 'delete_pdaoapprovalrecord', 'add_pdaoapprovalrecord']).exists())

    def test_linked_audit_actor_and_program_are_protected(self):
        entry = self.record()
        for item in (entry.audit_entry, self.officer, self.program):
            with self.assertRaises(ProtectedError):
                item.delete()

    def test_audit_failure_rolls_back_record(self):
        before = Program.objects.filter(pk=self.program.pk).values().get()
        with patch('programs.approval_services.record_log', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.record()
        self.assertFalse(PDAOApprovalRecord.objects.exists())
        self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), before)

    def test_record_failure_rolls_back_audit(self):
        with patch.object(PDAOApprovalRecord, 'save', side_effect=RuntimeError('Synthetic insert failure')):
            with self.assertRaises(RuntimeError):
                self.record()
        self.assertFalse(PDAOApprovalRecord.objects.exists())
        self.assertFalse(ProgramLog.objects.filter(action='pdao_recorded').exists())
        self.assertEqual(self.record().version, 1)

    def test_recording_does_not_change_program_or_internal_policy(self):
        for status in ('draft', 'published', 'cancelled', 'archived'):
            with self.subTest(status=status):
                program = create_program(budget=Decimal('55.00'))
                program.status = status
                program.policy_authorized_at = None
                program.save(update_fields=['status', 'policy_authorized_at'])
                before = Program.objects.filter(pk=program.pk).values().get()
                available = program.registration_available
                record_pdao_approval(program.pk, user=self.officer, data=approval_data())
                self.assertEqual(Program.objects.filter(pk=program.pk).values().get(), before)
                program.refresh_from_db()
                self.assertEqual(program.registration_available, available)
                self.assertIsNone(program.policy_authorized_at)

    def test_recording_preserves_existing_release_application_and_eligibility(self):
        from announcements.models import Announcement, ProgramResultRevision
        from announcements.results import prepare_results, results_current
        from announcements.services import change_publication
        from assistance.models import AssistanceCase, AssistanceRelease
        from assistance.services import review_eligibility, decide_assistance, record_release
        from assistance.tests import create_application, review_data, decision_data, release_data, seed_statuses
        from .testsupport import private_media, close_non_ewaf_program
        private_media(self)
        seed_statuses()
        admin = get_user_model().objects.create_superuser('synthetic_release_admin')
        application = create_application(program=self.program)
        review_eligibility(application.pk, user=admin, data=review_data(application))
        close_non_ewaf_program(self.program)
        decide_assistance(application.pk, user=admin, data=decision_data(application))
        release = record_release(application.pk, user=admin, data=release_data(application))
        announcement = prepare_results(self.program.pk, user=admin, version=0,
                                       reason='Synthetic approved result publication.')
        announcement = change_publication(announcement.pk, user=admin, version=announcement.version, action='published')
        before_announcement = Announcement.objects.filter(pk=announcement.pk).values().get()
        before_results = list(ProgramResultRevision.objects.filter(announcement=announcement).values())
        application.refresh_from_db()
        before_application = type(application).objects.filter(pk=application.pk).values().get()
        before_case = AssistanceCase.objects.filter(application=application).values().get()
        before_release = AssistanceRelease.objects.filter(pk=release.pk).values().get()
        before_program = Program.objects.filter(pk=self.program.pk).values().get()
        self.record()
        self.assertEqual(type(application).objects.filter(pk=application.pk).values().get(), before_application)
        self.assertEqual(AssistanceCase.objects.filter(application=application).values().get(), before_case)
        self.assertEqual(AssistanceRelease.objects.filter(pk=release.pk).values().get(), before_release)
        self.assertEqual(Program.objects.filter(pk=self.program.pk).values().get(), before_program)
        self.assertEqual(Announcement.objects.filter(pk=announcement.pk).values().get(), before_announcement)
        self.assertEqual(list(ProgramResultRevision.objects.filter(announcement=announcement).values()), before_results)
        self.assertTrue(results_current(announcement))
        self.assertEqual(self.client.get(reverse('announcements:detail', args=[announcement.pk])).status_code, 200)

    def test_no_autoapproval_or_new_application_gate(self):
        from members.tests import create_member
        from .services import require_open, verify_member, grant_valid
        from .tests import verification
        self.assertFalse(self.program.pdao_approval_records.exists())
        require_open(self.program)
        self.assertTrue(Program.objects.accepting_applications().filter(pk=self.program.pk).exists())
        self.client.force_login(self.officer)
        self.assertContains(self.client.get(self.url), 'No PDAO approval or legacy attestation has been recorded.')
        member = create_member('SYNTHETIC-PDAO-GRANT')
        member.refresh_from_db()
        verified = verify_member(self.program.pk, **verification(member, self.program))
        self.record(kind='legacy', approval_date='', signatory='')
        self.program.refresh_from_db()
        require_open(self.program)
        self.assertTrue(grant_valid(verified, self.program))

    def test_upload_rejected_no_upload_or_budget_fields(self):
        self.client.force_login(self.officer)
        response = self.client.get(self.url)
        self.assertNotContains(response, 'type="file"')
        self.assertNotContains(response, 'name="budget"')
        self.assertNotContains(response, 'name="approved_budget"')
        response = self.client.post(self.url, approval_data(
            letter=SimpleUploadedFile('synthetic.txt', b'Synthetic rejected content')))
        self.assertContains(response, 'Uploads are not accepted.')
        self.assertFalse(PDAOApprovalRecord.objects.exists())

    def test_csrf_and_http_method_guards(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.officer)
        self.assertEqual(client.post(self.url, approval_data()).status_code, 403)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.put(self.url, approval_data()).status_code, 405)
        self.assertEqual(self.client.delete(self.url).status_code, 405)

    def test_history_pagination_and_escaped_accessible_text(self):
        for version in range(21):
            self.record(expected_version=version, signatory='<script>Synthetic</script>')
        self.client.force_login(self.officer)
        response = self.client.get(self.url)
        self.assertEqual(len(response.context['history']), 20)
        self.assertContains(response, '&lt;script&gt;Synthetic&lt;/script&gt;')
        self.assertNotContains(response, '<script>Synthetic</script>')
        self.assertContains(response, 'for="id_manual_confirmation"')
        self.assertContains(response, 'PDAO history pages')
        self.assertContains(response, '(Philippine time)')
        second = self.client.get(self.url, {'page': 2})
        self.assertEqual([entry.version for entry in second.context['history']], [1])


class PDAOApprovalConcurrencyTests(TransactionTestCase):
    def test_simultaneous_recording_retains_one_entry_and_rejects_stale_writer(self):
        program = create_program()
        officer = get_user_model().objects.create_superuser('synthetic_concurrent_officer')
        barrier = Barrier(2)

        def worker():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    record_pdao_approval(program.pk, user=officer, data=approval_data())
                    return 'recorded'
                except ValidationError:
                    return 'stale'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]
        self.assertCountEqual(results, ['recorded', 'stale'])
        self.assertEqual(PDAOApprovalRecord.objects.count(), 1)
        self.assertEqual(ProgramLog.objects.filter(action='pdao_recorded').count(), 1)
        program.refresh_from_db()
        self.assertEqual(program.version, 0)
        next_entry = record_pdao_approval(program.pk, user=officer, data=approval_data(expected_version=1))
        self.assertEqual(next_entry.version, 2)


class PDAOApprovalMigrationTests(TransactionTestCase):
    def test_additive_migration_preserves_legacy_programs_without_inferred_approval(self):
        old = [('programs', '0003_revised_seventy_workflow')]
        new = [('programs', '0004_pdaoapprovalrecord')]
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        program = create_program(budget=Decimal('98765.43'))
        before = Program.objects.filter(pk=program.pk).values().get()
        executor.migrate(old)
        try:
            executor = MigrationExecutor(connection)
            migration = executor.loader.get_migration(*new[0])
            self.assertEqual([operation.__class__.__name__ for operation in migration.operations], ['CreateModel'])
            executor.migrate(new)
            self.assertEqual(Program.objects.filter(pk=program.pk).values().get(), before)
            self.assertFalse(PDAOApprovalRecord.objects.exists())
        finally:
            MigrationExecutor(connection).migrate(latest)
