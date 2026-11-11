"""Directory projections preserve existing records, visibility and workflow gates."""
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from membership.tests import grant
from programs.models import ProgramApplication
from programs.tests import create_program
from scripts.durable_test_runner import require_disposable
from .directory import directory_context
from .models import DisabilityType, Member, MemberEvent
from .review_services import open_review, record_findings
from .test_information_review import synthetic_review_policy, intake_data, finding_data
from .tests import create_member


@override_settings(INFORMATION_REVIEW_POLICY=synthetic_review_policy())
class MemberDirectoryTests(TestCase):
    def setUp(self):
        require_disposable()
        self.admin = get_user_model().objects.create_superuser('synthetic_directory_admin')
        self.viewer = get_user_model().objects.create_user('synthetic_directory_viewer', is_staff=True)
        grant(self.viewer, 'accounts.access_dashboard', 'members.view_member')
        self.member = create_member('DIRECTORY-001')
        self.url = reverse('member_directory')
        self.client.force_login(self.admin)

    def test_disability_filter_matches_multiple_types_and_legacy_fallback_without_duplicates(self):
        visual = self.member.disability_type
        hearing = DisabilityType.objects.create(name='Synthetic hearing classification')
        second = create_member('DIRECTORY-MULTI')
        second.disability_types.set([visual, hearing])
        third = create_member('DIRECTORY-AUTHORITATIVE')
        third.disability_types.set([hearing])
        response = self.client.get(self.url, {'disability': str(visual.pk)})
        self.assertEqual({row['id'] for row in response.context['directory_members']}, {str(self.member.pk), str(second.pk)})
        response = self.client.get(self.url, {'disability': str(hearing.pk)})
        self.assertEqual({row['id'] for row in response.context['directory_members']}, {str(second.pk), str(third.pk)})
        self.assertEqual(response.context['page_obj'].paginator.count, 2)
        self.assertEqual(self.client.get(self.url, {'disability': str(visual.pk), 'q': 'DIRECTORY-MULTI'})
            .context['page_obj'].paginator.count, 1)
        self.assertEqual(self.client.get(self.url, {'disability': str(visual.pk), 'status': 'inactive'})
            .context['page_obj'].paginator.count, 0)

    def test_disability_filter_keeps_inactive_types_and_rejects_unknown_input(self):
        kind = DisabilityType.objects.create(name='Synthetic retired classification', is_active=False)
        self.member.disability_types.set([kind])
        self.client.force_login(self.viewer)
        response = self.client.get(self.url, {'disability': str(kind.pk)})
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertContains(response, 'Synthetic retired classification (Inactive)')
        for value in ('unknown', '-1', '99999999999999999999'):
            response = self.client.get(self.url, {'disability': value})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['page_obj'].paginator.count, 0)
            self.assertContains(response, 'Choose a listed disability type.')

    def test_disability_filter_survives_pagination_and_no_javascript_form(self):
        for index in range(20):
            create_member(f'DIRECTORY-FILTER-{index}')
        kind = str(self.member.disability_type_id)
        response = self.client.get(self.url, {'disability': kind, 'status': 'active'})
        self.assertContains(response, 'name="disability"')
        self.assertContains(response, f'disability={kind}')
        response = self.client.get(self.url, {'disability': kind, 'status': 'active', 'page': 2})
        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertEqual(response.context['page_obj'].paginator.count, 21)
        self.assertEqual(response.context['disability'], kind)

    def test_alias_and_canonical_directory_keep_permissions_and_existing_routes(self):
        for url in (self.url, self.url + '/', reverse('members:list')):
            self.assertEqual(Client().get(url).status_code, 302)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Official member records')
            self.assertContains(response, f'href="{self.url}"')
            self.assertContains(response, f'href="{reverse("onsite_registration")}"')
            self.assertEqual(self.client.post(url).status_code, 405)
        self.assertRedirects(self.client.get(reverse('onsite_registration')),
                             reverse('membership:encode'), fetch_redirect_response=False)
        self.assertEqual(reverse('admin:index'), '/admin/')
        self.assertEqual(reverse('core:dashboard'), '/dashboard/')
        unauthorized = get_user_model().objects.create_user('synthetic_no_directory', is_staff=True)
        grant(unauthorized, 'accounts.access_dashboard')
        self.client.force_login(unauthorized)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_private_history_and_verification_are_not_serialized_for_directory_only_viewers(self):
        MemberEvent.objects.create(member=self.member, actor=self.admin, actor_label='Synthetic staff',
            action='profile_updated', notes='Private directory history example')
        self.client.force_login(self.viewer)
        response = self.client.get(self.url)
        preview = response.context['directory_members'][0]
        self.assertNotIn('note', preview)
        self.assertNotIn('verification', preview)
        self.assertEqual(preview['edit_url'], '')
        self.assertNotContains(response, 'Private directory history example')
        self.assertNotContains(response, 'Register new member')
        for field in ('birthdate', 'address', 'email', 'household_monthly_income', 'registration_profile'):
            self.assertNotIn(field, preview)
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertContains(response, 'Private directory history example')
        self.assertEqual(response.context['directory_members'][0]['verification'], 'PRPWD: manually verified')

    def test_real_counts_and_review_flags_stay_distinct(self):
        inactive = create_member('DIRECTORY-INACTIVE')
        Member.objects.filter(pk=inactive.pk).update(is_active=False)
        review = open_review(self.member.pk, user=self.admin, data=intake_data())
        response = self.client.get(self.url)
        self.assertEqual([row['value'] for row in response.context['directory_metrics']], ['2', '1'])
        row = response.context['directory_members'][0]
        self.assertEqual(row['status'], 'active')
        self.assertTrue(row['needs_review'])
        self.assertEqual(row['classification'], 'Visual Disability')
        record_findings(review.pk, user=self.admin, data=finding_data())
        response = self.client.get(self.url, {'status': 'review'})
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)

    def test_review_filter_keeps_private_program_review_permission_gate(self):
        application = ProgramApplication.objects.create(member=self.member, program=create_program(),
            public_reference='TEST-' + uuid4().hex, status='SELECTED')
        open_review(self.member.pk, user=self.admin, application_id=application.pk,
                    data=intake_data(kind='evaluation', trigger='clarification'))
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.url, {'status': 'review'}).status_code, 403)
        grant(self.viewer, 'members.view_informationreview')
        response = self.client.get(self.url, {'status': 'review'})
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        grant(self.viewer, 'programs.view_program', 'programs.view_programapplication')
        response = self.client.get(self.url, {'status': 'review'})
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        with override_settings(INFORMATION_REVIEW_POLICY=None):
            self.assertEqual(self.client.get(self.url, {'status': 'review'}).status_code, 403)
            self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_search_covers_later_pages_archived_records_remain_available(self):
        for index in range(21):
            create_member(f'DIRECTORY-PAGE-{index:02d}')
        target = create_member('DIRECTORY-SEARCH-END')
        Member.objects.filter(pk=target.pk).update(full_name='Zoe Synthetic', is_active=False,
                                                  archived_at=timezone.now())
        response = self.client.get(self.url, {'q': 'DIRECTORY-SEARCH-END', 'status': ''})
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(response.context['directory_members'][0]['status'], 'archived')
        self.assertEqual(response.context['directory_members'][0]['edit_url'], '')
        self.assertEqual(self.client.get(self.url, {'q': 'Zoe', 'status': 'active'}).context['page_obj'].paginator.count, 0)
        self.assertContains(self.client.get(self.url, {'q': 'not-a-record'}), 'No records found')
        self.assertEqual(self.client.get(self.url, {'page': 2}).context['page_obj'].number, 2)

    def test_preview_escapes_member_values_and_has_bounded_query_count(self):
        Member.objects.filter(pk=self.member.pk).update(full_name='<script>window.directoryLeak=1</script>')
        response = self.client.get(self.url)
        self.assertNotContains(response, '<script>window.directoryLeak=1</script>')
        self.assertContains(response, r'\u003Cscript\u003E')
        self.admin.get_all_permissions()
        with CaptureQueriesContext(connection) as before:
            directory_context(user=self.admin, query='', status='')
        for index in range(19):
            create_member(f'DIRECTORY-QUERY-{index}')
        with CaptureQueriesContext(connection) as after:
            directory_context(user=self.admin, query='', status='')
        self.assertEqual(len(after), len(before))

    def test_directory_assets_stay_off_other_pages(self):
        for url in (reverse('core:home'), reverse('core:dashboard'), reverse('membership:encode'),
                    reverse('members:detail', args=[self.member.pk])):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'css/member-directory.css')
            self.assertNotContains(response, 'js/member-directory.js')
