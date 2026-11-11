from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import StringIO

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.db import close_old_connections
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.backends import reserve_login_attempt, window_key
from accounts.models import LoginWindow
from audit.models import SecurityEvent


PASSWORD = 'Test-only-password-903!'


class AccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.staff = user.objects.create_user('officer', password=PASSWORD, is_staff=True)
        cls.superuser = user.objects.create_superuser('supervisor', password=PASSWORD)
        cls.regular = user.objects.create_user('visitor', password=PASSWORD)
        cls.inactive = user.objects.create_user('inactive', password=PASSWORD, is_staff=True, is_active=False)
        cls.permission = Permission.objects.get(content_type__app_label='accounts', codename='access_dashboard')

    def sign_in(self, username='officer', password=PASSWORD, path='accounts:login', **extra):
        return self.client.post(reverse(path), {'username': username, 'password': password, **extra})

    def test_superuser_login_and_safe_default_destination(self):
        response = self.sign_in('supervisor')
        self.assertRedirects(response, reverse('core:dashboard'))
        self.assertContains(self.client.get(reverse('core:dashboard')), 'Manage roles (groups)')

    def test_external_next_url_is_rejected_by_login_and_legacy_redirect(self):
        for route in ('accounts:login', 'admin:login'):
            with self.subTest(route=route):
                self.client.logout()
                response = self.sign_in('supervisor', path=route, next='https://attacker.invalid/')
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith('/'))
                self.assertNotIn('attacker.invalid', response.url)

    def test_old_admin_login_always_opens_main_login_with_dashboard_destination(self):
        target = reverse('accounts:login') + '?next=' + reverse('core:dashboard')
        for url in (reverse('admin:login'), reverse('admin:login').rstrip('/')):
            for values in ({}, {'next': '/admin/auth/user/'}, {'next': 'https://attacker.invalid/'},
                           {'next': '//attacker.invalid/', 'username': 'discarded', 'password': 'discarded'}):
                with self.subTest(url=url, values=values):
                    response = self.client.get(url, values)
                    self.assertRedirects(response, target, fetch_redirect_response=False)
                    self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.head(reverse('admin:login'))['Location'], target)
        page = self.client.get(reverse('admin:login'), {'next': '/admin/auth/user/'}, follow=True)
        self.assertTemplateUsed(page, 'accounts/login.html')
        self.assertTemplateNotUsed(page, 'admin/login.html')
        self.assertEqual(page.context['next'], reverse('core:dashboard'))

    def test_old_login_post_redirects_without_authentication_or_forwarding_credentials(self):
        response = self.sign_in('supervisor', path='admin:login', next='/admin/auth/user/')
        target = reverse('accounts:login') + '?next=' + reverse('core:dashboard')
        self.assertRedirects(response, target, fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(LoginWindow.objects.count(), 0)
        self.assertFalse(SecurityEvent.objects.filter(action__in=('login', 'login_failed')).exists())
        response = self.client.post(target, {'username': 'supervisor', 'password': PASSWORD,
                                            'next': reverse('core:dashboard')})
        self.assertRedirects(response, reverse('core:dashboard'), fetch_redirect_response=False)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.superuser.pk)

    def test_wrong_unknown_nonstaff_and_inactive_logins_have_same_error(self):
        for username, password in [('officer', 'wrong'), ('unknown', PASSWORD),
                                   ('visitor', PASSWORD), ('inactive', PASSWORD)]:
            with self.subTest(username=username):
                response = self.sign_in(username, password)
                self.assertContains(response, 'Unable to sign in. Check your credentials or try again later.')
                self.assertNotIn('_auth_user_id', self.client.session)

    def test_staff_flag_alone_does_not_grant_dashboard(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, 'Sign out', status_code=403)

    def test_group_permission_grants_access_and_revocation_is_immediate(self):
        group = Group.objects.create(name='Test configurable role')
        group.permissions.add(self.permission)
        self.staff.groups.add(group)
        self.client.force_login(self.staff)
        response = self.client.get(reverse('core:dashboard'))
        self.assertContains(response, group.name)
        self.assertNotContains(response, 'Manage accounts')
        self.assertIn('no-store', response['Cache-Control'])
        group.permissions.clear()
        self.assertEqual(self.client.get(reverse('core:dashboard')).status_code, 403)

    def test_direct_permission_also_grants_dashboard(self):
        self.staff.user_permissions.add(self.permission)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('core:dashboard')).status_code, 200)

    def test_removing_staff_or_active_flag_revokes_existing_session(self):
        for field in ('is_staff', 'is_active'):
            with self.subTest(field=field):
                self.staff.is_staff = self.staff.is_active = True
                self.staff.save()
                self.client.force_login(self.staff)
                get_user_model().objects.filter(pk=self.staff.pk).update(**{field: False})
                self.assertEqual(self.client.get(reverse('core:dashboard')).status_code, 302)
                self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)

    def test_even_staff_with_all_permissions_cannot_manage_accounts_or_roles(self):
        self.staff.user_permissions.set(Permission.objects.all())
        self.client.force_login(self.staff)
        group = Group.objects.create(name='Cannot be edited by staff')
        for model, pk in [('user', self.staff.pk), ('group', group.pk)]:
            for action, args in [('changelist', []), ('add', []), ('change', [pk]), ('delete', [pk])]:
                url = reverse(f'admin:auth_{model}_{action}', args=args)
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)
                    self.assertEqual(self.client.post(url, {'is_superuser': 'on', 'name': 'escalated'}).status_code, 403)
        self.assertEqual(self.client.post(reverse('admin:auth_user_password_change', args=[self.superuser.pk]),
                                         {'password1': PASSWORD, 'password2': PASSWORD}).status_code, 403)

    def test_superuser_can_create_edit_assign_and_revoke_configured_role(self):
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('admin:auth_group_add'), {
            'name': 'Local test role', 'permissions': [self.permission.pk], '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        group = Group.objects.get(name='Local test role')
        response = self.client.post(reverse('admin:auth_user_change', args=[self.staff.pk]), {
            'username': self.staff.username, 'is_active': 'on', 'is_staff': 'on',
            'groups': [group.pk], 'date_joined_0': '2026-09-19', 'date_joined_1': '10:00:00', '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        staff_client = Client()
        staff_client.force_login(self.staff)
        self.assertEqual(staff_client.get(reverse('core:dashboard')).status_code, 200)
        response = self.client.post(reverse('admin:auth_group_change', args=[group.pk]), {
            'name': 'Renamed test role', 'permissions': [], '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(staff_client.get(reverse('core:dashboard')).status_code, 403)
        self.assertEqual(LogEntry.objects.filter(user=self.superuser).count(), 3)

    def test_portal_login_logout_csrf_session_rotation_and_invalidation(self):
        client = Client(enforce_csrf_checks=True)
        session = client.session
        session['before_login'] = True
        session.save()
        previous_key = session.session_key
        login_url = reverse('accounts:login')
        self.assertEqual(client.post(login_url, {'username': 'supervisor', 'password': PASSWORD}).status_code, 403)
        client.get(login_url)
        response = client.post(login_url, {'username': 'supervisor', 'password': PASSWORD,
                                          'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(previous_key, client.session.session_key)
        self.assertTrue(client.cookies[settings.SESSION_COOKIE_NAME]['httponly'])
        self.assertTrue(client.session.get_expire_at_browser_close())
        logout_url = reverse('accounts:logout')
        self.assertEqual(client.get(logout_url).status_code, 405)
        self.assertEqual(client.post(logout_url).status_code, 403)
        response = client.post(logout_url, {'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('_auth_user_id', client.session)
        self.assertEqual(client.get(reverse('core:dashboard')).status_code, 302)

    def test_password_change_rejects_wrong_old_password_and_weak_new_password(self):
        self.client.force_login(self.staff)
        for old, new in [('wrong', 'New-safe-password-457!'), (PASSWORD, '123')]:
            response = self.client.post(reverse('accounts:password_change'), {
                'old_password': old, 'new_password1': new, 'new_password2': new})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password(PASSWORD))

    def test_password_change_keeps_current_session_and_revokes_other_sessions(self):
        self.client.force_login(self.staff)
        other = Client()
        other.force_login(self.staff)
        response = self.client.post(reverse('accounts:password_change'), {
            'old_password': PASSWORD, 'new_password1': 'Changed-safe-password-457!',
            'new_password2': 'Changed-safe-password-457!'})
        self.assertRedirects(response, reverse('accounts:password_change_done'))
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password('Changed-safe-password-457!'))
        self.assertIn('_auth_user_id', self.client.session)
        self.assertEqual(other.get(reverse('accounts:password_change')).status_code, 302)
        self.assertTrue(SecurityEvent.objects.filter(action='password_changed', user=self.staff).exists())

    def test_authentication_events_are_recorded_without_credentials(self):
        self.sign_in(password='Never-save-this-password')
        self.sign_in('supervisor')
        self.client.post(reverse('accounts:logout'))
        self.assertEqual(list(SecurityEvent.objects.order_by('pk').values_list('action', flat=True)),
                         ['login_failed', 'login', 'logout'])
        failed = SecurityEvent.objects.get(action='login_failed')
        self.assertIsNone(failed.user)
        self.assertNotIn('Never-save-this-password', str(list(SecurityEvent.objects.values())))

    def test_audit_is_permission_gated_and_read_only_even_for_superuser(self):
        self.client.force_login(self.staff)
        url = reverse('admin:audit_securityevent_changelist')
        self.assertEqual(self.client.get(url).status_code, 403)
        self.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label='audit', codename='view_securityevent'))
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.superuser)
        event = SecurityEvent.objects.first()
        self.assertEqual(self.client.post(reverse('admin:audit_securityevent_change', args=[event.pk]),
                                         {'action': 'logout'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:audit_securityevent_delete', args=[event.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:audit_securityevent_add')).status_code, 403)

    @override_settings(LOGIN_USERNAME_LIMIT=2, LOGIN_ADDRESS_LIMIT=20)
    def test_username_limit_handles_case_variants_after_legacy_redirect(self):
        self.sign_in('officer', 'wrong')
        redirect = self.client.get(reverse('admin:login'), {'next': '/admin/auth/user/'})
        self.client.post(redirect.url, {'username': 'OFFICER', 'password': 'wrong'})
        response = self.sign_in('officer')
        self.assertContains(response, 'Unable to sign in.')
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertTrue(SecurityEvent.objects.filter(action='login_blocked').exists())

    @override_settings(LOGIN_ADDRESS_LIMIT=2)
    def test_address_limit_covers_different_usernames_and_ignores_forwarded_header(self):
        for name in ('unknown-one', 'unknown-two'):
            self.client.post(reverse('accounts:login'), {'username': name, 'password': 'wrong'},
                             HTTP_X_FORWARDED_FOR=name)
        self.assertEqual(self.sign_in('supervisor').status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    @override_settings(LOGIN_USERNAME_LIMIT=1)
    def test_login_recovers_after_window_without_extending_lockout(self):
        self.sign_in(password='wrong')
        started = LoginWindow.objects.get(pk=window_key('username', 'officer')).started_at
        self.sign_in()
        self.assertEqual(LoginWindow.objects.get(pk=window_key('username', 'officer')).started_at, started)
        LoginWindow.objects.update(started_at=timezone.now() - timedelta(seconds=settings.LOGIN_WINDOW_SECONDS + 1))
        self.assertEqual(self.sign_in().status_code, 302)

    def test_purge_only_removes_expired_counters_and_keeps_audit(self):
        self.sign_in(password='wrong')
        expired = timezone.now() - timedelta(seconds=settings.LOGIN_WINDOW_SECONDS + 1)
        LoginWindow.objects.filter(pk=window_key('username', 'officer')).update(started_at=expired)
        call_command('purge_login_windows', stdout=StringIO())
        self.assertEqual(LoginWindow.objects.count(), 1)
        self.assertEqual(SecurityEvent.objects.count(), 1)


@override_settings(LOGIN_USERNAME_LIMIT=3, LOGIN_ADDRESS_LIMIT=10)
class ConcurrentLoginLimitTests(TransactionTestCase):
    def test_parallel_attempts_cannot_exceed_shared_database_limit(self):
        def attempt(_):
            close_old_connections()
            try:
                return reserve_login_attempt('parallel-user', '127.0.0.1')
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(attempt, range(6)))
        self.assertEqual(sum(results), 3)
        self.assertEqual(LoginWindow.objects.get(pk=window_key('username', 'parallel-user')).attempts, 3)
