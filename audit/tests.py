from datetime import timedelta

from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import SecurityEvent


class AuditDirectoryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser('directory_admin', password='Synthetic-test-903!')
        cls.event = SecurityEvent.objects.create(user=cls.admin, action='login_failed', address='192.0.2.44')
        cls.old = SecurityEvent.objects.create(user=cls.admin, action='login', address='192.0.2.45')
        SecurityEvent.objects.filter(pk=cls.old.pk).update(occurred_at=timezone.now() - timedelta(days=10))
        cls.entry = LogEntry.objects.create(user=cls.admin, action_flag=CHANGE,
            content_type=ContentType.objects.get_for_model(User), object_repr='Synthetic target',
            object_id=str(cls.admin.pk), change_message='Changed synthetic label <script>alert(1)</script>')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_audit_search_status_and_inclusive_date_filters(self):
        url = reverse('admin:audit_securityevent_changelist')
        today = timezone.localdate().isoformat()
        response = self.client.get(url, {'q': '192.0.2.44', 'action__exact': 'login_failed',
            'user__id__exact': self.admin.pk, 'date_from': today, 'date_to': today})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['cl'].result_list), [self.event])
        self.assertContains(response, 'Not recorded')
        self.assertNotContains(response, 'name="action"')
        self.assertContains(response, 'Apply filters')
        response = self.client.get(url, {'date_from': today, 'date_to': '2000-01-01'})
        self.assertEqual(response.context['cl'].result_count, 0)
        self.assertContains(response, 'Start date must be on or before end date.')
        response = self.client.get(url, {'date_from': 'invalid'})
        self.assertEqual(response.context['cl'].result_count, 0)

    def test_all_filters_and_log_details_are_safe(self):
        url = reverse('admin:admin_logentry_changelist')
        response = self.client.get(url, {'action_flag__exact': '', 'user__id__exact': '',
            'content_type__id__exact': '', 'q': 'synthetic label'}, follow=True)
        self.assertEqual(response.context['page'].paginator.count, 1)
        self.assertContains(response, 'Synthetic target')
        self.assertContains(response, 'Administrator account changed')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, 'name="action"')
        detail = self.client.get(reverse('admin:administration_activity', args=['administration', self.entry.pk]))
        self.assertContains(detail, '&lt;script&gt;')
        self.assertNotContains(detail, '<script>alert(1)</script>')
        self.assertEqual(self.client.post(reverse('admin:admin_logentry_change', args=[self.entry.pk]), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:admin_logentry_delete', args=[self.entry.pk])).status_code, 403)

    def test_pagination_retains_audit_search(self):
        SecurityEvent.objects.bulk_create([SecurityEvent(user=self.admin, action='login_failed', address='192.0.2.44') for _ in range(31)])
        response = self.client.get(reverse('admin:audit_securityevent_changelist'), {'q': '192.0.2.44', 'p': 2})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Showing 31 to 32 of 32 records')
        self.assertContains(response, 'p=1&amp;q=192.0.2.44')

    def test_roles_search_permissions_without_duplicate_groups(self):
        group = Group.objects.create(name='Synthetic review role')
        group.permissions.add(*Permission.objects.filter(content_type__app_label='audit'))
        response = self.client.get(reverse('admin:auth_group_changelist'), {'q': 'security event'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context['cl'].result_list), [group])
