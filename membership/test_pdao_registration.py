"""Synthetic end-to-end checks; run only on the disposable native MySQL runner."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from config.registration_workflow import association_policy
from members.models import Member
from . import pdao_services as services
from .models import MembershipApplication, MembershipSettings
from .pdao_models import PDAORegistration, PDAORegistrationEvent
from .registration_models import RegistrationIntake, registration_write
from .test_pdf_registration import pdao_data, association_data


def actor(*permissions):
    user = get_user_model().objects.create_user('synthetic_pdao_staff', is_staff=True)
    for name in ('accounts.access_dashboard', *permissions):
        app, code = name.split('.')
        user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=code))
    return user


class PDAOHelpers:
    def prepare(self, client=None):
        client = client or self.client
        response = client.get(reverse('membership:pdao_apply'))
        self.assertEqual(response.status_code, 200)
        return pdao_data() | {'submission_token': response.context['form'].initial['submission_token']}

    def submit(self):
        data = self.prepare()
        response = self.client.post(reverse('membership:pdao_apply'), data)
        self.assertRedirects(response, reverse('membership:pdao_receipt'), fetch_redirect_response=False)
        return PDAORegistration.objects.get(), data


@override_settings(PDAO_REGISTRATION_ENABLED=True)
class PDAORegistrationTests(PDAOHelpers, TestCase):
    def test_retry_across_midnight_keeps_original_application_date(self):
        item, data = self.submit()
        original_date = item.data['date_applied']
        with patch('membership.intake_validation.timezone.localdate', return_value=timezone.localdate() + timedelta(days=1)):
            self.assertEqual(self.client.post(reverse('membership:pdao_apply'), data).status_code, 302)
            self.assertEqual(self.client.post(reverse('membership:pdao_apply'), data | {'first_name': 'Changed'}).status_code, 400)
        item.refresh_from_db()
        self.assertEqual(item.data['date_applied'], original_date)
        self.assertEqual(PDAORegistration.objects.count(), 1)
        self.assertEqual(item.events.count(), 1)

    def test_original_pdao_form_link_saves_to_staff_queue(self):
        url = reverse('membership:pdao_prepare')
        response = self.client.get(url)
        data = pdao_data() | {'submission_token': response.context['form'].initial['submission_token']}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        item = PDAORegistration.objects.get()
        self.client.force_login(actor(services.VIEW))
        self.assertContains(self.client.get(reverse('membership:pdao_inbox')), item.reference)

    def test_staff_can_review_retained_records_when_public_intake_is_closed(self):
        item, _ = self.submit()
        self.client.force_login(actor(services.VIEW))
        with self.settings(PDAO_REGISTRATION_ENABLED=False):
            self.assertContains(self.client.get(reverse('membership:pdao_inbox')), item.reference)
            self.assertContains(self.client.get(reverse('membership:pdao_detail', args=[item.pk])), item.reference)
            self.assertEqual(self.client.get(reverse('membership:pdao_apply')).status_code, 503)
            self.client.logout()
            self.assertEqual(self.client.get(reverse('membership:pdao_inbox')).status_code, 302)

    def test_confirmation_required_and_record_is_separate_from_members(self):
        data = self.prepare()
        response = self.client.post(reverse('membership:pdao_apply'), data | {'acknowledgement': ''})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(PDAORegistration.objects.exists())
        response = self.client.post(reverse('membership:pdao_apply'), data)
        self.assertEqual(response.status_code, 302)
        item = PDAORegistration.objects.get()
        self.assertTrue(item.data['acknowledgement'])
        self.assertNotIn('submission_token', item.data)
        self.assertEqual(item.events.get().action, 'submitted')
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertFalse(RegistrationIntake.objects.exists())

    def test_same_submission_is_idempotent_and_changed_retry_rejected(self):
        item, data = self.submit()
        self.assertEqual(self.client.post(reverse('membership:pdao_apply'), data).status_code, 302)
        self.assertEqual(self.client.post(reverse('membership:pdao_apply'), data | {'first_name': 'Changed'}).status_code, 400)
        self.assertEqual(PDAORegistration.objects.count(), 1)
        self.assertEqual(item.events.count(), 1)

    def test_receipt_is_private_and_hides_processing_history(self):
        item, data = self.submit()
        response = self.client.get(reverse('membership:pdao_receipt'))
        self.assertContains(response, item.reference)
        self.assertContains(response, 'submitted to Admin for review')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow, noarchive')
        stranger = Client()
        session = stranger.session
        session[services.RECEIPT_KEY] = str(item.pk)
        session.save()
        self.assertEqual(stranger.get(reverse('membership:pdao_receipt')).status_code, 404)
        self.assertEqual(stranger.post(reverse('membership:pdao_apply'), data).status_code, 403)
        self.assertNotContains(response, 'Processing history')
        self.assertNotContains(response, 'No application was sent to PDAO and no reference number was issued.')

    def test_finish_revokes_receipt_and_old_submission_token(self):
        item, data = self.submit()
        self.assertEqual(self.client.get(reverse('membership:pdao_finish')).status_code, 405)
        self.assertEqual(self.client.post(reverse('membership:pdao_finish')).status_code, 302)
        item.refresh_from_db()
        self.assertIsNotNone(item.receipt_revoked_at)
        self.assertEqual(self.client.get(reverse('membership:pdao_receipt')).status_code, 404)
        self.assertEqual(self.client.post(reverse('membership:pdao_apply'), data).status_code, 403)
        self.assertEqual(PDAORegistration.objects.count(), 1)

    def test_expired_token_fails_closed(self):
        data = self.prepare()
        token = signing.loads(data['submission_token'], salt=services.SALT)
        token['expires'] = 1
        data['submission_token'] = signing.dumps(token, salt=services.SALT)
        self.assertEqual(self.client.post(reverse('membership:pdao_apply'), data).status_code, 403)
        self.assertFalse(PDAORegistration.objects.exists())

    def test_csrf_is_enforced_and_oversized_body_rejected(self):
        client = Client(enforce_csrf_checks=True)
        data = self.prepare(client)
        self.assertEqual(client.post(reverse('membership:pdao_apply'), data).status_code, 403)
        data['csrfmiddlewaretoken'] = client.cookies['csrftoken'].value
        self.assertEqual(client.post(reverse('membership:pdao_apply'), data).status_code, 302)
        self.assertEqual(self.client.post(reverse('membership:pdao_apply'), b'x' * 65537,
                                         content_type='application/octet-stream').status_code, 413)

    def test_unknown_fields_duplicates_and_uploads_are_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        data = self.prepare()
        for extras in ({'status': 'forwarded'}, {'first_name': ['A', 'B']},
                       {'photo': SimpleUploadedFile('private.txt', b'private')}):
            with self.subTest(extras=tuple(extras)):
                self.assertEqual(self.client.post(reverse('membership:pdao_apply'), data | extras).status_code, 400)
        self.assertFalse(PDAORegistration.objects.exists())

    def test_audit_failure_rolls_back_submission(self):
        data = self.prepare()
        with patch.object(services, 'record_event', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('membership:pdao_apply'), data)
        self.assertFalse(PDAORegistration.objects.exists())

    def test_staff_queue_print_permissions_and_revocation(self):
        item, _ = self.submit()
        staff = actor(services.VIEW)
        self.client.force_login(staff)
        self.assertContains(self.client.get(reverse('membership:review_home')), 'PDAO Membership')
        self.assertContains(self.client.get(reverse('membership:pdao_inbox')), item.reference)
        self.assertContains(self.client.get(reverse('membership:pdao_detail', args=[item.pk])), item.data['full_name'])
        url = reverse('membership:pdao_print', args=[item.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename='print_pdaoregistration'))
        response = self.client.get(url)
        self.assertContains(response, 'Print or save PDF')
        self.assertContains(response, 'PDAO consent statement')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertTrue(item.events.filter(action='print_viewed').exists())
        staff.has_perm(services.PRINT)  # Populate a cache, then revoke permission.
        staff.user_permissions.remove(Permission.objects.get(codename='print_pdaoregistration'))
        with self.assertRaises(PermissionDenied):
            services.staff_record(item.pk, staff, printing=True)
        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertEqual(self.client.get(reverse('membership:registration_inbox')).status_code, 403)

    def test_forwarding_requires_permission_confirmation_and_current_version(self):
        item, _ = self.submit()
        staff = actor(services.VIEW)
        with self.assertRaises(PermissionDenied):
            services.transition(item.pk, staff, {'version': 0, 'action': 'ready', 'ready_confirmed': 'on'})
        staff.user_permissions.add(Permission.objects.get(codename='forward_pdaoregistration'))
        services.transition(item.pk, staff, {'version': 0, 'action': 'ready', 'ready_confirmed': 'on'})
        with self.assertRaises(ValidationError):
            services.transition(item.pk, staff, {'version': 0, 'action': 'forwarded', 'confirmed': 'on'})
        with self.assertRaises(ValidationError):
            services.transition(item.pk, staff, {'version': 1, 'action': 'forwarded'})
        services.transition(item.pk, staff, {'version': 1, 'action': 'forwarded', 'confirmed': 'on'})
        item.refresh_from_db()
        self.assertEqual(item.status, 'forwarded')
        self.assertEqual(list(item.events.values_list('action', flat=True)), ['submitted', 'ready', 'forwarded'])
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())

    def test_transition_audit_failure_rolls_back_and_original_data_is_immutable(self):
        item, _ = self.submit()
        staff = actor(services.VIEW, services.FORWARD)
        with patch.object(services, 'record_event', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                services.transition(item.pk, staff, {'version': 0, 'action': 'ready', 'ready_confirmed': 'on'})
        item.refresh_from_db()
        self.assertEqual(item.status, 'received')
        self.assertEqual(item.version, 0)
        with registration_write():
            with self.assertRaises(PermissionDenied):
                item.save(update_fields=['data'])
            event = item.events.get()
            with self.assertRaises(PermissionDenied):
                event.save()
        with self.assertRaises(PermissionDenied):
            PDAORegistration.objects.filter(pk=item.pk).update(status='forwarded')

    def test_rate_limit_and_disabled_service(self):
        with patch.object(services, 'reserve_windows', return_value=False):
            self.assertEqual(self.client.get(reverse('membership:pdao_apply')).status_code, 403)
        with override_settings(PDAO_REGISTRATION_ENABLED=False):
            with self.assertNumQueries(0):
                response = self.client.get(reverse('membership:pdao_apply'))
            self.assertEqual(response.status_code, 503)

    @override_settings(ASSOCIATION_REGISTRATION_POLICY=association_policy(5242880, 20971520))
    def test_enabled_association_confirmation_admin_decision_creates_member(self):
        response = self.client.get(reverse('core:membership'))
        self.assertContains(response, reverse('membership:registration_apply'))
        self.assertContains(response, reverse('membership:pdao_apply'))
        self.assertNotContains(response, 'Online membership registration is currently unavailable.')
        response = self.client.get(reverse('membership:registration_apply'))
        data = association_data() | {'context_id': response.context['context_id'], 'pwd_number': '00-0000-000-0000003'}
        self.assertEqual(self.client.post(reverse('membership:registration_apply'), data | {'acknowledgement': ''}).status_code, 400)
        self.assertFalse(RegistrationIntake.objects.exists())
        self.assertEqual(self.client.post(reverse('membership:registration_apply'), data).status_code, 302)
        self.assertFalse(Member.objects.exists())
        intake = RegistrationIntake.objects.get()
        MembershipSettings.objects.update_or_create(pk=1, defaults={
            'prpwd_url': 'https://registry.example.test/manual'})
        staff = actor('membership.view_membershipapplication', 'membership.view_registrationintake',
                      'membership.decide_membershipapplication', 'membership.verify_membershipapplication',
                      'members.view_member')
        self.client.force_login(staff)
        self.assertContains(self.client.get(reverse('membership:registration_inbox')), intake.reference)
        from .test_registration_decisions import accepted_office_invitation
        accepted_office_invitation(intake, staff)
        response = self.client.post(reverse('membership:registration_detail', args=[intake.reference]),
            association_data() | {'action': 'approve_registration', 'version': intake.version,
                                 'office_verification_confirmed': 'on',
                                 'pwd_number': '00-0000-000-0000003',
                                 'prpwd_lookup_number': '00-0000-000-0000003'})
        self.assertEqual(response.status_code, 302)
        member = Member.objects.get()
        self.assertEqual(member.application.status, 'approved')
        self.assertEqual(member.control_number, '00-0000-000-0000003')
        self.assertContains(self.client.get(reverse('members:registration_print', args=[member.pk])), 'Print')


@override_settings(PDAO_REGISTRATION_ENABLED=True)
class PDAOConcurrencyTests(PDAOHelpers, TransactionTestCase):
    def test_concurrent_duplicate_submissions_create_one_record(self):
        data = self.prepare()
        barrier = Barrier(2)
        cookies = self.client.cookies.copy()

        def send():
            close_old_connections()
            try:
                client = Client()
                client.cookies = cookies.copy()
                barrier.wait(timeout=10)
                return client.post(reverse('membership:pdao_apply'), data).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: send(), range(2)))
        self.assertEqual(results, [302, 302])
        self.assertEqual(PDAORegistration.objects.count(), 1)
        self.assertEqual(PDAORegistrationEvent.objects.filter(action='submitted').count(), 1)


class PDAOMigrationTests(TransactionTestCase):
    def test_additive_migration_rehearsal_preserves_existing_records(self):
        import importlib
        from django.db.migrations.loader import MigrationLoader
        from .pdao_models import PDAORegistrationRevision
        from .pdao_email_models import PDAOReviewEmail, PDAOReviewEmailAttempt
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        self.assertNotEqual(connection.settings_dict['NAME'], 'santolan_pwd')
        staff = actor()
        loader = MigrationLoader(connection, ignore_no_migrations=True)
        state = loader.project_state()
        state.remove_model('membership', 'pdaoreviewemailattempt')
        state.remove_model('membership', 'pdaoreviewemail')
        state.remove_model('membership', 'pdaoregistrationrevision')
        state.remove_model('membership', 'pdaoregistrationevent')
        state.remove_model('membership', 'pdaoregistration')
        migration = importlib.import_module('membership.migrations.0009_pdao_online_registration').Migration(
            '0009_pdao_online_registration', 'membership')
        self.assertFalse(PDAORegistrationRevision.objects.exists())
        try:
            with connection.schema_editor() as editor:
                editor.delete_model(PDAOReviewEmailAttempt)
                editor.delete_model(PDAOReviewEmail)
                editor.delete_model(PDAORegistrationRevision)
                migration.unapply(state, editor)
            with connection.schema_editor() as editor:
                migration.apply(state, editor)
        finally:
            # The rehearsal contains no PDAO rows. Restore the current schema,
            # including later review fields and dependent notification tables.
            with connection.schema_editor() as editor:
                for model in (PDAORegistrationEvent, PDAORegistration):
                    if model._meta.db_table in connection.introspection.table_names():
                        self.assertFalse(model.objects.only('pk').exists())
                        editor.delete_model(model)
                for model in (PDAORegistration, PDAORegistrationEvent, PDAORegistrationRevision, PDAOReviewEmail, PDAOReviewEmailAttempt):
                    if model._meta.db_table not in connection.introspection.table_names():
                        editor.create_model(model)
            self.assertTrue(get_user_model().objects.filter(pk=staff.pk).exists())
        self.assertFalse(PDAORegistration.objects.exists())
        self.assertFalse(PDAORegistrationEvent.objects.exists())
