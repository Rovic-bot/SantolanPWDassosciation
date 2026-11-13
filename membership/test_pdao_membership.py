"""Claim-to-membership acceptance using fictional applicants and disposable DBs."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from importlib import import_module
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, connections, IntegrityError, transaction
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict

from members.models import Member
from scripts.durable_test_runner import require_disposable
from . import pdao_membership as transfer, pdao_services, registration_services as intake_services
from .models import MembershipApplication
from .pdao_claim_email import queue_claim_notices
from .pdao_email import current_notice
from .pdao_email_models import PDAOReviewEmail
from .pdao_forms import PDAOOnsiteForm, ONSITE_PRIVACY_VERSION
from .pdao_models import PDAOIDClaim, PDAORegistration
from .registration_decisions import member_values
from .registration_forms import OnlineRegistrationForm, OnsiteRegistrationForm
from .registration_models import RegistrationIntake, RegistrationAttachment, registration_write
from .registration_policy import digest, policy_for
from .test_pdf_registration import association_data, pdao_data, pdf_policy
from .test_registration_intake import staff, upload
from .tests import grant


class TransferHelpers:
    def setup_transfer(self):
        require_disposable()
        self.actor = staff('fictional_transfer_staff', pdao_services.VIEW, pdao_services.FORWARD,
                           'membership.encode_registrationintake')
        self.binding = intake_services.binding_for('fictional-transfer-session')
        self.client.force_login(self.actor)

    def record(self, *, status='forwarded', **changes):
        form = PDAOOnsiteForm(pdao_data() | {'submission_token': 'fictional',
            'disability_types': ['Physical Disability'], 'suffix': 'Jr.',
            'sex': 'Male', 'employment_status': 'Unemployed', **changes})
        assert form.is_valid(), form.errors
        data = form.submitted_data() | {'intake_channel': 'walk_in'}
        with registration_write():
            return PDAORegistration.objects.create(submission_key=uuid4(), data=data,
                payload_digest=digest(data), privacy_version=ONSITE_PRIVACY_VERSION,
                binding_digest='fictional', receipt_expires_at=timezone.now() + timedelta(hours=1),
                status=status, version=2 if status == 'forwarded' else 0)

    def claim(self, record):
        return transfer.record_claim(record.pk, user=self.actor,
            data={'version': record.version, 'pwd_number': '00-0000-000-0000123', 'confirmed': 'on'})

    def submit(self, record, *, data=None, context=None, files=None):
        context = context or intake_services.issue_context(self.binding, user=self.actor, channel='walk_in')
        return transfer.submit_membership(record.pk, user=self.actor, context_id=context.pk,
            binding=self.binding, data=association_data() | {'membership_requested': 'on', **(data or {})}, files=files)


@override_settings(PDAO_REGISTRATION_ENABLED=True, ASSOCIATION_REGISTRATION_POLICY=pdf_policy(),
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', PDAO_CLAIM_EMAIL_BACKGROUND=False)
class PDAOToMembershipTests(TransferHelpers, TestCase):
    def setUp(self):
        self.setup_transfer()
        self.media = TemporaryDirectory(prefix='fictional-pdao-transfer-')
        self.addCleanup(self.media.cleanup)
        override = override_settings(MEDIA_ROOT=self.media.name)
        override.enable()
        self.addCleanup(override.disable)

    def test_claim_requires_forwarded_actual_collection_valid_id_and_current_version(self):
        for status in ('received', 'needs_info', 'ready'):
            with self.assertRaises(ValidationError):
                self.claim(self.record(status=status))
        record = self.record()
        for changes in ({'confirmed': ''}, {'pwd_number': 'PWD-invalid'}, {'version': 1}):
            with self.assertRaises(ValidationError):
                transfer.record_claim(record.pk, user=self.actor, data={
                    'version': 2, 'pwd_number': '00-0000-000-0000123', 'confirmed': 'on', **changes})
        self.assertFalse(PDAOIDClaim.objects.exists())
        self.claim(record)
        self.assertEqual(self.claim(record).pk, record.pk)
        record.refresh_from_db()
        self.assertEqual(record.version, 3)
        self.assertEqual(record.events.filter(action='id_claimed').count(), 1)
        self.assertEqual(PDAOIDClaim.objects.count(), 1)
        self.assertFalse(RegistrationIntake.objects.exists())
        self.assertFalse(Member.objects.exists())
        self.assertFalse(PDAOReviewEmail.objects.exists())
        with self.assertRaises(ValidationError):
            transfer.record_claim(record.pk, user=self.actor, data={
                'version': 3, 'pwd_number': '999', 'confirmed': 'on'})

    def test_ready_notice_does_not_unlock_membership_and_claim_stops_new_notices(self):
        record = self.record()
        queue_claim_notices(user=self.actor, selections={record.pk: 2}, confirmed=True)
        notice = PDAOReviewEmail.objects.get()
        self.assertTrue(current_notice(notice, record))
        url = reverse('membership:pdao_membership', args=[record.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        with self.assertRaises(ValidationError):
            self.submit(record)
        self.claim(record)
        record.refresh_from_db()
        self.assertFalse(current_notice(notice, record))
        with self.assertRaises(ValidationError):
            queue_claim_notices(user=self.actor, selections={record.pk: 3}, confirmed=True)
        self.assertFalse(RegistrationIntake.objects.exists())

    def test_all_disability_labels_map_without_changing_source(self):
        for source, target in transfer.DISABILITIES.items():
            with self.subTest(disability=source):
                record = self.record(disability_types=[source])
                claim = self.claim(record)
                form = transfer.PDAOAssociationForm(claim=claim, policy=policy_for('staff'))
                self.assertEqual(form['disability_type'].value(), target)
                self.assertTrue(form.fields['disability_type'].disabled)
                self.assertFalse(form['four_ps_member'].value())
                self.assertTrue(form.fields['four_ps_member'].required)
                record.refresh_from_db()
                self.assertEqual(record.current_data['disability_types'], [source])

    def test_multiple_disabilities_require_an_explicit_recorded_choice(self):
        claim = self.claim(self.record(disability_types=['Visual Disability', 'Physical Disability']))
        for value in ('', 'Hearing'):
            form = transfer.PDAOAssociationForm(association_data() | {
                'membership_requested': 'on', 'disability_type': value}, claim=claim, policy=policy_for('staff'))
            self.assertFalse(form.is_valid())
            self.assertIn('disability_type', form.errors)
        form = transfer.PDAOAssociationForm(association_data() | {
            'membership_requested': 'on', 'disability_type': 'Physical / Orthopedic'}, claim=claim, policy=policy_for('staff'))
        self.assertTrue(form.is_valid(), form.errors)

    def test_remaining_required_fields_and_explicit_membership_request(self):
        claim = self.claim(self.record(email='', employment_status=''))
        for name in ('household_monthly_income', 'household_members', 'four_ps_member',
                     'employment_status', 'email', 'acknowledgement', 'membership_requested'):
            form = transfer.PDAOAssociationForm(association_data() | {
                'membership_requested': 'on', name: ''}, claim=claim, policy=policy_for('staff'))
            with self.subTest(field=name):
                self.assertFalse(form.is_valid())
                self.assertIn(name, form.errors)
        self.assertFalse(RegistrationIntake.objects.exists())

    def test_transfer_uses_server_record_and_creates_only_one_pending_application(self):
        record = self.record()
        original = record.current_data
        claim = self.claim(record)
        context = intake_services.issue_context(self.binding, user=self.actor, channel='walk_in')
        intake = self.submit(record, context=context, data={'first_name': 'Tampered',
            'birthdate': '2001-01-01', 'pwd_number': '999', 'disability_type': 'Hearing',
            'four_ps_member': 'No', 'suffix': 'Changed'})
        source = intake.revisions.get(number=1).data
        self.assertEqual(source['first_name'], original['first_name'])
        self.assertEqual(source['birthdate'], original['birthdate'])
        self.assertEqual(source['pwd_number'], claim.pwd_number)
        self.assertEqual(source['disability_type'], 'Physical / Orthopedic')
        self.assertEqual(source['four_ps_member'], 'No')
        self.assertEqual(source['full_name'], original['full_name'])
        self.assertEqual(source['suffix'], 'Jr.')
        self.assertEqual(member_values(source, claim.pwd_number)[0]['suffix'], 'Jr.')
        self.assertEqual(self.submit(record, context=context).pk, intake.pk)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        claim.refresh_from_db()
        self.assertEqual(claim.membership_intake_id, intake.pk)
        self.assertEqual(intake.state, 'received')
        self.assertEqual(record.events.filter(action='membership_started').count(), 1)
        self.assertEqual(record.current_data, original)
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertFalse(PDAOReviewEmail.objects.exists())

    def test_claim_and_transfer_roll_back_on_audit_failure_including_private_files(self):
        record = self.record()
        with patch.object(pdao_services, 'record_event', side_effect=RuntimeError('Fictional audit failure')):
            with self.assertRaises(RuntimeError):
                self.claim(record)
        self.assertFalse(PDAOIDClaim.objects.exists())
        claim = self.claim(record)
        with patch.object(pdao_services, 'record_event', side_effect=RuntimeError('Fictional audit failure')):
            with self.assertRaises(RuntimeError):
                self.submit(record, files=MultiValueDict({'voter_certificate': [upload()]}))
        claim.refresh_from_db()
        self.assertIsNone(claim.membership_intake_id)
        self.assertFalse(RegistrationIntake.objects.exists())
        self.assertFalse(RegistrationAttachment.objects.exists())
        self.assertEqual([p for p in Path(self.media.name).rglob('*') if p.is_file()], [])

    def test_http_buttons_prefill_consent_submission_and_duplicate_click(self):
        record = self.record()
        detail = reverse('membership:pdao_detail', args=[record.pk])
        url = reverse('membership:pdao_membership', args=[record.pk])
        before = self.client.get(detail)
        self.assertContains(before, 'Record ID as claimed')
        self.assertNotContains(before, 'Start Association Membership')
        self.client.post(reverse('membership:pdao_claim_id', args=[record.pk]),
            {'version': 2, 'pwd_number': '00-0000-000-0000123', 'confirmed': 'on'})
        self.assertContains(self.client.get(detail), 'Start Association Membership')
        page = self.client.get(url)
        self.assertContains(page, 'name="membership_requested"')
        self.assertContains(page, 'PDAO disability record')
        self.assertTrue(page.context['form'].fields['first_name'].disabled)
        self.assertIn('no-store', page['Cache-Control'])
        response = self.client.post(url, association_data() | {
            'context_id': page.context['context_id'], 'membership_requested': 'on'})
        intake = RegistrationIntake.objects.get()
        self.assertRedirects(response, reverse('membership:registration_detail', args=[intake.reference]),
                             fetch_redirect_response=False)
        self.assertContains(self.client.get(detail), 'Open membership application')
        self.assertNotContains(self.client.get(detail), 'Start Association Membership')
        self.assertRedirects(self.client.get(url), response.url, fetch_redirect_response=False)
        self.assertRedirects(self.client.post(url, {}), response.url, fetch_redirect_response=False)
        self.assertEqual(RegistrationIntake.objects.count(), 1)

    def test_private_permissions_csrf_and_session_binding(self):
        record = self.record()
        url = reverse('membership:pdao_membership', args=[record.pk])
        claim_url = reverse('membership:pdao_claim_id', args=[record.pk])
        self.assertEqual(Client().get(url).status_code, 302)
        viewer = get_user_model().objects.create_user('fictional_pdao_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', pdao_services.VIEW)
        client = Client()
        client.force_login(viewer)
        self.assertEqual(client.get(url).status_code, 403)
        self.assertEqual(client.post(claim_url,
            {'version': 2, 'pwd_number': '123', 'confirmed': 'on'}).status_code, 403)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.actor)
        self.assertEqual(protected.post(claim_url, {}).status_code, 403)
        self.claim(record)
        self.assertEqual(protected.post(url, {}).status_code, 403)
        self.assertEqual(self.client.get(claim_url).status_code, 405)
        context = intake_services.issue_context('wrong-session', user=self.actor, channel='walk_in')
        with self.assertRaises(PermissionDenied):
            self.submit(record, context=context)
        self.assertFalse(RegistrationIntake.objects.exists())

    def test_claim_identity_is_immutable_and_link_must_be_complete(self):
        claim = self.claim(self.record())
        with registration_write():
            with self.assertRaises(PermissionDenied):
                claim.save(update_fields=['pwd_number'])
            claim.membership_started_at = timezone.now()
            with self.assertRaises(IntegrityError), transaction.atomic():
                claim.save(update_fields=['membership_intake', 'membership_started_at', 'membership_started_by'])

    def test_both_membership_entry_forms_require_disability_and_four_ps(self):
        for form_class in (OnlineRegistrationForm, OnsiteRegistrationForm):
            for name in ('four_ps_member', 'disability_type'):
                for value in ('', 'not-a-choice'):
                    form = form_class(association_data() | {name: value}, policy=policy_for('staff'))
                    with self.subTest(form=form_class, field=name, value=value):
                        self.assertFalse(form.is_valid())
                        self.assertIn(name, form.errors)
            for answer in ('Yes', 'No'):
                form = form_class(association_data() | {'four_ps_member': answer}, policy=policy_for('staff'))
                self.assertTrue(form.is_valid(), form.errors)

    def test_new_postgres_table_keeps_server_only_row_security(self):
        if connection.vendor != 'postgresql':
            self.skipTest('PostgreSQL deployment policy.')
        from django.apps import apps
        with connection.cursor() as cursor:
            for role in ('santolan_app', 'anon', 'authenticated'):
                cursor.execute(f'CREATE ROLE {role} NOLOGIN')
            cursor.execute('GRANT ALL ON membership_pdaoidclaim TO anon, authenticated')
        with connection.schema_editor() as editor:
            import_module('membership.migrations.0016_pdao_claim_membership').protect_claims(apps, editor)
        with connection.cursor() as cursor:
            cursor.execute("SELECT relrowsecurity FROM pg_class WHERE oid = 'membership_pdaoidclaim'::regclass")
            self.assertTrue(cursor.fetchone()[0])
            cursor.execute("SELECT roles FROM pg_policies WHERE tablename = 'membership_pdaoidclaim'")
            self.assertEqual(cursor.fetchone()[0], ['santolan_app'])
            for role, expected in (('anon', False), ('authenticated', False), ('santolan_app', True)):
                cursor.execute("SELECT has_table_privilege(%s, 'membership_pdaoidclaim', 'SELECT')", [role])
                self.assertEqual(cursor.fetchone()[0], expected)


@override_settings(PDAO_REGISTRATION_ENABLED=True, ASSOCIATION_REGISTRATION_POLICY=pdf_policy())
class PDAOToMembershipConcurrencyTests(TransferHelpers, TransactionTestCase):
    def test_two_staff_submissions_create_one_linked_intake(self):
        self.setup_transfer()
        record = self.record()
        self.claim(record)
        contexts = [intake_services.issue_context(self.binding, user=self.actor, channel='walk_in') for _ in range(2)]
        barrier = Barrier(2)

        def run(context):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return self.submit(record, context=context).pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(2) as pool:
            results = list(pool.map(run, contexts))
        self.assertEqual(results[0], results[1])
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(record.events.filter(action='membership_started').count(), 1)
