"""Reference aliases on a disposable MySQL database, using fictional records."""
import importlib
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import connection, connections, close_old_connections, transaction
from django.db.migrations.loader import MigrationLoader
from django.db.models import Q
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from assistance.test_referrals import Fixtures
from assistance.referral_models import ReferralEmail
from events.models import EventAttendance, EventRegistration
from events.tests import create_event
from membership import registration_services
from membership.test_pdao_registration import PDAOHelpers
from membership.test_pdf_registration import association_data, pdf_policy
from programs.models import ProgramApplication
from programs.tests import create_program
from programs.tracking_services import verify_application, reserve_tracking_attempt
from core.reference_models import ShortReference
from core.reference_services import (KINDS, allocate, display_reference, filter_reference,
    format_code, lookup_key, original_reference)


SETTINGS = dict(SHORT_REFERENCES_ENABLED=True, PDAO_REGISTRATION_ENABLED=True,
    ASSOCIATION_REGISTRATION_POLICY=pdf_policy(), REFERRAL_ENABLED=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')


class Records(Fixtures, PDAOHelpers):
    def make_records(self):
        binding = registration_services.binding_for('synthetic-alias-session')
        context = registration_services.issue_context(binding)
        association = registration_services.submit_registration(context.pk, binding, association_data())
        pdao, _ = PDAOHelpers.submit(self)
        program = create_program()
        application = ProgramApplication.objects.create(program=program, member=self.member,
            public_reference='SPA-ORIGINAL-ALIAS-TEST')
        event = create_event()
        registration = EventRegistration.objects.create(event=event, member=self.member)
        attendance = EventAttendance.objects.create(event=event, attendee_name='Fictional attendee')
        ticket = Fixtures.submit(self)
        return dict(association=association, membership=self.member.application, pdao=pdao,
            program=application, event=registration, attendance=attendance, referral=ticket)

    def originals(self, records):
        return {kind: str(getattr(record, KINDS[kind][2] or 'reference')) for kind, record in records.items()}


@override_settings(**SETTINGS)
class ShortReferenceTests(Records, TestCase):
    def test_every_service_gets_unique_code_and_original_references_remain_valid(self):
        records = self.make_records()
        originals = self.originals(records)
        self.assertEqual(ShortReference.objects.count(), 7)
        self.assertEqual(len({record.short_reference.split('-')[1] for record in records.values()}), 7)
        for kind, record in records.items():
            code = record.short_reference
            self.assertRegex(code, rf'^{KINDS[kind][0]}-[0-9]{{6,}}$')
            for query in (code, code.lower(), code.replace('-', ''), code.split('-')[1], str(int(code.split('-')[1]))):
                self.assertEqual(lookup_key(kind, query), str(record.pk))
                self.assertEqual(original_reference(kind, query), originals[kind])
            self.assertEqual(original_reference(kind, originals[kind]), originals[kind])
            self.assertEqual(display_reference(kind, originals[kind]), code)
            record.refresh_from_db()
            self.assertEqual(str(getattr(record, KINDS[kind][2] or 'reference')), originals[kind])
        self.assertEqual(format_code('program', 1000000), 'PRG-1000000')
        self.assertEqual(display_reference('membership', 'invalid reference'), 'invalid reference')
        with override_settings(SHORT_REFERENCES_ENABLED=False):
            for kind, record in records.items():
                self.assertEqual(record.short_reference, originals[kind])

    def test_codes_cannot_be_changed_deleted_or_reallocated(self):
        records = self.make_records()
        row = ShortReference.objects.get(kind='program')
        for action in (lambda: row.save(), lambda: row.delete(),
                       lambda: ShortReference.objects.filter(pk=row.pk).delete(),
                       lambda: ShortReference.objects.filter(pk=row.pk).update(object_key='forged')):
            with self.assertRaises(PermissionDenied):
                action()
        self.assertEqual(allocate(records['program']), row.code)
        self.assertEqual(ShortReference.objects.count(), 7)

    def test_new_record_and_alias_roll_back_together(self):
        event = create_event()
        before = ShortReference.objects.count()
        with self.assertRaises(RuntimeError), transaction.atomic():
            EventAttendance.objects.create(event=event, attendee_name='Rolled back')
            raise RuntimeError('Simulated audit failure')
        self.assertFalse(EventAttendance.objects.exists())
        self.assertEqual(ShortReference.objects.count(), before)
        with patch('core.reference_services.allocate', side_effect=RuntimeError('Alias unavailable')):
            with self.assertRaises(RuntimeError):
                EventAttendance.objects.create(event=event, attendee_name='Must not commit')
        self.assertFalse(EventAttendance.objects.exists())

    def test_short_and_original_searches_for_all_admin_lists_remain_permission_checked(self):
        records = self.make_records()
        originals = self.originals(records)
        urls = {
            'association': reverse('membership:registration_inbox'),
            'pdao': reverse('membership:pdao_inbox'),
            'program': reverse('programs:applications', args=[records['program'].program_id]),
            'event': reverse('events:registrations', args=[records['event'].event_id]),
            'attendance': reverse('events:attendance_list', args=[records['attendance'].event_id]),
            'referral': reverse('assistance:referral_inbox'),
        }
        self.client.force_login(self.admin)
        for kind, url in urls.items():
            record = records[kind]
            for query in (record.short_reference, record.short_reference.split('-')[1], originals[kind]):
                params = {'q': query}
                response = self.client.get(url, params)
                self.assertEqual(response.status_code, 200, (kind, query))
                page = response.context['page' if kind == 'referral' else 'page_obj']
                self.assertEqual(list(page), [record], (kind, query))
                self.assertContains(response, record.short_reference)
            self.assertEqual(Client().get(url, {'q': record.short_reference}).status_code, 302)
        self.client.force_login(self.viewer)
        for kind in ('association', 'pdao', 'program', 'event', 'attendance'):
            self.assertEqual(self.client.get(urls[kind], {'q': records[kind].short_reference}).status_code, 403)

        # The retired onsite list no longer resolves references, while the
        # immutable alias remains valid for the retained historical record.
        self.client.force_login(self.admin)
        legacy = records['membership']
        for query in (legacy.short_reference, originals['membership']):
            self.assertRedirects(self.client.get(reverse('membership:list'), {'reference': query}),
                                 reverse('membership:review_home'))
        self.assertEqual(lookup_key('membership', legacy.short_reference), str(legacy.pk))

    def test_program_scope_and_service_type_are_not_bypassed(self):
        records = self.make_records()
        app = records['program']
        other_program = create_program(name='Another fictional program')
        scoped = ProgramApplication.objects.filter(program=other_program)
        self.assertFalse(filter_reference(scoped, 'program', app.short_reference, Q()).exists())
        self.assertEqual(lookup_key('pdao', app.short_reference.split('-')[1]), '')
        self.assertIsNone(lookup_key('pdao', app.short_reference))
        self.client.force_login(self.admin)
        response = self.client.get(reverse('programs:applications', args=[other_program.pk]), {'q': app.short_reference})
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        for query in (app.short_reference, app.short_reference.split('-')[1], app.public_reference):
            response = self.client.get(reverse('programs:photo_queue'), {'q': query})
            self.assertEqual(list(response.context['page_obj']), [app])
            self.assertContains(response, app.short_reference)

    def test_program_alias_opens_limited_status_and_shares_rate_limits(self):
        app = self.make_records()['program']
        data = {'reference': app.short_reference}
        self.assertEqual(verify_application(data)['application'], str(app.pk))
        with patch('programs.tracking_services.reserve_windows', return_value=True) as reserve:
            reserve_tracking_attempt(app.short_reference, '127.0.0.1')
            short_limits = reserve.call_args
            reserve_tracking_attempt(app.public_reference, '127.0.0.1')
            self.assertEqual(short_limits, reserve.call_args)
        with override_settings(PROGRAM_TRACKING_ENABLED=True):
            response = Client().post(reverse('programs:tracking'), {'reference': app.short_reference}, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, self.member.full_name)

    def test_receipt_is_session_bound_and_generated_email_uses_short_code(self):
        records = self.make_records()
        pdao = records['pdao']
        self.assertContains(self.client.get(reverse('membership:pdao_receipt')), pdao.short_reference)
        self.assertEqual(Client().get(reverse('membership:pdao_receipt')).status_code, 404)
        job = ReferralEmail.objects.get(ticket=records['referral'])
        self.assertIn(records['referral'].short_reference, job.subject)
        self.assertIn(records['referral'].short_reference, job.body)


@override_settings(**(SETTINGS | {'SHORT_REFERENCES_ENABLED': False}))
class ShortReferenceMigrationTests(Records, TransactionTestCase):
    def test_backfill_all_seven_services_preserves_existing_rows_and_is_idempotent(self):
        self.assertTrue(connection.settings_dict['NAME'].startswith('test_'))
        self.assertNotEqual(connection.settings_dict['NAME'], 'santolan_pwd')
        records = self.make_records()
        snapshots = {kind: type(record).objects.filter(pk=record.pk).values().get() for kind, record in records.items()}
        module = importlib.import_module('core.migrations.0003_short_application_references')
        state = MigrationLoader(connection, ignore_no_migrations=True).project_state()
        state.remove_model('core', 'shortreference')
        migration = module.Migration('0003_short_application_references', 'core')
        with connection.schema_editor() as editor:
            editor.delete_model(ShortReference)  # New alias table only, on a disposable instance.
        try:
            with connection.schema_editor() as editor:
                updated = migration.apply(state, editor)
            self.assertEqual(ShortReference.objects.count(), 7)
            aliases = list(ShortReference.objects.order_by('pk').values())
            with connection.schema_editor() as editor:
                module.populate_codes(updated.apps, editor)
            self.assertEqual(list(ShortReference.objects.order_by('pk').values()), aliases)
            for kind, record in records.items():
                self.assertEqual(type(record).objects.filter(pk=record.pk).values().get(), snapshots[kind])
                with override_settings(SHORT_REFERENCES_ENABLED=True):
                    self.assertEqual(lookup_key(kind, record.short_reference), str(record.pk))
        finally:
            if ShortReference._meta.db_table not in connection.introspection.table_names():
                with connection.schema_editor() as editor:
                    editor.create_model(ShortReference)


@override_settings(SHORT_REFERENCES_ENABLED=True)
class ShortReferenceConcurrencyTests(TransactionTestCase):
    def test_concurrent_submissions_and_duplicate_allocation(self):
        event = create_event()
        barrier = Barrier(2)

        def submit(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return EventAttendance.objects.create(event_id=event.pk, attendee_name=f'Fictional {index}').short_reference
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = list(pool.map(submit, range(2)))
        self.assertEqual(len(set(codes)), 2)
        with override_settings(SHORT_REFERENCES_ENABLED=False):
            existing = EventAttendance.objects.create(event=event, attendee_name='Fictional existing')
        barrier = Barrier(2)

        def claim(index):
            close_old_connections()
            try:
                record = EventAttendance.objects.get(pk=existing.pk)
                barrier.wait(timeout=10)
                return allocate(record)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            codes = list(pool.map(claim, range(2)))
        self.assertEqual(codes[0], codes[1])
        self.assertEqual(ShortReference.objects.count(), 3)
