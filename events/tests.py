from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch
import uuid
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections, IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from announcements.tests import image_upload
from members.tests import create_member
from membership.tests import grant
from .forms import EventForm
from .models import Event, EventLog, EventRegistration, VerificationWindow
from .services import (VERIFICATION_FAILED, change_publication, change_registration, normalize_name,
                       normalize_phone, register_member, reserve_verification, save_event)


def event_data(**overrides):
    now = timezone.now().replace(second=0, microsecond=0)
    return {'title': 'Community gathering', 'description': 'A synthetic community activity.', 'location': 'Test venue',
        'starts_at': now + timedelta(days=2), 'ends_at': now + timedelta(days=2, hours=2),
        'registration_opens_at': now - timedelta(days=1), 'registration_closes_at': now + timedelta(days=1),
        'event_category': 'general', 'target_audience': 'Community members', 'who_may_participate': 'Everyone, subject to the organizer rules.',
        'capacity': 2, 'version': 0, 'image_alt': '', 'notes': 'Reviewed correction.', **overrides}


def create_event(**overrides):
    data = event_data(event_category='', **overrides) if 'event_category' not in overrides else event_data(**overrides)
    data.pop('notes', None)
    return Event.objects.create(**data, status='published', published_at=timezone.now())


def verification(member, event):
    return {'version': event.version, 'control_number': member.control_number, 'full_name': member.full_name,
            'birthdate': date.fromisoformat(member.birthdate) if isinstance(member.birthdate, str) else member.birthdate,
            'contact_number': member.contact_number}


def historical_registration(event, member):
    """Seed a preserved legacy record, without invoking the retired intake."""
    record = EventRegistration.objects.create(event=event, member=member)
    EventLog.objects.create(event=event, registration=record, action='registered',
                            notes='Active member verified and registered.')
    return record


class EventWorkflowTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.override = override_settings(MEDIA_ROOT=self.media.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.admin = get_user_model().objects.create_superuser('event_admin', password='test-only-password')
        self.viewer = get_user_model().objects.create_user('event_viewer', is_staff=True)
        grant(self.viewer, 'accounts.access_dashboard', 'events.view_event')
        self.member = create_member('EVENT-001')
        self.member.contact_number = '09171234567'
        self.member.save()
        self.member.refresh_from_db()
        self.event = create_event()
        self.detail = reverse('events:detail', args=[self.event.pk]) + '?popup=1'
        self.register = reverse('events:register', args=[self.event.pk])
        self.manage = reverse('events:manage_detail', args=[self.event.pk])
        self.payload = verification(self.member, self.event)

    def test_draft_creation_ignores_forged_publication_and_actor(self):
        item = save_event(user=self.admin, data=event_data(status='published', created_by=self.viewer.pk))
        self.assertEqual(item.status, 'draft')
        self.assertEqual(item.created_by, self.admin)
        self.assertEqual(item.history.get().action, 'created')
        self.assertEqual(self.client.get(reverse('events:detail', args=[item.pk])).status_code, 404)

    def test_publication_withdrawal_cancellation_archive_and_images(self):
        item = save_event(user=self.admin, data=event_data(image_alt='Synthetic image'), files=MultiValueDict({'image': [image_upload()]}))
        for action, status_code in [('published', 200), ('cancelled', 200), ('draft', 404), ('published', 200), ('archived', 404)]:
            item = change_publication(item.pk, user=self.admin, version=item.version, action=action, notes='Reviewed event status.')
            for route in ('events:detail', 'events:image'):
                response = self.client.get(reverse(route, args=[item.pk]), {'popup': '1'} if route == 'events:detail' else {})
                self.assertEqual(response.status_code, status_code)
                if status_code == 200:
                    self.assertIn('no-store', response['Cache-Control'])
                if response.streaming:
                    b''.join(response.streaming_content)
            if action == 'cancelled':
                self.assertContains(self.client.get(reverse('events:detail', args=[item.pk]), {'popup': '1'}), 'This event has been cancelled.')

    def test_future_publication_is_private(self):
        self.event.published_at = timezone.now() + timedelta(days=1)
        self.event.save()
        self.assertEqual(self.client.get(self.detail).status_code, 404)
        self.assertEqual(self.client.post(self.register, self.payload).status_code, 410)

    def test_schedule_and_capacity_validation(self):
        self.assertFalse(EventForm(event_data(ends_at=self.event.starts_at), instance=self.event).is_valid())
        self.event.refresh_from_db()
        # Capacity is no longer editable; forged values are ignored, while
        # the database still protects historical capacity values.
        self.assertTrue(EventForm(event_data(capacity=0), instance=self.event).is_valid())
        with transaction.atomic(), self.assertRaises(IntegrityError):
            Event.objects.filter(pk=self.event.pk).update(capacity=0)

    def test_rescheduling_preserves_retired_registration_dates(self):
        updated = save_event(user=self.admin, pk=self.event.pk, data=event_data(
            starts_at=timezone.now()-timedelta(hours=1), ends_at=timezone.now()+timedelta(hours=1)))
        self.assertEqual(updated.registration_closes_at, self.event.registration_closes_at)

    def test_normalization_is_conservative_and_matches_confirmed_policy(self):
        self.assertEqual(normalize_name('  JUAN   Dela\tCruz '), 'juan dela cruz')
        self.assertEqual(normalize_phone('+63 (917) 123-4567'), '09171234567')
        self.assertNotEqual(normalize_name('Jose'), normalize_name('Jos\u00e9'))
        self.assertIsNone(normalize_phone('0917INVALID1234567'))
        self.assertIsNone(normalize_phone('0917+1234567'))

    def test_retired_service_rejects_all_identity_payloads(self):
        for change in ({}, {'control_number': 'UNKNOWN'}, {'full_name': 'Wrong'}):
            with self.assertRaisesMessage(ValidationError, 'Program Application'):
                register_member(self.event.pk, **{**self.payload, **change})
        self.assertFalse(EventRegistration.objects.exists())

    def test_open_events_do_not_require_member_verification(self):
        self.member.is_active = False
        self.member.save()
        response = self.client.get(self.detail)
        self.assertContains(response, 'Who May Participate')
        self.assertContains(response, 'Everyone, subject to the organizer rules.')
        self.assertNotContains(response, 'Control Number')

    def test_retired_route_does_not_lookup_or_expose_member_identity(self):
        for value in (self.member.control_number, 'UNKNOWN'):
            response = self.client.post(self.register, {**self.payload, 'control_number': value})
            self.assertEqual(response.status_code, 410)
            self.assertNotIn(self.member.full_name, response.content.decode())

    def test_legacy_registration_dates_never_reenable_registration(self):
        for point in (self.event.registration_opens_at, self.event.registration_closes_at):
            with patch('events.services.timezone.now', return_value=point):
                with self.assertRaises(ValidationError):
                    register_member(self.event.pk, **self.payload)
        self.assertFalse(self.event.registration_available)

    def test_historical_capacity_and_cancellation_remain_enforced(self):
        self.event.capacity = 1
        self.event.save()
        first = historical_registration(self.event, self.member)
        change_registration(first.pk, user=self.admin, version=0, status='cancelled', notes='Historical correction.')
        historical_registration(self.event, create_member('EVENT-002'))
        with self.assertRaisesMessage(ValidationError, 'No slot'):
            change_registration(first.pk, user=self.admin, version=1, status='registered', notes='Requested restoration.')
        self.assertEqual(EventRegistration.objects.count(), 2)

    def test_restoration_requires_active_member_and_published_event(self):
        registration = historical_registration(self.event, self.member)
        change_registration(registration.pk, user=self.admin, version=0, status='cancelled', notes='Cancellation.')
        self.member.is_active = False
        self.member.save()
        with self.assertRaisesMessage(ValidationError, 'active member'):
            change_registration(registration.pk, user=self.admin, version=1, status='registered', notes='Restore.')
        self.member.is_active = True
        self.member.save()
        self.event.status = 'archived'
        self.event.save()
        with self.assertRaisesMessage(ValidationError, 'published event'):
            change_registration(registration.pk, user=self.admin, version=1, status='registered', notes='Restore.')

    def test_attendance_timing_corrections_reasons_and_versions(self):
        registration = historical_registration(self.event, self.member)
        with self.assertRaisesMessage(ValidationError, 'after the event starts'):
            change_registration(registration.pk, user=self.admin, version=0, status='attended', notes='Too early.')
        for bad in [{'status': 'invalid', 'notes': 'Invalid.'}, {'status': 'confirmed', 'notes': ''}]:
            with self.assertRaises(ValidationError):
                change_registration(registration.pk, user=self.admin, version=0, **bad)
        registration = change_registration(registration.pk, user=self.admin, version=0, status='confirmed', notes='Confirmed participation.')
        with patch('events.services.timezone.now', return_value=self.event.starts_at):
            registration = change_registration(registration.pk, user=self.admin, version=1, status='attended', notes='Present at venue.')
            registration = change_registration(registration.pk, user=self.admin, version=2, status='absent', notes='Corrected mistaken attendance.')
        self.assertEqual(registration.history.count(), 4)
        self.assertEqual(registration.history.first().changes['status'], {'before': 'attended', 'after': 'absent'})
        with self.assertRaisesMessage(ValidationError, 'changed'):
            change_registration(registration.pk, user=self.admin, version=0, status='cancelled', notes='Stale form.')

    def test_historical_attendance_changes_roll_back_if_audit_fails(self):
        registration = historical_registration(self.event, self.member)
        with patch('events.services.record_log', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                change_registration(registration.pk, user=self.admin, version=0, status='cancelled', notes='Cancel.')
        registration.refresh_from_db()
        self.assertEqual(registration.status, 'registered')

    def test_member_event_and_registration_history_are_protected(self):
        registration = historical_registration(self.event, self.member)
        for item in (registration, self.member, self.event):
            with self.assertRaises(ProtectedError):
                item.delete()

    def test_services_require_separate_capabilities(self):
        for user in (AnonymousUser(), self.viewer):
            with self.assertRaises(PermissionDenied):
                save_event(user=user, data=event_data())
            with self.assertRaises(PermissionDenied):
                change_publication(self.event.pk, user=user, version=0, action='archived', notes='Archive.')
        grant(self.viewer, 'events.add_event', 'events.change_event')
        self.viewer = get_user_model().objects.get(pk=self.viewer.pk)
        draft = save_event(user=self.viewer, data=event_data())
        self.assertEqual(draft.status, 'draft')
        with self.assertRaises(PermissionDenied):
            save_event(user=self.viewer, data=event_data(), pk=self.event.pk)
        registration = historical_registration(self.event, self.member)
        with self.assertRaises(PermissionDenied):
            change_registration(registration.pk, user=self.viewer, version=0, status='confirmed', notes='Confirm.')

    def test_private_routes_and_separate_history_and_attendance_permissions(self):
        registration = historical_registration(self.event, self.member)
        attendance = reverse('events:registration_detail', args=[self.event.pk, registration.pk])
        for route in (self.manage, reverse('events:manage_list'), reverse('events:registrations', args=[self.event.pk]), attendance):
            self.assertEqual(self.client.get(route).status_code, 302)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.manage).status_code, 200)
        self.assertEqual(self.client.get(attendance).status_code, 403)
        self.assertEqual(self.client.post(self.manage, {'action': 'archived'}).status_code, 403)
        grant(self.viewer, 'events.view_eventregistration')
        self.assertNotContains(self.client.get(attendance), 'Active member verified and registered.')
        self.assertEqual(self.client.post(attendance, {'status': 'confirmed'}).status_code, 403)
        grant(self.viewer, 'events.view_eventlog')
        self.assertContains(self.client.get(attendance), 'Active member verified and registered.')

    def test_registration_detail_rejects_wrong_event(self):
        registration = historical_registration(self.event, self.member)
        another = create_event(title='Another')
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('events:registration_detail', args=[another.pk, registration.pk])).status_code, 404)

    def test_csrf_confirmation_and_get_do_not_change_state(self):
        csrf = Client(enforce_csrf_checks=True)
        self.assertEqual(csrf.post(self.register, self.payload).status_code, 403)
        csrf.force_login(self.admin)
        self.assertEqual(csrf.post(self.manage, {'action': 'archived'}).status_code, 403)
        self.client.force_login(self.admin)
        self.client.get(self.manage + '?action=archived')
        self.client.post(self.manage, {'version': 0, 'action': 'archived', 'notes': 'Unconfirmed.'})
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, 'published')
        self.assertFalse(EventRegistration.objects.exists())

    def test_retired_registration_provides_no_new_receipt(self):
        self.assertEqual(self.client.post(self.register, self.payload).status_code, 410)
        self.assertFalse(EventRegistration.objects.exists())
        self.assertEqual(self.client.get(reverse('events:registered', args=[self.event.pk])).status_code, 410)

    def test_shared_identity_counter_still_hashes_keys_for_program_verification(self):
        self.assertTrue(reserve_verification(self.member.control_number, '192.0.2.9'))
        for key in VerificationWindow.objects.values_list('key', flat=True):
            self.assertEqual(len(key), 64)
            self.assertNotIn(self.member.control_number, key)

    def test_retired_route_does_not_create_verification_counters(self):
        for number in ('ONE', 'TWO'):
            self.assertEqual(self.client.post(self.register, {**self.payload, 'control_number': number}).status_code, 410)
        self.assertFalse(VerificationWindow.objects.exists())

    def test_public_events_use_observances_and_preserve_historical_events(self):
        draft = save_event(user=self.admin, data=event_data(title='Private draft'))
        past = create_event(title='Past gathering', starts_at=timezone.now()-timedelta(days=2), ends_at=timezone.now()-timedelta(days=1),
            registration_opens_at=timezone.now()-timedelta(days=4), registration_closes_at=timezone.now()-timedelta(days=3))
        self.assertContains(self.client.get('/events/'), self.event.title)
        self.assertNotContains(self.client.get('/events/'), past.title)
        self.assertContains(self.client.get('/events/?period=past'), past.title)
        # Home features only an event happening now; upcoming events remain here.
        self.assertNotContains(self.client.get('/'), self.event.title)
        self.assertContains(self.client.get('/'), 'No event happening now')
        self.assertNotContains(self.client.get('/'), draft.title)
        self.assertEqual(Event.objects.filter(pk__in=[self.event.pk, past.pk, draft.pk]).count(), 3)

    def test_search_filter_pagination_and_member_history(self):
        registration = historical_registration(self.event, self.member)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get('/events/manage/?q=Community&status=published'), self.event.title)
        missing = self.client.get('/events/manage/?q=missing')
        self.assertEqual(list(missing.context['page_obj']), [])
        self.assertContains(missing, 'No events found')
        # The next-event operations card is independent of the filtered agenda.
        roster = reverse('events:registrations', args=[self.event.pk])
        self.assertContains(self.client.get(roster + '?q=EVENT-001'), self.member.full_name)
        self.assertNotContains(self.client.get(roster + '?status=cancelled'), self.member.full_name)
        # Retired registrations remain in the permission-checked history context;
        # the redesigned member activity section no longer lists these as attendance.
        record = self.client.get(reverse('members:detail', args=[self.member.pk]))
        self.assertEqual(list(record.context['event_history']), [registration])
        grant(self.viewer, 'members.view_member')
        self.client.force_login(self.viewer)
        record = self.client.get(reverse('members:detail', args=[self.member.pk]))
        self.assertIsNone(record.context['event_history'])
        self.assertNotContains(record, self.event.title)
        for i in range(21):
            create_event(title=f'Activity {i}')
        self.assertEqual(len(self.client.get('/events/manage/').context['page_obj']), 20)
        self.assertEqual(len(self.client.get('/events/manage/?page=2').context['page_obj']), 2)

    def test_xss_and_public_member_privacy(self):
        self.event.title = '<script>alert(1)</script>'
        self.event.description = '<img src=x onerror=alert(1)>'
        self.event.save()
        historical_registration(self.event, self.member)
        response = self.client.get(self.detail)
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, self.event.description)
        for private in (self.member.full_name, self.member.control_number, self.member.contact_number):
            self.assertNotContains(response, private)

    def test_edit_preserves_registrations_ignores_hidden_capacity_and_rejects_stale_version(self):
        historical_registration(self.event, self.member)
        second = create_member('EVENT-002')
        historical_registration(self.event, second)
        updated = save_event(user=self.admin, pk=self.event.pk, data=event_data(title='Updated gathering', capacity=1))
        self.assertEqual(updated.capacity, self.event.capacity)
        self.assertEqual(updated.registrations.count(), 2)
        with self.assertRaisesMessage(ValidationError, 'changed'):
            save_event(user=self.admin, pk=updated.pk, data=event_data())
        with self.assertRaisesMessage(ValidationError, 'changed'):
            change_publication(updated.pk, user=self.admin, version=0, action='archived', notes='Stale.')

    def test_image_validation_alt_text_reencoding_and_missing_image(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.assertTrue(EventForm(event_data(), MultiValueDict({'image': [image_upload()]})).is_valid())
        invalid = [SimpleUploadedFile('fake.png', b'not an image', content_type='image/png')]
        for image in invalid:
            self.assertFalse(EventForm(event_data(), MultiValueDict({'image': [image]})).is_valid())
        item = save_event(user=self.admin, data=event_data(image_alt='Image description'), files=MultiValueDict({'image': [image_upload()]}))
        with item.image.open('rb') as file:
            self.assertTrue(file.read().startswith(b'\x89PNG'))
        self.assertEqual(self.client.get(item.image.url).status_code, 404)
        item.image.storage.delete(item.image.name)
        with self.assertRaisesMessage(ValidationError, 'missing image'):
            change_publication(item.pk, user=self.admin, version=item.version, action='published', notes='Publish.')

    def test_event_image_rollback_replacement_and_removal_cleanup(self):
        from pathlib import Path
        with patch('events.services.record_log', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                save_event(user=self.admin, data=event_data(image_alt='Image'), files=MultiValueDict({'image': [image_upload()]}))
        self.assertFalse(any(path.is_file() for path in Path(self.media.name).rglob('*')))
        item = save_event(user=self.admin, data=event_data(image_alt='Image'), files=MultiValueDict({'image': [image_upload()]}))
        previous = item.image.name
        with self.captureOnCommitCallbacks(execute=True):
            item = save_event(user=self.admin, pk=item.pk, data=event_data(version=item.version, image_alt='Replacement'),
                              files=MultiValueDict({'image': [image_upload()]}))
        self.assertFalse(item.image.storage.exists(previous))
        previous = item.image.name
        with self.captureOnCommitCallbacks(execute=True):
            item = save_event(user=self.admin, pk=item.pk, data=event_data(version=item.version, remove_image=True))
        self.assertFalse(item.image.storage.exists(previous))
        self.assertFalse(item.image)

    @override_settings(EVENT_IMAGE_MAX_BYTES=1)
    def test_event_specific_image_limits_and_extra_uploads(self):
        form = EventForm(event_data(image_alt='Image'), MultiValueDict({'image': [image_upload()]}))
        self.assertFalse(form.is_valid())
        self.assertIn('image', form.errors)
        form = EventForm(event_data(), MultiValueDict({'unlisted': [image_upload()]}))
        self.assertFalse(form.is_valid())

    def test_event_cancellation_blocks_new_registration_without_erasing_history(self):
        registration = historical_registration(self.event, self.member)
        item = change_publication(self.event.pk, user=self.admin, version=0, action='cancelled', notes='Activity cancelled.')
        second = create_member('EVENT-002')
        with self.assertRaisesMessage(ValidationError, 'Program Application'):
            register_member(item.pk, **verification(second, item))
        registration.refresh_from_db()
        self.assertEqual(registration.status, 'registered')
        self.assertEqual(item.registrations.count(), 1)
        self.assertEqual(registration.history.count(), 1)

    def test_publication_rolls_back_if_audit_fails(self):
        with patch('events.services.record_log', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                change_publication(self.event.pk, user=self.admin, version=0, action='archived', notes='Archive.')
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, 'published')

    def test_expired_counter_cleanup_preserves_recent_counters(self):
        from django.core.management import call_command
        from io import StringIO
        VerificationWindow.objects.create(key='a'*64, started_at=timezone.now()-timedelta(days=1))
        VerificationWindow.objects.create(key='b'*64, started_at=timezone.now())
        call_command('purge_event_verification_windows', stdout=StringIO())
        self.assertEqual(list(VerificationWindow.objects.values_list('key', flat=True)), ['b'*64])


class EventConcurrencyTests(TransactionTestCase):
    def run_parallel(self, tasks):
        barrier = Barrier(len(tasks))
        def run(task):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return str(task().pk)
                except ValidationError:
                    return 'blocked'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
            return list(pool.map(run, tasks))

    def test_concurrent_last_slot_does_not_overbook(self):
        item = create_event(capacity=1)
        first, second = create_member('CONCURRENT-1'), create_member('CONCURRENT-2')
        results = self.run_parallel([lambda: register_member(item.pk, **verification(first, item)),
                                     lambda: register_member(item.pk, **verification(second, item))])
        self.assertEqual(results.count('blocked'), 2)
        self.assertEqual(item.registrations.count(), 0)

    def test_concurrent_duplicate_creates_one_registration_and_audit(self):
        item, member = create_event(capacity=1), create_member('CONCURRENT')
        results = self.run_parallel([lambda: register_member(item.pk, **verification(member, item))] * 2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(results, ['blocked', 'blocked'])
        self.assertEqual(item.registrations.count(), 0)
        self.assertEqual(item.history.count(), 0)

    def test_restoration_and_new_registration_share_capacity_lock(self):
        item = create_event(capacity=1)
        first, second = create_member('RESTORE-1'), create_member('RESTORE-2')
        admin = get_user_model().objects.create_superuser('concurrency_admin')
        registration = historical_registration(item, first)
        change_registration(registration.pk, user=admin, version=0, status='cancelled', notes='Cancelled.')
        results = self.run_parallel([
            lambda: change_registration(registration.pk, user=admin, version=1, status='registered', notes='Restore.'),
            lambda: register_member(item.pk, **verification(second, item))])
        self.assertEqual(results.count('blocked'), 1)
        self.assertEqual(item.registrations.exclude(status='cancelled').count(), 1)
