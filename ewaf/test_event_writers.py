"""Fictional linked-event integration and separate-connection MySQL evidence."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from threading import Event as Signal
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
from events import services
from events.forms import EventForm
from events.models import Event, EventLog, EventRegistration, EventAttendance
from events.tests import event_data, historical_registration
from members.tests import create_member
from membership.tests import grant
from programs.models import Program, ProgramApplication
from programs.tests import create_program
from programs.testsupport import application_fixture
from . import event_invalidation as adapter, generation_services as generation
from .generation_models import ProgramSourceState, SourceMutationBatch, SourceInvalidation, DevelopmentPromotion
from .test_source_writers import SourceHelpers
from .durable_testsupport import DurableHelpers


def draft_program():
    item = create_program()
    Program.objects.filter(pk=item.pk).update(status='draft', published_at=None)
    item.refresh_from_db()
    return item


class EventHelpers(SourceHelpers):
    def setup_event(self):
        self.setup_foundation()
        Program.objects.filter(pk=self.program.pk).update(status='draft', published_at=None)
        self.program.refresh_from_db()
        self.other = draft_program()
        self.event = services.save_event(user=self.officer,
            data=event_data(application_program=self.program.pk, image_alt='Fictional event image'),
            files=MultiValueDict({'image': [image_upload()]}))
        self.bootstrap([self.program.pk, self.other.pk])
        context = authority_services._disposable_authority_session(user=self.officer)
        context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)

    def tokens(self, *programs):
        return {str(p.pk): self.token(p) for p in programs or (self.program,)}

    def data(self, **overrides):
        self.event.refresh_from_db()
        return {**{field: getattr(self.event, field) for field in EventForm.Meta.fields if field not in ('image', 'application_program')},
            'application_program': self.event.application_program_id or '', 'version': self.event.version,
            'notes': 'Fictional reviewed event edit', **overrides}

    def save(self, *, expected=None, files=None, **overrides):
        return services.save_event(pk=self.event.pk, user=self.officer, data=self.data(**overrides),
            files=files, source_expected=self.tokens() if expected is None else expected)

    def publish(self, action='published', *, expected=None, **overrides):
        self.event.refresh_from_db()
        return services.change_publication(self.event.pk, **{'user': self.officer, 'version': self.event.version,
            'action': action, 'notes': 'Fictional publication review',
            'source_expected': self.tokens() if expected is None else expected, **overrides})

    def snapshot(self):
        return {m._meta.label: list(m.objects.order_by('pk').values()) for m in
            (Event, EventLog, Program, ProgramSourceState, SourceMutationBatch, SourceInvalidation,
             EventRegistration, EventAttendance)}

    def files(self):
        return {str(p.relative_to(settings.MEDIA_ROOT)): sha256(p.read_bytes()).hexdigest()
                for p in Path(settings.MEDIA_ROOT).rglob('*') if p.is_file()}

    def upload(self):
        return MultiValueDict({'image': [image_upload()]})

    def rollback(self, operation, target, replacement=None):
        before, files = self.snapshot(), self.files()
        context = patch(target, replacement) if replacement is not None else patch(target, side_effect=ValidationError('Fictional failure'))
        with context, self.assertRaises(ValidationError):
            operation()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(files, self.files())


class EventWriterTests(EventHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_event()

    def test_linked_creation_uses_existing_program_state(self):
        item = services.save_event(user=self.officer, data=event_data(application_program=self.other.pk), source_expected=self.tokens(self.other))
        state = ProgramSourceState.objects.get(program=self.other)
        self.assertEqual(state.generation, 2)
        self.assertEqual((state.last_invalidation.batch.source_kind, state.last_invalidation.batch.source_id), ('event', str(item.pk)))
        generation._validate_batch(state.last_invalidation.batch)
        self.assert_transition(1)

    def test_linked_edit_retains_exact_native_audit(self):
        self.save(title='Fictional corrected title')
        self.assert_transition(2)
        batch = ProgramSourceState.objects.get(program=self.program).last_invalidation.batch
        log = EventLog.objects.get(pk=batch.source_audits[0]['pk'])
        self.assertEqual(log.changes['title']['after'], 'Fictional corrected title')
        self.assertEqual(batch.source_audits[0]['model'], 'events.eventlog')

    def test_admin_local_datetime_strings_preserve_native_audit_spelling(self):
        start = timezone.localtime(self.event.starts_at)
        end = timezone.localtime(self.event.ends_at)
        self.save(starts_at=start.strftime('%Y-%m-%dT%H:%M'), ends_at=end.strftime('%Y-%m-%dT%H:%M'))
        self.assert_transition(2)
        log = self.event.history.first()
        self.assertTrue(log.changes['starts_at']['after'].endswith('+08:00'))

    def test_native_ipv6_address_normalization_preserved(self):
        services.save_event(pk=self.event.pk, user=self.officer, data=self.data(), source_expected=self.tokens(),
            address='2001:0db8:0000:0000:0000:0000:0000:0001')
        self.assertEqual(self.event.history.first().address, '2001:db8::1')
        self.assert_transition(2)

    def test_relink_invalidates_union_once_with_one_batch(self):
        self.save(application_program=self.other.pk, expected=self.tokens(self.program, self.other))
        states = list(ProgramSourceState.objects.order_by('program_id'))
        self.assertEqual([s.generation for s in states], [2, 2])
        self.assertEqual(len({s.last_invalidation.batch_id for s in states}), 1)
        self.assertEqual(states[0].last_invalidation.batch.scope_count, 2)

    def test_unlink_invalidates_old_program(self):
        self.save(application_program='')
        self.assert_transition(2)
        self.event.refresh_from_db()
        self.assertIsNone(self.event.application_program_id)

    def test_unlinked_creation_edit_and_publication_make_no_batch(self):
        before = SourceMutationBatch.objects.count()
        self.event = services.save_event(user=self.officer, data=event_data(), source_expected={})
        self.save(expected={}, title='Fictional unlinked edit')
        self.publish(expected={})
        self.assertEqual(SourceMutationBatch.objects.count(), before)
        self.assertEqual(self.event.history.count(), 3)

    def test_unlinked_to_linked_uses_proposed_program(self):
        self.event = services.save_event(user=self.officer, data=event_data(), source_expected={})
        self.save(application_program=self.other.pk, expected=self.tokens(self.other))
        self.assertEqual(ProgramSourceState.objects.get(program=self.other).generation, 2)
        self.assert_transition(1)

    def test_publication_cancellation_withdrawal_archive_preserved(self):
        program = list(Program.objects.filter(pk=self.program.pk).values())
        for action in ('published', 'cancelled', 'draft', 'published', 'archived'):
            self.publish(action)
        self.assert_transition(6)
        self.assertEqual(program, list(Program.objects.filter(pk=self.program.pk).values()))

    def test_invalid_status_and_unpublished_cancellation_rejected(self):
        for action in ('draft', 'cancelled', 'invalid'):
            with self.subTest(action=action), self.assertRaises(ValidationError):
                self.publish(action)
        self.assert_transition(1)

    def test_same_visible_values_still_retain_native_version_dependency(self):
        self.save()
        self.assert_transition(2)
        self.assertEqual(self.event.history.first().changes, {})

    def test_changed_then_restored_cannot_reuse_token(self):
        old = self.tokens()
        self.save(title='Fictional temporary title')
        self.save(title=self.event.title)
        with self.assertRaisesMessage(ValidationError, 'STALE_GENERATION'):
            self.save(expected=old)
        self.assert_transition(3)

    def test_incomplete_extra_and_malformed_scope_rejected(self):
        for expected in ({}, self.tokens(self.other), self.tokens(self.program, self.other), {str(self.program.pk): {}}):
            with self.subTest(expected=expected), self.assertRaises(ValidationError):
                self.save(expected=expected)
        with self.assertRaises(ValidationError):
            self.save(application_program=self.other.pk, expected=self.tokens())
        self.assert_transition(1)

    def test_missing_source_state_denied(self):
        third = draft_program()
        with self.assertRaisesMessage(ValidationError, 'SOURCE_STATE_NOT_INITIALIZED'):
            self.save(application_program=third.pk, expected={**self.tokens(), str(third.pk): self.token()})
        self.assert_transition(1)

    def test_invalid_link_and_stale_event_version_denied(self):
        for data in ({'application_program': 'invalid'}, {'version': 0}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                self.save(**data)
        with self.assertRaises(ValidationError):
            self.publish(version=0)
        self.assert_transition(1)

    def test_fresh_actor_permission_recheck(self):
        expected = self.tokens()
        get_user_model().objects.filter(pk=self.officer.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied):
            self.save(expected=expected)
        with self.assertRaises(PermissionDenied):
            self.publish(expected=expected)

    def test_all_token_fields_checked(self):
        for field, value in (('source_generation', 99), ('authority_generation', 99), ('revision', 99), ('current_binding', 99)):
            token = self.tokens(); token[str(self.program.pk)][field] = value
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.save(expected=token)
        self.assert_transition(1)

    def test_actor_without_program_permission_preserves_existing_link(self):
        user = get_user_model().objects.create_user('fictional_event_editor', is_staff=True)
        grant(user, 'accounts.access_dashboard', 'events.view_event', 'events.change_event')
        data = self.data(title='Fictional restricted edit'); data.pop('application_program')
        result = services.save_event(pk=self.event.pk, user=user, data=data, source_expected=self.tokens())
        self.assertEqual(result.application_program_id, self.program.pk)
        data['application_program'] = str(self.other.pk)
        with self.assertRaises(PermissionDenied):
            services.save_event(pk=self.event.pk, user=user, data=data, source_expected=self.tokens())

    def test_protected_terms_prevent_edit_relink_and_unlink(self):
        Program.objects.filter(pk=self.program.pk).update(status='published', published_at=timezone.now())
        for values in ({'title': 'Forbidden revision'}, {'application_program': ''}, {'application_program': self.other.pk}):
            expected = self.tokens(self.program, self.other) if values.get('application_program') else self.tokens()
            with self.subTest(values=values), self.assertRaisesMessage(ValidationError, 'protected'):
                self.save(expected=expected, **values)
        self.assert_transition(1)

    def test_protected_program_publication_does_not_approve_or_rewrite_program(self):
        Program.objects.filter(pk=self.program.pk).update(status='published', published_at=timezone.now())
        before = list(Program.objects.filter(pk=self.program.pk).values())
        self.publish()
        self.assertEqual(before, list(Program.objects.filter(pk=self.program.pk).values()))
        self.assert_transition(2)

    def test_link_to_protected_program_and_existing_one_to_one_denied(self):
        Program.objects.filter(pk=self.other.pk).update(status='published', published_at=timezone.now())
        with self.assertRaises(ValidationError):
            self.save(application_program=self.other.pk, expected=self.tokens(self.program, self.other))
        with self.assertRaises(ValidationError):
            services.save_event(user=self.officer, data=event_data(application_program=self.program.pk), source_expected=self.tokens())
        self.assert_transition(1)

    def test_applications_prevent_unlink_and_survive_edit(self):
        member = create_member('FICTIONAL-EVENT-APPLICATION')
        app = application_fixture(self.program, member)
        before = list(ProgramApplication.objects.values())
        with self.assertRaisesMessage(ValidationError, 'once applications exist'):
            self.save(application_program='')
        self.save(image_alt='Fictional accessible description')
        self.assertEqual(before, list(ProgramApplication.objects.values()))
        self.assertTrue(ProgramApplication.objects.filter(pk=app.pk).exists())

    def test_registration_capacity_and_schedule_rules_preserved(self):
        for suffix in ('A', 'B'):
            historical_registration(self.event, create_member('FICTIONAL-REG-' + suffix))
        before = list(EventRegistration.objects.order_by('pk').values())
        for values in ({'capacity': 1}, {'ends_at': self.event.starts_at - timedelta(hours=1)}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                self.save(**values)
        self.save(image_alt='Fictional planning description')
        self.assertEqual(before, list(EventRegistration.objects.order_by('pk').values()))

    def test_missing_native_audit_rolls_back(self):
        self.rollback(self.save, 'events.services.record_log', lambda *a, **k: None)

    def test_duplicate_native_audit_rolls_back(self):
        original = services.record_log
        def duplicate(*args, **kwargs):
            original(*args, **kwargs)
            return original(*args, **kwargs)
        self.rollback(self.save, 'events.services.record_log', duplicate)

    def test_foreign_event_audit_rolls_back(self):
        other = services.save_event(user=self.officer, data=event_data(application_program=self.other.pk), source_expected=self.tokens(self.other))
        original = services.record_log
        def foreign(item, *args, **kwargs):
            return original(other, *args, **kwargs)
        self.rollback(self.save, 'events.services.record_log', foreign)

    def test_forged_native_audit_fields_roll_back(self):
        original = services.record_log
        for field, value in (('actor_label', 'forged'), ('changes', {}), ('notes', 'forged'), ('action', 'published')):
            def forge(*args, **kwargs):
                log = original(*args, **kwargs)
                EventLog.objects.filter(pk=log.pk).update(**{field: value})
                return log
            with self.subTest(field=field):
                self.rollback(lambda: self.save(title='Fictional changed title'), 'events.services.record_log', forge)

    def test_native_audit_failure_rolls_back_publication(self):
        self.rollback(self.publish, 'events.services.record_log')

    def test_batch_cas_and_final_failure_roll_back_publication(self):
        for target in ('ewaf.generation_services._invalidate', 'ewaf.generation_services._cas_source', 'ewaf.event_invalidation._finalize'):
            with self.subTest(target=target):
                self.rollback(self.publish, target)

    def test_second_program_cas_failure_rolls_back_whole_union(self):
        original = generation._cas_source
        def fail_second(state, event):
            if state.program_id == max(self.program.pk, self.other.pk):
                raise ValidationError('Fictional second state failure')
            return original(state, event)
        self.rollback(lambda: self.save(application_program=self.other.pk, expected=self.tokens(self.program, self.other)),
                      'ewaf.generation_services._cas_source', fail_second)

    def test_final_scope_check_rejects_partial_invalidation(self):
        original = generation._invalidate
        def partial(states, **kwargs):
            return original(states[:1], **kwargs)
        self.rollback(lambda: self.save(application_program=self.other.pk, expected=self.tokens(self.program, self.other)),
                      'ewaf.generation_services._invalidate', partial)

    def test_replacement_and_removal_retain_prior_image_bytes(self):
        before = self.files()
        self.save(files=self.upload())
        retained = self.files()
        self.assertTrue(before.items() <= retained.items())
        self.assertEqual(len(retained), len(before) + 1)
        self.save(remove_image=True)
        self.assertEqual(retained, self.files())
        self.event.refresh_from_db(); self.assertFalse(self.event.image)

    def test_late_failures_clean_new_upload_and_retain_old_image(self):
        for target in ('events.services.record_log', 'ewaf.generation_services._invalidate',
                       'ewaf.generation_services._cas_source', 'ewaf.event_invalidation._finalize'):
            with self.subTest(target=target):
                self.rollback(lambda: self.save(files=self.upload()), target)

    def test_creation_failure_cleans_new_image(self):
        self.rollback(lambda: services.save_event(user=self.officer, data=event_data(application_program=self.other.pk, image_alt='Fictional image'),
            files=self.upload(), source_expected=self.tokens(self.other)), 'ewaf.generation_services._invalidate')

    def test_image_collision_never_overwrites_retained_bytes(self):
        before = self.files()
        field = Event._meta.get_field('image')
        with patch.object(field, 'generate_filename', return_value=self.event.image.name):
            self.save(files=self.upload())
        self.assertTrue(before.items() <= self.files().items())
        self.assertEqual(len(self.files()), len(before) + 1)

    def test_image_alt_and_missing_image_guards(self):
        with self.assertRaises(ValidationError):
            self.save(image_alt='', files=self.upload())
        self.event.image.storage.delete(self.event.image.name)
        with self.assertRaises(ValidationError):
            self.publish()
        self.assert_transition(1)

    def test_overwriting_storage_denied(self):
        with patch.object(Event._meta.get_field('image').storage, '_allow_overwrite', True), self.assertRaises(ValidationError):
            self.save()
        self.assert_transition(1)

    def test_historical_native_audit_cannot_be_rewritten(self):
        original = services.record_log
        old = self.event.history.first()
        def rewrite(*args, **kwargs):
            EventLog.objects.filter(pk=old.pk).update(notes='forged past')
            return original(*args, **kwargs)
        self.rollback(self.save, 'events.services.record_log', rewrite)

    def test_final_permission_revocation_rolls_back_event_and_actor(self):
        original = services.record_log
        def revoke(*args, **kwargs):
            log = original(*args, **kwargs)
            get_user_model().objects.filter(pk=self.officer.pk).update(is_active=False)
            return log
        before, files = self.snapshot(), self.files()
        with patch('events.services.record_log', revoke), self.assertRaises(PermissionDenied):
            self.save(files=self.upload())
        self.assertEqual(before, self.snapshot()); self.assertEqual(files, self.files())
        self.assertTrue(get_user_model().objects.get(pk=self.officer.pk).is_active)

    def test_unregistered_requests_have_no_generation_queries(self):
        with patch.object(authority_services, 'enlisted', return_value=False), CaptureQueriesContext(connection) as queries:
            services.save_event(pk=self.event.pk, user=self.officer, data=self.data())
            self.event.refresh_from_db()
            services.change_publication(self.event.pk, user=self.officer, version=self.event.version, action='published', notes='Fictional original path')
        generation_tables = ('ewaf_authoritygeneration', 'ewaf_authorityinvalidation', 'ewaf_programsourcestate',
            'ewaf_sourcemutationbatch', 'ewaf_sourceinvalidation', 'ewaf_requestsourcebinding',
            'ewaf_runsourcebinding', 'ewaf_developmentpromotion')
        self.assertFalse(any(table in row['sql'] for row in queries for table in generation_tables))
        self.assert_transition(1)

    def test_tokens_cannot_activate_and_unowned_transactions_denied(self):
        with patch.object(authority_services, 'enlisted', return_value=False), self.assertRaises(PermissionDenied):
            self.save()
        with transaction.atomic(), self.assertRaises(ValidationError):
            self.save()

    def test_sql_all_programs_then_all_states_then_event(self):
        # Relink from the larger ID to the smaller ID to exercise sorted union.
        low, high = sorted((self.program, self.other), key=lambda item: item.pk)
        if self.event.application_program_id != high.pk:
            self.save(application_program=high.pk, expected=self.tokens(self.program, self.other))
        expected = self.tokens(self.program, self.other)
        with CaptureQueriesContext(connection) as queries:
            self.save(application_program=low.pk, expected=expected)
        locks = [row['sql'] for row in queries if 'FOR UPDATE' in row['sql']]
        tables = ('programs_programtermslock', 'ewaf_authoritygeneration', 'programs_program', 'ewaf_programsourcestate', 'events_event')
        first = {table: next(i for i, sql in enumerate(locks) if f'FROM `{table}`' in sql) for table in tables}
        self.assertEqual(list(first.values()), sorted(first.values()))
        p = [i for i, sql in enumerate(locks) if 'FROM `programs_program`' in sql]
        s = [i for i, sql in enumerate(locks) if 'FROM `ewaf_programsourcestate`' in sql]
        self.assertLess(max(p), min(s))
        self.assertLess(max(s), first['events_event'])
        for sql, pk in zip([locks[i] for i in p], sorted([self.program.pk, self.other.pk])):
            self.assertIn(str(pk).replace('-', ''), sql.replace('-', ''))
        print('Gate 2D-2C actual SQL first lock order:', ' -> '.join(tables), '; two Programs then two SourceStates')


class EventConcurrencyTests(EventHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_event()

    def race(self, operation, fail_first=False):
        entered, release, attempted = Signal(), Signal(), Signal()
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
            self.assertEqual(a[1], 'committed')
            self.assertTrue('STALE_GENERATION' in b[1] or 'INCOMPLETE_EVENT_SOURCE_SCOPE' in b[1], b[1])
        print('Gate 2D-2C MySQL writer connections:', a[0], b[0], '; first rollback:', fail_first)
        self.assert_transition(2)

    def test_two_editors_one_generation_winner(self):
        expected = self.tokens()
        self.race(lambda: self.save(expected=expected, title='Fictional concurrent edit'))

    def test_two_publishers_one_generation_winner(self):
        expected = self.tokens()
        self.race(lambda: self.publish(expected=expected))

    def test_two_relinks_have_one_complete_union_winner(self):
        expected = self.tokens(self.program, self.other)
        self.race(lambda: self.save(application_program=self.other.pk, expected=expected))
        self.assertEqual(ProgramSourceState.objects.get(program=self.other).generation, 2)

    def test_failed_image_replacement_allows_waiter_without_orphan(self):
        expected, files = self.tokens(), self.files()
        self.race(lambda: self.save(expected=expected, files=self.upload()), fail_first=True)
        self.assertTrue(files.items() <= self.files().items())
        self.assertEqual(len(self.files()), len(files) + 1)

    def test_program_wait_does_not_lock_event_early(self):
        held, attempted, release = Signal(), Signal(), Signal()
        expected = self.tokens()
        original = Program.objects.select_for_update
        def signal(*args, **kwargs):
            attempted.set()
            return original(*args, **kwargs)
        def blocker():
            with transaction.atomic():
                Program.objects.select_for_update().get(pk=self.program.pk)
                held.set()
                if not release.wait(20):
                    raise RuntimeError('Fictional timeout')
                Event.objects.select_for_update(nowait=True).get(pk=self.event.pk)
            return 'event acquired while holding program'
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(worker, blocker)
            self.assertTrue(held.wait(10))
            with patch.object(Program.objects, 'select_for_update', signal):
                second = pool.submit(worker, lambda: self.save(expected=expected).version)
                try:
                    self.assertTrue(attempted.wait(10))
                    with self.assertRaises(TimeoutError):
                        second.result(.25)
                finally:
                    release.set()
                a, b = first.result(30), second.result(30)
        self.assertNotEqual(a[0], b[0])
        self.assertEqual(a[1], 'event acquired while holding program')
        print('Gate 2D-2C Program/Event probe connections:', a[0], b[0])

    def test_registration_restoration_can_finish_while_event_writer_waits(self):
        self.publish()
        member = create_member('FICTIONAL-EVENT-RACE')
        registration = historical_registration(self.event, member)
        EventRegistration.objects.filter(pk=registration.pk).update(status='cancelled')
        entered, release, attempted = Signal(), Signal(), Signal()
        expected = self.tokens()
        original = EventRegistration.objects.select_for_update
        event_lock = Event.objects.select_for_update
        def hold(*args, **kwargs):
            entered.set()
            if not release.wait(20):
                raise RuntimeError('Fictional timeout')
            return original(*args, **kwargs)
        def signal(*args, **kwargs):
            if entered.is_set():
                attempted.set()
            return event_lock(*args, **kwargs)
        with patch.object(EventRegistration.objects, 'select_for_update', hold), patch.object(Event.objects, 'select_for_update', signal):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(worker, lambda: services.change_registration(registration.pk, user=self.officer,
                    version=0, status='confirmed', notes='Fictional legacy restoration').status)
                try:
                    self.assertTrue(entered.wait(10))
                    second = pool.submit(worker, lambda: self.save(expected=expected).version)
                    self.assertTrue(attempted.wait(10))
                    with self.assertRaises(TimeoutError):
                        second.result(.25)
                finally:
                    release.set()
                a, b = first.result(30), second.result(30)
        self.assertNotEqual(a[0], b[0]); self.assertEqual(a[1], 'confirmed')
        self.assert_transition(3)
        print('Gate 2D-2C legacy registration/Event connections:', a[0], b[0])


class EventHistoryTests(SourceHelpers, DurableHelpers, TransactionTestCase):
    def setup_evidence(self):
        super().setup_evidence()
        # Fixture linkage predates the audited development epoch, not a new
        # permission to link a protected program through the event service.
        self.event = Event.objects.create(title='Fictional historical linked event', description='Fictional',
            location='Fictional venue', starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=3), application_program=self.program,
            created_by=self.officer, updated_by=self.officer)

    def setUp(self):
        self.setup_durable()
        self.register()

    def test_publication_preserves_durable_history_and_disabled_access(self):
        from .durable_services import inspect_development_history, require_operational_result
        request = self.request_run(); run = self.process(request)
        expected = self.token()
        with generation._fence(self.officer, [self.program.pk]) as (_, authority, _, states):
            state = states[self.program.pk]
            binding = generation._bind_request(request, run.snapshot, state=state, authority=authority,
                expected=expected, valid_until=timezone.now() + timedelta(minutes=2))
            run_binding = generation._bind_run(run, state=state, authority=authority)
        before = run.digest, run.snapshot, binding.digest, run_binding.digest
        services.change_publication(self.event.pk, user=self.officer, version=0, action='published',
            notes='Fictional publication', source_expected=self.expected())
        run.refresh_from_db(); binding.refresh_from_db(); run_binding.refresh_from_db()
        binding.full_clean(); run_binding.full_clean()
        self.assertEqual(before, (run.digest, run.snapshot, binding.digest, run_binding.digest))
        self.assertFalse(inspect_development_history(run.pk, program_id=self.program.pk, user=self.officer)['operational_ready'])
        self.assertFalse(DevelopmentPromotion.objects.exists())
        with self.assertRaises(ValidationError):
            require_operational_result()
        self.assert_transition(2)
