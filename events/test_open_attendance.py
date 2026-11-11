from datetime import timedelta
from unittest.mock import patch
import uuid

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from members.tests import create_member
from membership.tests import grant
from .models import EventAttendance, EventAttendanceLog
from .services import save_attendance
from programs.testsupport import private_media, application_fixture
from programs.tests import create_program
from . import tests as event_tests
from .tests import create_event, historical_registration


def attendance_data(**overrides):
    return {'submission_key': str(uuid.uuid4()), 'version': 0, 'attendee_name': 'Synthetic visitor',
            'member': '', 'status': 'attended', 'notes': 'Observed at the venue.', **overrides}


class OpenAttendanceTests(TestCase):
    def setUp(self):
        private_media(self)
        self.officer = get_user_model().objects.create_user('attendance_officer', is_staff=True)
        grant(self.officer, 'accounts.access_dashboard', 'events.view_event', 'events.view_eventattendance',
              'events.add_eventattendance', 'events.change_eventattendance', 'events.view_eventattendancelog', 'members.view_member')
        self.event = create_event(starts_at=timezone.now()-timedelta(hours=1), ends_at=timezone.now()+timedelta(hours=1), capacity=1)
        self.member = create_member('ATTEND-SELECTED')
        self.program = create_program()
        application = application_fixture(self.program, self.member)
        application.status = 'SELECTED'
        application.save()
        self.event.application_program = self.program
        self.event.save()
        self.roster = reverse('events:attendance_list', args=[self.event.pk])
        self.create = reverse('events:attendance_create', args=[self.event.pk])
        self.client.force_login(self.officer)

    def save(self, data=None, **kwargs):
        data = data or attendance_data()
        if not data.get('member'):
            data = {**data, 'member': str(self.member.pk)}
        return save_attendance(self.event.pk, user=self.officer, data=data, **kwargs)

    def detail(self, item):
        return reverse('events:attendance_detail', args=[self.event.pk, item.pk])

    def test_nonmember_intake_has_atomic_audit_and_no_capacity_or_identity_gate(self):
        with self.assertRaises(ValidationError):
            save_attendance(self.event.pk, user=self.officer, data=attendance_data())
        self.assertFalse(EventAttendance.objects.exists())
        first = self.save(address='192.0.2.1')
        self.assertEqual(first.member, self.member)
        self.assertEqual(first.history.count(), 1)
        self.assertEqual(first.history.get().address, '192.0.2.1')

    def test_same_name_can_identify_distinct_people_but_same_submission_is_idempotent(self):
        data = attendance_data()
        first = self.save(data)
        self.assertEqual(self.save(data).pk, first.pk)
        self.assertEqual(first.history.count(), 1)
        self.save(attendance_data())
        self.assertEqual(self.event.attendance.count(), 2)
        with self.assertRaisesMessage(ValidationError, 'already been used'):
            self.save({**data, 'attendee_name': 'Changed request'})

    def test_member_link_allows_inactive_archived_members_and_does_not_replace_snapshot(self):
        self.member.is_active = False
        self.member.save()
        with self.assertRaises(ValidationError):
            self.save()
        legacy = EventAttendance.objects.create(event=self.event, member=self.member, attendee_name='Historical attendee', status='attended')
        updated = self.save(attendance_data(submission_key=str(legacy.pk), version=0, status='absent'), reference=legacy.pk)
        self.assertEqual(updated.member, self.member)
        self.assertEqual(updated.status, 'absent')

    def test_member_directory_requires_permission_even_for_forged_posts(self):
        self.officer.user_permissions.remove(*self.officer.user_permissions.filter(codename='view_member'))
        self.officer = get_user_model().objects.get(pk=self.officer.pk)
        member = create_member('PRIVATE-LINK')
        response = self.client.get(self.create)
        self.assertNotContains(response, 'id_member')
        self.assertNotContains(response, member.full_name)
        with self.assertRaises(PermissionDenied):
            self.save(attendance_data(member=str(member.pk)))
        self.assertEqual(self.client.post(self.create, attendance_data(member=str(member.pk))).status_code, 403)
        self.assertFalse(EventAttendance.objects.exists())

    def test_staff_without_directory_access_can_correct_record_without_erasing_link(self):
        item = self.save()
        self.officer.user_permissions.remove(*self.officer.user_permissions.filter(codename='view_member'))
        self.officer = get_user_model().objects.get(pk=self.officer.pk)
        updated = save_attendance(self.event.pk, user=self.officer, reference=item.pk,
            data=attendance_data(submission_key=str(item.pk), version=item.version, attendee_name='Corrected historical name'))
        self.assertEqual(updated.member, self.member)

    def test_corrections_record_deltas_and_reject_stale_versions_and_noops(self):
        item = self.save()
        data = attendance_data(submission_key=str(item.pk), version=item.version, status='absent', notes='Corrected a mistaken entry.')
        changed = self.save(data, reference=item.pk)
        self.assertEqual(changed.version, 2)
        self.assertEqual(changed.history.count(), 2)
        self.assertEqual(changed.history.first().changes, {'status': {'before': 'attended', 'after': 'absent'}})
        with self.assertRaisesMessage(ValidationError, 'changed'):
            self.save(data, reference=item.pk)
        with self.assertRaisesMessage(ValidationError, 'before saving'):
            self.save({**data, 'version': changed.version}, reference=item.pk)

    def test_validation_timing_and_unpublished_cancelled_states(self):
        for changes in [{'attendee_name': ''}, {'notes': ''}, {'status': 'registered'}, {'version': 3},
                        {'submission_key': 'invalid'}, {'attendee_name': 'x'*201}]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.save(attendance_data(**changes))
        for state in ('draft', 'cancelled'):
            self.event.status = state
            self.event.save()
            with self.assertRaisesMessage(ValidationError, 'Publish'):
                self.save()
        self.event.status = 'published'
        self.event.starts_at = timezone.now()+timedelta(minutes=20)
        self.event.ends_at = self.event.starts_at+timedelta(hours=1)
        self.event.save()
        with self.assertRaisesMessage(ValidationError, 'after the event starts'):
            self.save()
        with patch('events.services.timezone.now', return_value=self.event.starts_at):
            self.save()

    def test_create_and_correction_roll_back_when_audit_fails(self):
        with patch('events.services.record_attendance_log', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                self.save()
        self.assertFalse(EventAttendance.objects.exists())
        item = self.save()
        with patch('events.services.record_attendance_log', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                self.save(attendance_data(submission_key=str(item.pk), version=1, status='absent'), reference=item.pk)
        item.refresh_from_db()
        self.assertEqual((item.status, item.version, item.history.count()), ('attended', 1, 1))

    def test_legacy_records_and_history_are_preserved_and_not_in_new_count(self):
        member = create_member('LEGACY-KEEP')
        legacy = historical_registration(self.event, member)
        before = list(legacy.history.values())
        item = self.save()
        self.save(attendance_data(submission_key=str(item.pk), version=1, status='absent'), reference=item.pk)
        self.assertEqual(list(legacy.history.values()), before)
        legacy.refresh_from_db()
        self.assertEqual((legacy.status, legacy.version), ('registered', 0))
        response = self.client.get(self.roster)
        self.assertEqual(response.context['attended_count'], 0)
        self.assertEqual(response.context['page_obj'].paginator.count, 1)

    def test_separate_view_add_change_and_history_permissions(self):
        viewer = get_user_model().objects.create_user('attendance_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'events.view_event')
        item = self.save()
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.roster).status_code, 403)
        grant(viewer, 'events.view_eventattendance')
        self.assertContains(self.client.get(self.detail(item)), 'Synthetic visitor')
        self.assertNotContains(self.client.get(self.detail(item)), 'Observed at the venue.')
        self.assertNotContains(self.client.get(self.detail(item)), 'Save attendance correction')
        self.assertEqual(self.client.get(self.create).status_code, 403)
        self.assertEqual(self.client.post(self.detail(item), attendance_data()).status_code, 403)
        for user in (AnonymousUser(), viewer):
            with self.assertRaises(PermissionDenied):
                save_attendance(self.event.pk, user=user, data=attendance_data())

    def test_private_routes_csrf_escaping_and_public_flow(self):
        item = self.save(attendance_data(attendee_name='<script>visitor</script>'))
        response = self.client.get(self.roster)
        self.assertContains(response, '&lt;script&gt;visitor&lt;/script&gt;')
        self.assertIn('no-store', response['Cache-Control'])
        visitor = Client(enforce_csrf_checks=True)
        for route in (self.roster, self.create, self.detail(item)):
            self.assertEqual(visitor.get(route).status_code, 302)
        visitor.force_login(self.officer)
        self.assertEqual(visitor.post(self.create, attendance_data()).status_code, 403)
        self.assertEqual(visitor.post(self.detail(item), attendance_data()).status_code, 403)
        response = self.client.get(reverse('events:detail', args=[self.event.pk]), {'popup': '1'})
        self.assertContains(response, self.event.who_may_participate)
        self.assertContains(response, 'Online applications for the linked program require verified Association membership.')
        self.assertNotContains(response, 'visitor')
        self.assertNotContains(response, 'Control Number')
        self.assertEqual(self.client.post(reverse('events:register', args=[self.event.pk]), {}).status_code, 410)

    def test_wrong_event_references_and_database_history_protection(self):
        item = self.save()
        other = create_event(title='Other event')
        self.assertEqual(self.client.get(reverse('events:attendance_detail', args=[other.pk, item.pk])).status_code, 404)
        for record in (item, self.event):
            with self.assertRaises(ProtectedError):
                record.delete()
        with transaction.atomic(), self.assertRaises(IntegrityError):
            EventAttendance.objects.filter(pk=item.pk).update(status='registered')

    def test_link_unlink_corrections_and_name_filter_pagination(self):
        item = self.save()
        with self.assertRaises(ValidationError):
            save_attendance(self.event.pk, user=self.officer, reference=item.pk,
                data=attendance_data(submission_key=str(item.pk), version=item.version, member='', status='absent'))
        self.save(attendance_data(submission_key=str(item.pk), version=item.version, status='absent'), reference=item.pk)
        self.assertEqual(self.client.get(self.roster+'?q=Synthetic&status=absent').context['page_obj'].paginator.count, 1)


class OpenAttendanceConcurrencyTests(TransactionTestCase):
    def setUp(self):
        private_media(self)
        self.member = create_member('RACE-ATTEND')
        self.program = create_program()
        app = application_fixture(self.program, self.member)
        app.status = 'SELECTED'
        app.save()

    run_parallel = event_tests.EventConcurrencyTests.run_parallel

    def test_retried_concurrent_form_creates_one_attendee_and_one_audit(self):
        item = create_event(starts_at=timezone.now()-timedelta(hours=1), application_program=self.program)
        admin = get_user_model().objects.create_superuser('open_concurrent')
        data = attendance_data(member=str(self.member.pk))
        results = self.run_parallel([lambda: save_attendance(item.pk, user=admin, data=data)]*2)
        self.assertEqual(results[0], results[1])
        self.assertEqual(EventAttendance.objects.count(), 1)
        self.assertEqual(EventAttendanceLog.objects.count(), 1)

    def test_concurrent_corrections_accept_only_one_current_version(self):
        event = create_event(starts_at=timezone.now()-timedelta(hours=1), application_program=self.program)
        admin = get_user_model().objects.create_superuser('open_edit_concurrent')
        item = save_attendance(event.pk, user=admin, data=attendance_data(member=str(self.member.pk)))
        results = self.run_parallel([lambda name=name: save_attendance(event.pk, user=admin, reference=item.pk,
            data=attendance_data(submission_key=str(item.pk), version=1, attendee_name=name, member=str(self.member.pk))) for name in ('First correction', 'Second correction')])
        self.assertEqual(results.count('blocked'), 1)
        self.assertEqual(EventAttendanceLog.objects.count(), 2)
