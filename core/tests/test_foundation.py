import os
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.staticfiles import finders
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from config.environment import env_bool, env_list, required


class ConfigurationTests(SimpleTestCase):
    def test_required_secrets_reject_blank_values(self):
        with patch.dict(os.environ, {'EXAMPLE_SECRET': '  '}):
            with self.assertRaises(ImproperlyConfigured):
                required('EXAMPLE_SECRET')

    def test_boolean_configuration_rejects_typos(self):
        with patch.dict(os.environ, {'EXAMPLE_BOOL': 'ture'}):
            with self.assertRaises(ImproperlyConfigured):
                env_bool('EXAMPLE_BOOL')

    def test_boolean_configuration_parses_false(self):
        with patch.dict(os.environ, {'EXAMPLE_BOOL': 'False'}):
            self.assertFalse(env_bool('EXAMPLE_BOOL'))

    def test_host_list_trims_empty_entries(self):
        with patch.dict(os.environ, {'EXAMPLE_HOSTS': ' localhost, ,127.0.0.1 '}):
            self.assertEqual(env_list('EXAMPLE_HOSTS'), ['localhost', '127.0.0.1'])

    def test_test_database_is_separate(self):
        self.assertNotEqual(settings.DB_NAME.casefold(), settings.DB_TEST_NAME.casefold())
        self.assertTrue(settings.DB_TEST_NAME.startswith('test_'))


class PublicFoundationTests(TestCase):
    def test_home_is_public_and_honest_about_unavailable_features(self):
        response = self.client.get(reverse('core:home'))
        self.assertContains(response, 'Access.')
        self.assertContains(response, 'Membership Guidelines')
        self.assertContains(response, 'No announcements')
        self.assertNotContains(response, 'type="password"')

    def test_home_rejects_mutating_requests(self):
        self.assertEqual(self.client.post(reverse('core:home')).status_code, 405)

    def test_private_media_is_not_publicly_served(self):
        self.assertEqual(self.client.get('/media/private-document.pdf').status_code, 404)

    def test_security_headers(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(response['Referrer-Policy'], 'same-origin')

    @override_settings(ALLOWED_HOSTS=['localhost'])
    def test_unknown_host_rejected(self):
        self.assertEqual(self.client.get('/', HTTP_HOST='untrusted.invalid').status_code, 400)

    def test_styles_and_bootstrap_are_available_locally(self):
        for asset in ('css/site.css', 'vendor/bootstrap/bootstrap.min.css',
                      'vendor/bootstrap/bootstrap.bundle.min.js'):
            with self.subTest(asset=asset):
                self.assertIsNotNone(finders.find(asset))

    def test_admin_login_is_csrf_protected(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse('admin:login'), {'username': 'invalid', 'password': 'invalid'})
        self.assertEqual(response.status_code, 403)


class AdminAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.staff = user.objects.create_user(username='test_staff', password='Test-only-pass-579!', is_staff=True)
        cls.staff.user_permissions.add(Permission.objects.get(
            content_type__app_label='accounts', codename='access_dashboard'))
        cls.regular = user.objects.create_user(username='test_nonstaff', password='Test-only-pass-579!')
        cls.inactive = user.objects.create_user(username='test_inactive', is_staff=True, is_active=False)
        cls.superuser = user.objects.create_superuser(username='test_superuser', password='Test-only-pass-579!')

    def test_database_is_mysql_with_strict_utf8_and_innodb(self):
        self.assertEqual(connection.vendor, 'mysql')
        with connection.cursor() as cursor:
            cursor.execute('SELECT VERSION(), @@sql_mode, @@character_set_connection, @@default_storage_engine')
            version, mode, charset, engine = cursor.fetchone()
        self.assertNotIn('MariaDB', version)
        self.assertIn('STRICT_TRANS_TABLES', mode)
        self.assertEqual(charset, 'utf8mb4')
        self.assertEqual(engine, 'InnoDB')

    def test_anonymous_visitors_are_redirected_to_the_correct_login(self):
        for path, login in ((reverse('core:dashboard'), reverse('accounts:login')),
                            (reverse('admin:index'), reverse('admin:login'))):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith(login))

    def test_nonstaff_and_inactive_users_cannot_open_dashboard(self):
        for user in (self.regular, self.inactive):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse('core:dashboard')).status_code, 302)

    def test_staff_can_open_dashboard_but_cannot_manage_users_without_permission(self):
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('core:dashboard')), 'Dashboard Overview')
        self.assertEqual(self.client.get(reverse('admin:auth_user_changelist')).status_code, 403)

    def test_superuser_can_open_admin(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(reverse('admin:auth_user_changelist')).status_code, 200)

    def test_login_rotates_session_and_logout_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        session = client.session
        session['pre_auth'] = 'session-rotation-check'
        session.save()
        previous_session_key = session.session_key
        client.get(reverse('admin:login'), follow=True)
        response = client.post(reverse('accounts:login'), {
            'username': 'test_staff', 'password': 'Test-only-pass-579!',
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
            'next': reverse('core:dashboard'),
        })
        self.assertRedirects(response, reverse('core:dashboard'))
        self.assertNotEqual(client.session.session_key, previous_session_key)
        self.assertTrue(client.cookies[settings.SESSION_COOKIE_NAME]['httponly'])
        self.assertEqual(client.get(reverse('admin:logout')).status_code, 405)
        self.assertEqual(client.post(reverse('admin:logout')).status_code, 403)
        self.assertEqual(client.post(reverse('admin:logout'), {
            'csrfmiddlewaretoken': client.cookies['csrftoken'].value,
        }).status_code, 302)
        self.assertEqual(client.get(reverse('core:dashboard')).status_code, 302)

    def test_password_is_hashed(self):
        self.assertNotEqual(self.staff.password, 'Test-only-pass-579!')
        self.assertTrue(self.staff.check_password('Test-only-pass-579!'))
