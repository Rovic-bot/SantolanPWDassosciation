"""Fictional PDAO corrections, preserved originals and review concurrency."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from members.models import Member
from .models import MembershipApplication
from .pdao_forms import PDAOReviewForm
from .pdao_models import PDAORegistration, PDAORegistrationRevision
from . import pdao_services as services
from .registration_models import registration_write
from .test_pdao_registration import PDAOHelpers, actor


def review_data(item, **changes):
    data = {name: value for name, value in item.current_data.items() if name in PDAOReviewForm.base_fields}
    return data | {'version': item.version, 'action': 'correct'} | changes


@override_settings(PDAO_REGISTRATION_ENABLED=True, SHORT_REFERENCES_ENABLED=True)
class PDAOReviewTests(PDAOHelpers, TestCase):
    def test_online_channel_is_automatic_and_not_an_applicant_question(self):
        response = self.client.get(reverse('membership:pdao_apply'))
        self.assertNotContains(response, 'Planned submission channel')
        self.assertNotContains(response, 'name="submission_channel"')
        self.assertContains(response, 'name="submission_token"')
        self.assertContains(response, 'Confirm details and submit application')
        item, data = self.submit()
        self.assertEqual(item.data['intake_channel'], 'online')
        self.assertNotIn('submission_channel', item.data)
        self.assertEqual(self.client.post(reverse('membership:pdao_apply'), data | {'intake_channel': 'walk_in'}).status_code, 400)

    def test_admin_edits_print_and_search_current_details_without_rewriting_original(self):
        item, original_post = self.submit()
        applicant = self.client
        self.client = Client()
        original, payload_digest, reference = item.data, item.payload_digest, item.short_reference
        staff = actor(services.VIEW, services.CORRECT, services.PRINT)
        self.client.force_login(staff)
        url = reverse('membership:pdao_detail', args=[item.pk])
        response = self.client.get(url)
        self.assertContains(response, 'Save reviewed details')
        self.assertEqual(response.context['editor_form'].initial['first_name'], original['first_name'])
        self.assertNotContains(response, 'name="acknowledgement"')
        self.assertNotContains(response, 'name="submission_channel"')
        data = review_data(item, first_name='Corrected', contact_number='09170000001')
        self.assertRedirects(self.client.post(url, data), url)
        item.refresh_from_db()
        self.assertEqual(item.data, original)
        self.assertEqual(item.payload_digest, payload_digest)
        self.assertEqual(item.short_reference, reference)
        self.assertEqual(item.current_data['first_name'], 'Corrected')
        self.assertEqual(item.current_data['contact_number'], '09170000001')
        self.assertEqual(item.revisions.get().actor, staff)
        self.assertTrue(item.events.filter(action='corrected', actor=staff, version=1).exists())
        response = self.client.get(reverse('membership:pdao_print', args=[item.pk]))
        self.assertContains(response, 'Corrected Example')
        self.assertContains(response, '09170000001')
        self.assertIn('no-store', response['Cache-Control'])
        response = self.client.get(reverse('membership:pdao_inbox'), {'q': 'Corrected'})
        self.assertEqual(list(response.context['page_obj']), [item])
        self.assertContains(response, 'Corrected Example')
        self.assertEqual(self.client.get(reverse('membership:pdao_inbox'), {'q': 'Fictional'}).context['page_obj'].paginator.count, 0)
        self.assertContains(applicant.get(reverse('membership:pdao_receipt')), 'Fictional Example')
        self.assertNotContains(applicant.get(reverse('membership:pdao_receipt')), 'Corrected Example')
        self.assertEqual(applicant.post(reverse('membership:pdao_apply'), original_post).status_code, 302)
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())

    def test_read_only_staff_and_revoked_permission_cannot_edit(self):
        item, _ = self.submit()
        staff = actor(services.VIEW, services.PRINT, services.FORWARD)
        self.client.force_login(staff)
        url = reverse('membership:pdao_detail', args=[item.pk])
        self.assertNotContains(self.client.get(url), 'Save reviewed details')
        self.assertEqual(self.client.post(url, review_data(item, first_name='Denied')).status_code, 403)
        from django.contrib.auth.models import Permission
        permission = Permission.objects.get(codename='correct_pdaoregistration')
        staff.user_permissions.add(permission)
        staff.has_perm(services.CORRECT)
        staff.user_permissions.remove(permission)
        with self.assertRaises(PermissionDenied):
            services.correct(item.pk, staff, review_data(item, first_name='Denied'))
        self.assertFalse(item.revisions.exists())

    def test_validation_stale_form_ready_reset_and_forwarded_record_protection(self):
        item, _ = self.submit()
        staff = actor(services.VIEW, services.CORRECT, services.FORWARD)
        stale = review_data(item, first_name='Stale')
        services.transition(item.pk, staff, {'version': 0, 'action': 'ready', 'ready_confirmed': 'on'})
        with self.assertRaises(ValidationError):
            services.correct(item.pk, staff, stale)
        item.refresh_from_db()
        self.client.force_login(staff)
        url = reverse('membership:pdao_detail', args=[item.pk])
        for changes in ({'contact_number': 'Letters'}, {'sex': 'invalid'}, {'first_name': ''}, {'status': 'forwarded'},
                        {'first_name': ['A', 'B']}, {'intake_channel': 'walk_in'}, {'acknowledgement': ''}):
            self.assertEqual(self.client.post(url, review_data(item, **changes)).status_code, 400)
        services.correct(item.pk, staff, review_data(item, first_name='Updated'))
        item.refresh_from_db()
        self.assertEqual((item.status, item.version), ('received', 2))
        self.assertEqual(self.client.post(url, stale).status_code, 409)
        services.correct(item.pk, staff, review_data(item))  # Unchanged save is idempotent.
        item.refresh_from_db()
        self.assertEqual(item.version, 2)
        services.transition(item.pk, staff, {'version': 2, 'action': 'ready', 'ready_confirmed': 'on'})
        services.transition(item.pk, staff, {'version': 3, 'action': 'forwarded', 'confirmed': 'on'})
        item.refresh_from_db()
        with self.assertRaises(ValidationError):
            services.correct(item.pk, staff, review_data(item, first_name='Too late'))
        self.assertNotContains(self.client.get(url), 'Save reviewed details')
        self.assertEqual(item.revisions.count(), 1)

    def test_audit_failure_rolls_back_and_revision_history_is_immutable(self):
        item, _ = self.submit()
        staff = actor(services.VIEW, services.CORRECT)
        data = review_data(item, first_name='Corrected')
        with patch.object(services, 'record_event', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                services.correct(item.pk, staff, data)
        item.refresh_from_db()
        self.assertEqual(item.version, 0)
        self.assertFalse(item.revisions.exists())
        services.correct(item.pk, staff, data)
        revision = item.revisions.get()
        with registration_write(), self.assertRaises(PermissionDenied):
            revision.save()
        with self.assertRaises(PermissionDenied):
            item.revisions.update(data={})
        with self.assertRaises(PermissionDenied):
            revision.delete()


@override_settings(PDAO_REGISTRATION_ENABLED=True)
class PDAOReviewConcurrencyTests(PDAOHelpers, TransactionTestCase):
    def test_concurrent_corrections_keep_one_current_revision(self):
        item, _ = self.submit()
        staff = actor(services.VIEW, services.CORRECT)
        data = review_data(item)
        barrier = Barrier(2)

        def save(name):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    services.correct(item.pk, staff, data | {'first_name': name})
                    return 'saved'
                except ValidationError:
                    return 'stale'
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(save, ['First', 'Second']))
        self.assertCountEqual(results, ['saved', 'stale'])
        item.refresh_from_db()
        self.assertEqual(item.version, 1)
        self.assertEqual(item.revisions.count(), 1)
        self.assertEqual(item.events.filter(action='corrected').count(), 1)


@override_settings(PDAO_REGISTRATION_ENABLED=True)
class PDAOReviewMigrationTests(PDAOHelpers, TransactionTestCase):
    def test_additive_migration_keeps_saved_submissions_and_history(self):
        import importlib
        from django.db.migrations.loader import MigrationLoader
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        self.assertNotEqual(connection.settings_dict['NAME'], 'santolan_pwd')
        item, _ = self.submit()
        before = PDAORegistration.objects.filter(pk=item.pk).values().get()
        events = list(item.events.values())
        state = MigrationLoader(connection, ignore_no_migrations=True).project_state()
        state.remove_model('membership', 'pdaoregistrationrevision')
        migration = importlib.import_module('membership.migrations.0010_pdao_review_corrections').Migration(
            '0010_pdao_review_corrections', 'membership')
        with connection.schema_editor() as editor:
            editor.delete_model(PDAORegistrationRevision)
        try:
            with connection.schema_editor() as editor:
                migration.apply(state, editor)
            self.assertEqual(PDAORegistration.objects.filter(pk=item.pk).values().get(), before)
            self.assertEqual(list(item.events.values()), events)
            self.assertFalse(PDAORegistrationRevision.objects.exists())
        finally:
            if PDAORegistrationRevision._meta.db_table not in connection.introspection.table_names():
                with connection.schema_editor() as editor:
                    editor.create_model(PDAORegistrationRevision)
