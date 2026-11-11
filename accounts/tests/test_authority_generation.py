"""Fictional Gate 2C requests; requires the fresh disposable MySQL runner."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextlib import contextmanager
from threading import Event
from unittest.mock import patch

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth import SESSION_KEY, HASH_SESSION_KEY
from django.contrib.auth.models import User, Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connections, connection, transaction, OperationalError
from django.test import Client, RequestFactory, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from accounts import authority_services as service
from accounts.admin import AdministratorAdmin
from audit.models import SecurityEvent
from ewaf import generation_services as generation
from ewaf.generation_models import AuthorityGeneration, AuthorityInvalidation, ProgramSourceState, DevelopmentPromotion
from ewaf.test_generation_foundation import FoundationHelpers

PASSWORD = 'Fictional-authority-903!'
NEW_PASSWORD = 'Changed-fictional-904!'


class AuthorityHelpers(FoundationHelpers):
    def setUp(self):
        self.setup_foundation()
        self.bootstrap()
        self.target = User.objects.create_user('fictional_target', password=PASSWORD, is_staff=True)
        self.group = Group.objects.create(name='Fictional authority group')
        self.permission = Permission.objects.get(content_type__app_label='accounts', codename='access_dashboard')
        self.client.force_login(self.officer)
        self.session_context = service._disposable_authority_session(user=self.officer)
        self.session_context.__enter__()
        self.addCleanup(self.session_context.__exit__, None, None, None)

    def epoch(self):
        return AuthorityGeneration.objects.get(pk=1).generation

    def user_data(self, **overrides):
        self.target.refresh_from_db()
        joined = timezone.localtime(self.target.date_joined)
        return {'username': self.target.username, 'first_name': self.target.first_name,
                'last_name': self.target.last_name, 'email': self.target.email,
                'is_active': 'on', 'is_staff': 'on',
                'date_joined_0': joined.strftime('%Y-%m-%d'),
                'date_joined_1': joined.strftime('%H:%M:%S.%f'),
                'groups': list(self.target.groups.values_list('pk', flat=True)),
                'user_permissions': list(self.target.user_permissions.values_list('pk', flat=True)),
                '_save': 'Save', **overrides}

    def edit_user(self, **overrides):
        return self.client.post(reverse('admin:auth_user_change', args=[self.target.pk]), self.user_data(**overrides))

    def edit_group(self, **overrides):
        return self.client.post(reverse('admin:auth_group_change', args=[self.group.pk]), {
            'name': self.group.name, 'permissions': list(self.group.permissions.values_list('pk', flat=True)),
            '_save': 'Save', **overrides})

    def relation(self, operation, ids=(), **overrides):
        return service.mutate_relation(**{'user': self.officer, 'model': User, 'pk': self.target.pk,
            'relation': 'user_permissions', 'operation': operation, 'related_ids': ids, **overrides})

    def assert_history(self, generation_count):
        self.assertEqual(self.epoch(), generation_count)
        self.assertEqual(AuthorityInvalidation.objects.count(), generation_count)
        for event in AuthorityInvalidation.objects.all():
            event.full_clean()
        self.assertFalse(DevelopmentPromotion.objects.exists())
        self.assertFalse(ProgramSourceState.objects.exclude(current_binding=None).exists())


class AuthorityRequestTests(AuthorityHelpers, TransactionTestCase):
    def test_unrelated_login_failure_audit_does_not_disrupt_password_change(self):
        from accounts.views import record_event
        self.client.force_login(self.target)
        def with_login_failure(*args, **kwargs):
            SecurityEvent.objects.create(action=SecurityEvent.Action.LOGIN_FAILED)
            record_event(*args, **kwargs)
        with patch('accounts.views.record_event', with_login_failure):
            response = self.client.post(reverse('accounts:password_change'), {
                'old_password': PASSWORD, 'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assert_history(2)

    def test_automatic_password_hash_upgrade_does_not_invalidate(self):
        # Historical low-iteration hash exercises Django's real upgrade setter.
        from django.contrib.auth.hashers import PBKDF2PasswordHasher
        self.target.password = PBKDF2PasswordHasher().encode(PASSWORD, 'fictional-salt', iterations=1)
        self.target.save(update_fields=['password'])
        old_hash = self.target.password
        self.assertTrue(self.client.login(username=self.target.username, password=PASSWORD))
        self.target.refresh_from_db()
        self.assertNotEqual(old_hash, self.target.password)
        self.assert_history(1)

    def test_admin_self_password_session_is_updated_after_commit(self):
        original = __import__('django.contrib.auth', fromlist=['update_session_auth_hash']).update_session_auth_hash
        observed = []
        def check_commit(request, user):
            observed.append((connection.in_atomic_block, self.epoch()))
            return original(request, user)
        with patch('accounts.admin.update_session_auth_hash', check_commit):
            response = self.client.post(reverse('admin:auth_user_password_change', args=[self.officer.pk]), {
                'password1': NEW_PASSWORD, 'password2': NEW_PASSWORD, 'usable_password': 'true'})
        self.assertEqual(response.status_code, 302)
        self.officer.refresh_from_db()
        self.assertEqual(self.client.session[HASH_SESSION_KEY], self.officer.get_session_auth_hash())
        self.assertEqual(observed, [(False, 2)])

    def test_user_creation_has_native_audit_and_one_generation(self):
        response = self.client.post(reverse('admin:auth_user_add'), {
            'username': 'fictional_created', 'password1': PASSWORD, 'password2': PASSWORD,
            'usable_password': 'true', '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='fictional_created').exists())
        self.assert_history(2)

    def test_group_creation_and_edit(self):
        self.assertEqual(self.client.post(reverse('admin:auth_group_add'), {
            'name': 'Fictional new role', 'permissions': [self.permission.pk]}).status_code, 302)
        self.assertEqual(self.edit_group(name='Fictional renamed role').status_code, 302)
        self.assert_history(3)

    def test_user_scalar_and_staff_superuser_status_changes(self):
        for overrides in ({'first_name': 'Fictional'}, {'is_superuser': 'on'}, {'is_staff': ''}):
            self.assertEqual(self.edit_user(**overrides).status_code, 302)
        self.assert_history(4)

    def test_deactivation_and_reactivation_do_not_restore_generation(self):
        self.assertEqual(self.edit_user(is_active='').status_code, 302)
        self.assertEqual(self.edit_user().status_code, 302)
        self.assert_history(3)

    def test_same_value_user_and_group_forms_do_not_invalidate(self):
        self.assertEqual(self.edit_user().status_code, 302)
        self.assertEqual(self.edit_group().status_code, 302)
        self.assert_history(1)
        self.assertEqual(LogEntry.objects.count(), 2)

    def test_admin_direct_permission_add_remove_and_restore(self):
        for values in ([self.permission.pk], [], [self.permission.pk]):
            self.assertEqual(self.edit_user(user_permissions=values).status_code, 302)
        self.assert_history(4)

    def test_admin_group_membership_add_remove(self):
        for values in ([self.group.pk], []):
            self.assertEqual(self.edit_user(groups=values).status_code, 302)
        self.assert_history(3)

    def test_admin_group_permission_add_remove(self):
        for values in ([self.permission.pk], []):
            self.assertEqual(self.edit_group(permissions=values).status_code, 302)
        self.assert_history(3)

    def test_invalid_form_does_not_mutate_or_invalidate(self):
        self.assertEqual(self.edit_user(username='').status_code, 200)
        self.assert_history(1)
        self.assertFalse(LogEntry.objects.exists())

    def test_single_user_delete(self):
        pk = self.target.pk
        self.assertEqual(self.client.post(reverse('admin:auth_user_delete', args=[pk]), {'post': 'yes'}).status_code, 302)
        self.assertFalse(User.objects.filter(pk=pk).exists())
        self.assert_history(2)

    def test_single_group_delete_with_membership_cascade(self):
        self.relation('add', [self.group.pk], relation='groups')
        self.assertEqual(self.client.post(reverse('admin:auth_group_delete', args=[self.group.pk]), {'post': 'yes'}).status_code, 302)
        self.assertFalse(self.target.groups.exists())
        self.assert_history(3)

    def test_bulk_user_delete(self):
        other = User.objects.create_user('fictional_other')
        response = self.client.post(reverse('admin:auth_user_changelist'), {
            'action': 'delete_selected', '_selected_action': [self.target.pk, other.pk], 'post': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk__in=[self.target.pk, other.pk]).exists())
        self.assert_history(3)

    def test_bulk_group_delete(self):
        other = Group.objects.create(name='Fictional second group')
        self.assertEqual(self.client.post(reverse('admin:auth_group_changelist'), {
            'action': 'delete_selected', '_selected_action': [self.group.pk, other.pk], 'post': 'yes'}).status_code, 302)
        self.assert_history(3)

    def test_delete_confirmation_does_not_invalidate(self):
        self.assertEqual(self.client.post(reverse('admin:auth_group_changelist'), {
            'action': 'delete_selected', '_selected_action': [self.group.pk]}).status_code, 200)
        self.assert_history(1)

    def test_protected_audit_actor_cannot_be_deleted(self):
        response = self.client.post(reverse('admin:auth_user_delete', args=[self.officer.pk]), {'post': 'yes'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.officer.pk).exists())
        self.assert_history(1)

    def test_admin_password_change_is_a_credential_event_without_secrets(self):
        old_hash = self.target.password
        response = self.client.post(reverse('admin:auth_user_password_change', args=[self.target.pk]), {
            'password1': NEW_PASSWORD, 'password2': NEW_PASSWORD, 'usable_password': 'true'})
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(NEW_PASSWORD))
        event = AuthorityInvalidation.objects.get(after_generation=2)
        self.assertEqual(event.kind, 'CREDENTIAL_CHANGE')
        payload = str(event.payload())
        for secret in (PASSWORD, NEW_PASSWORD, old_hash, self.target.password):
            self.assertNotIn(secret, payload)
        self.assert_history(2)

    def test_admin_unset_password(self):
        response = self.client.post(reverse('admin:auth_user_password_change', args=[self.target.pk]), {
            'usable_password': 'false', 'unset-password': 'yes'})
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertFalse(self.target.has_usable_password())
        self.assert_history(2)

    def test_staff_own_password_preserves_session_and_security_event(self):
        self.client.force_login(self.target)
        old_key = self.client.session.session_key
        response = self.client.post(reverse('accounts:password_change'), {
            'old_password': PASSWORD, 'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.target.refresh_from_db()
        self.assertNotEqual(old_key, self.client.session.session_key)
        self.assertEqual(self.client.session[SESSION_KEY], str(self.target.pk))
        self.assertEqual(self.client.session[HASH_SESSION_KEY], self.target.get_session_auth_hash())
        self.assertEqual(SecurityEvent.objects.filter(action='password_changed', user=self.target).count(), 1)
        self.assert_history(2)

    def test_staff_with_cached_all_permissions_still_cannot_administer(self):
        self.target.user_permissions.set(Permission.objects.all())
        self.client.force_login(self.target)
        self.assertEqual(self.edit_group(name='Forbidden').status_code, 403)
        self.assert_history(1)

    def test_fresh_actor_recheck_ignores_stale_superuser_object(self):
        request = RequestFactory().post('/')
        request.user = self.officer
        User.objects.filter(pk=self.officer.pk).update(is_superuser=False)
        with self.assertRaises(PermissionDenied), service.protect_request(request, User):
            self.fail('Revoked actor entered mutation')
        self.assert_history(1)

    def test_login_logout_and_last_login_do_not_invalidate(self):
        self.client.logout()
        self.assertTrue(self.client.login(username=self.target.username, password=PASSWORD))
        self.client.get(reverse('accounts:password_change'))
        self.client.logout()
        self.assert_history(1)

    def test_no_authority_program_fanout_and_old_token_is_stale(self):
        old = self.token()
        before = list(ProgramSourceState.objects.values())
        self.relation('add', [self.permission.pk])
        self.assertEqual(before, list(ProgramSourceState.objects.values()))
        with self.assertRaisesMessage(ValidationError, 'STALE'):
            self.advance(expected={self.program.pk: old})
        self.assert_history(2)


class AuthorityRollbackTests(AuthorityHelpers, TransactionTestCase):
    def test_closed_session_cannot_resume_across_unfenced_changes(self):
        self.session_context.__exit__(None, None, None)
        with self.assertRaisesMessage(ValidationError, 'REINITIALIZATION_REQUIRED'):
            with service._disposable_authority_session(user=self.officer):
                self.fail('A suspended authority epoch was silently reused')

    def test_actual_missing_authority_state_fails_closed(self):
        with connection.cursor() as cursor:
            cursor.execute('DELETE FROM ewaf_authoritygeneration WHERE id=1')
        with self.assertRaisesMessage(ValidationError, 'AUTHORITY_NOT_INITIALIZED'):
            self.edit_user(first_name='Forbidden')
        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, '')
        self.assertFalse(LogEntry.objects.exists())

    def test_unknown_admin_action_is_not_silently_integrated(self):
        with self.assertRaisesMessage(ValidationError, 'ACTION_NOT_INTEGRATED'):
            self.client.post(reverse('admin:auth_group_changelist'), {'action': 'future_custom_action'})
        self.assert_history(1)

    def test_missing_delete_audit_rolls_back(self):
        with patch.object(AdministratorAdmin, 'log_deletions'), self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT'):
            self.client.post(reverse('admin:auth_user_delete', args=[self.target.pk]), {'post': 'yes'})
        self.assertTrue(User.objects.filter(pk=self.target.pk).exists())
        self.assert_history(1)

    def test_missing_native_admin_audit_rolls_back_scalar_and_m2m(self):
        with patch.object(AdministratorAdmin, 'log_change'), self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT'):
            self.edit_user(first_name='Rolled back', groups=[self.group.pk], user_permissions=[self.permission.pk])
        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, '')
        self.assertFalse(self.target.groups.exists())
        self.assertFalse(self.target.user_permissions.exists())
        self.assert_history(1)

    def test_duplicate_native_admin_audit_rolls_back(self):
        original = AdministratorAdmin.log_change
        def duplicate(*args, **kwargs):
            original(*args, **kwargs)
            original(*args, **kwargs)
        with patch.object(AdministratorAdmin, 'log_change', duplicate), self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT'):
            self.edit_user(first_name='Rolled back')
        self.assertFalse(LogEntry.objects.exists())
        self.assert_history(1)

    def test_native_audit_exception_rolls_back(self):
        with patch.object(AdministratorAdmin, 'log_change', side_effect=RuntimeError('Fictional audit failure')):
            with self.assertRaises(RuntimeError):
                self.edit_user(first_name='Rolled back')
        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, '')
        self.assert_history(1)

    def test_generation_audit_failure_rolls_back(self):
        with patch.object(generation, '_persist', side_effect=ValidationError('Fictional generation failure')):
            with self.assertRaises(ValidationError):
                self.edit_user(first_name='Rolled back')
        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, '')
        self.assertFalse(LogEntry.objects.exists())
        self.assert_history(1)

    def test_cas_failure_rolls_back(self):
        with patch.object(generation, '_cas_authority', side_effect=ValidationError('Fictional CAS conflict')):
            with self.assertRaises(ValidationError):
                self.relation('add', [self.permission.pk])
        self.assertFalse(self.target.user_permissions.exists())
        self.assertFalse(LogEntry.objects.exists())
        self.assert_history(1)

    def test_bulk_deletion_failure_restores_all_targets_and_audits(self):
        other = User.objects.create_user('fictional_bulk_other')
        original = generation._cas_authority
        def fail_second(state, event):
            if state.generation == 2:
                raise ValidationError('Fictional second CAS failure')
            return original(state, event)
        with patch.object(generation, '_cas_authority', fail_second), self.assertRaises(ValidationError):
            self.client.post(reverse('admin:auth_user_changelist'), {
                'action': 'delete_selected', '_selected_action': [self.target.pk, other.pk], 'post': 'yes'})
        self.assertEqual(User.objects.filter(pk__in=[self.target.pk, other.pk]).count(), 2)
        self.assertFalse(LogEntry.objects.exists())
        self.assert_history(1)

    def test_own_password_audit_failure_restores_password_and_old_session(self):
        self.client.force_login(self.target)
        old_session = self.client.session.session_key
        old_hash = self.target.password
        with patch('accounts.views.record_event', side_effect=RuntimeError('Fictional security audit failure')):
            with self.assertRaises(RuntimeError):
                self.client.post(reverse('accounts:password_change'), {
                    'old_password': PASSWORD, 'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD})
        self.target.refresh_from_db()
        self.assertEqual(old_hash, self.target.password)
        from django.contrib.sessions.models import Session
        self.assertTrue(Session.objects.filter(session_key=old_session).exists())
        self.assert_history(1)

    def test_missing_own_password_audit_rolls_back(self):
        self.client.force_login(self.target)
        with patch('accounts.views.record_event'), self.assertRaisesMessage(ValidationError, 'NATIVE_AUDIT'):
            self.client.post(reverse('accounts:password_change'), {
                'old_password': PASSWORD, 'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD})
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(PASSWORD))
        self.assert_history(1)

    def test_admin_password_generation_failure_rolls_back(self):
        with patch.object(generation, '_cas_authority', side_effect=ValidationError('Fictional CAS failure')):
            with self.assertRaises(ValidationError):
                self.client.post(reverse('admin:auth_user_password_change', args=[self.target.pk]), {
                    'password1': NEW_PASSWORD, 'password2': NEW_PASSWORD, 'usable_password': 'true'})
        self.target.refresh_from_db()
        self.assertTrue(self.target.check_password(PASSWORD))
        self.assertFalse(LogEntry.objects.exists())
        self.assert_history(1)

    def test_registered_missing_state_denies_before_account_write(self):
        with patch.object(generation, '_authority', side_effect=ValidationError('AUTHORITY_NOT_INITIALIZED')):
            with self.assertRaisesMessage(ValidationError, 'NOT_INITIALIZED'):
                self.edit_user(first_name='Forbidden')
        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, '')

    def test_registered_identity_mismatch_never_falls_back(self):
        with patch.object(service, '_session', ('wrong',)):
            self.assertEqual(self.edit_user(first_name='Forbidden').status_code, 403)
        self.assert_history(1)

    def test_outer_transaction_rejected_before_any_authority_lock(self):
        with transaction.atomic(), self.assertRaisesMessage(ValidationError, 'transaction'):
            self.relation('add', [self.permission.pk])

    def test_unregistered_account_request_uses_no_foundation_tables(self):
        with patch.object(service, '_session', None), CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.edit_user(first_name='Normal application behavior').status_code, 302)
        self.assertFalse(any('ewaf_authority' in row['sql'].lower() for row in queries))
        self.assert_history(1)


class AuthorityRelationTests(AuthorityHelpers, TransactionTestCase):
    def test_forward_add_remove_set_clear_and_noop(self):
        for model, pk, relation, related in (
                (User, self.target.pk, 'user_permissions', self.permission.pk),
                (User, self.target.pk, 'groups', self.group.pk),
                (Group, self.group.pk, 'permissions', self.permission.pk)):
            for operation, ids in (('add', [related]), ('add', [related]), ('remove', [related]),
                                   ('set', [related]), ('clear', [])):
                self.relation(operation, ids, model=model, pk=pk, relation=relation)
        self.assert_history(13)

    def test_reverse_add_remove_set_clear(self):
        for model, pk, relation, related in (
                (Group, self.group.pk, 'user_set', self.target.pk),
                (Permission, self.permission.pk, 'user_set', self.target.pk),
                (Permission, self.permission.pk, 'group_set', self.group.pk)):
            for operation, ids in (('add', [related]), ('remove', [related]), ('set', [related]), ('clear', [])):
                self.relation(operation, ids, model=model, pk=pk, relation=relation)
        self.assert_history(13)

    def test_revoke_restore_has_distinct_audits_and_generations(self):
        self.relation('add', [self.permission.pk])
        original = set(self.target.user_permissions.values_list('pk', flat=True))
        self.relation('clear')
        self.relation('add', [self.permission.pk])
        self.assertEqual(original, set(self.target.user_permissions.values_list('pk', flat=True)))
        self.assert_history(4)

    def test_unregistered_internal_m2m_denied(self):
        with patch.object(service, '_session', None), self.assertRaises(PermissionDenied):
            self.relation('add', [self.permission.pk])

    def test_missing_relation_target_denied(self):
        with self.assertRaises(ValidationError):
            self.relation('add', [99999999])
        self.assert_history(1)


def worker(action):
    close_old_connections()
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT CONNECTION_ID()')
            identity = cursor.fetchone()[0]
        return identity, action()
    finally:
        connections.close_all()


class AuthorityConcurrencyTests(AuthorityHelpers, TransactionTestCase):
    def test_real_admin_requests_serialize_at_terms_before_authority(self):
        clients = [Client(), Client()]
        for client in clients:
            client.force_login(self.officer)
        entered, release, attempted = Event(), Event(), Event()
        original_lock = service._lock_records
        original_terms = service.terms_lock
        calls = []
        def hold_first():
            original_lock()
            calls.append('locked')
            if len(calls) == 1:
                entered.set()
                if not release.wait(15):
                    raise RuntimeError('Concurrency test timed out')
        @contextmanager
        def observed_terms():
            if entered.is_set():
                attempted.set()
            with original_terms():
                yield
        url = reverse('admin:auth_group_change', args=[self.group.pk])
        with patch.object(service, '_lock_records', hold_first), patch.object(service, 'terms_lock', observed_terms):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(worker, lambda: clients[0].post(url, {'name': 'Fictional first'}).status_code)
                try:
                    self.assertTrue(entered.wait(10))
                    second = pool.submit(worker, lambda: clients[1].post(url, {'name': 'Fictional second'}).status_code)
                    self.assertTrue(attempted.wait(10))
                    with self.assertRaises(TimeoutError):
                        second.result(timeout=0.25)
                    self.assertEqual(calls, ['locked'])
                finally:
                    release.set()
                a, b = first.result(20), second.result(20)
        self.assertNotEqual(a[0], b[0])
        self.assertEqual((a[1], b[1]), (302, 302))
        self.assert_history(3)

    def test_waiting_request_rechecks_revoked_actor(self):
        second_actor = User.objects.create_superuser('fictional_second_admin')
        second_client = Client()
        second_client.force_login(second_actor)
        entered, release, attempted = Event(), Event(), Event()
        original_lock, original_terms = service._lock_records, service.terms_lock
        first_call = []
        def hold_first():
            original_lock()
            if not first_call:
                first_call.append(True)
                entered.set()
                if not release.wait(15):
                    raise RuntimeError('Fictional test timeout')
        @contextmanager
        def observed_terms():
            if entered.is_set():
                attempted.set()
            with original_terms():
                yield
        self.target = second_actor
        data = self.user_data(is_superuser='')
        with patch.object(service, '_lock_records', hold_first), patch.object(service, 'terms_lock', observed_terms):
            with ThreadPoolExecutor(max_workers=2) as pool:
                first = pool.submit(worker, lambda: self.client.post(
                    reverse('admin:auth_user_change', args=[second_actor.pk]), data).status_code)
                try:
                    self.assertTrue(entered.wait(10))
                    second = pool.submit(worker, lambda: second_client.post(
                        reverse('admin:auth_group_change', args=[self.group.pk]), {'name': 'Forbidden'}).status_code)
                    self.assertTrue(attempted.wait(10))
                    with self.assertRaises(TimeoutError):
                        second.result(timeout=0.25)
                finally:
                    release.set()
                a, b = first.result(20), second.result(20)
        self.assertNotEqual(a[0], b[0])
        self.assertEqual((a[1], b[1]), (302, 403))
        self.group.refresh_from_db()
        self.assertEqual(self.group.name, 'Fictional authority group')
        self.assert_history(2)

    def test_mysql_lock_timeout_rolls_back_without_retry(self):
        held, release = Event(), Event()
        def blocker():
            with service.terms_lock():
                held.set()
                if not release.wait(15):
                    raise RuntimeError('Fictional test timeout')
        with ThreadPoolExecutor(max_workers=1) as pool:
            blocking = pool.submit(worker, blocker)
            try:
                self.assertTrue(held.wait(10))
                with connection.cursor() as cursor:
                    cursor.execute('SET SESSION innodb_lock_wait_timeout=1')
                with self.assertRaises(OperationalError) as error:
                    self.edit_user(first_name='Forbidden')
                self.assertEqual(error.exception.args[0], 1205)
            finally:
                release.set()
                with connection.cursor() as cursor:
                    cursor.execute('SET SESSION innodb_lock_wait_timeout=50')
            blocking.result(20)
        self.target.refresh_from_db()
        self.assertEqual(self.target.first_name, '')
        self.assert_history(1)

    def test_lock_sql_order_is_terms_authority_users_groups_permissions_through(self):
        with CaptureQueriesContext(connection) as queries:
            self.relation('add', [self.permission.pk])
        locks = [row['sql'] for row in queries if 'FOR UPDATE' in row['sql']]
        expected = ('programs_programtermslock', 'ewaf_authoritygeneration', 'auth_user', 'auth_group',
                    'auth_permission', 'auth_user_groups', 'auth_user_user_permissions', 'auth_group_permissions')
        for sql, table in zip(locks, expected):
            self.assertIn('`' + table + '`', sql)
        self.assertGreaterEqual(len(locks), len(expected))
