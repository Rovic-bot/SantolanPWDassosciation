"""Navigation is permission-aware presentation, never a substitute for RBAC."""
import html
import re
from uuid import uuid4
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from assistance.services import VIEW_PERMISSIONS
from assistance.tests import seed_statuses
from announcements.models import Announcement
from programs.tests import create_program
from programs.testsupport import private_media


MODULES = ['Dashboard', 'Members', 'Programs & Events', 'Applications & Verification',
           'EWAF & Selection', 'Announcements & CMS', 'Reports & Exports', 'Administration']


def grant(user, *permissions):
    for permission in permissions:
        app, codename = permission.split('.')
        user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))


def sidebar(response):
    return response.content.decode().split('<nav aria-label="Administration navigation">', 1)[1].split('</nav>', 1)[0]


def modules(response):
    return [html.unescape(label) for label in re.findall(r'data-module-label>(.*?)</span>', sidebar(response))]


class WorkspaceNavigationTests(TestCase):
    def test_operational_ewaf_navigation_matches_complete_backend_permissions(self):
        from ewaf.operational_services import VIEW
        user = self.limited('ewaf.view_operational')
        self.assertNotIn('Program EWAF &amp; beneficiary decisions', sidebar(self.client.get(reverse('core:dashboard'))))
        self.assertEqual(self.client.get(reverse('ewaf:operational_programs')).status_code, 403)
        grant(user, *VIEW)
        response = self.client.get(reverse('ewaf:operational_programs'))
        self.assertEqual(response.status_code, 200)
        self.assert_current(response, 'selection', 'EWAF')
        self.assertContains(response, 'aria-label="Filter EWAF programs"')

    def test_g14_entry_requires_explicit_configuration_view_permissions(self):
        from ewaf.configuration_services import VIEW
        user = self.limited('programs.view_program')
        self.assertNotIn('Configuration drafts &amp; validation', sidebar(self.client.get(reverse('core:dashboard'))))
        grant(user, *VIEW)
        response = self.client.get(reverse('ewaf:configuration_list'))
        self.assertNotIn('Configuration drafts &amp; validation', sidebar(response))
        self.assertEqual(response.status_code, 200)  # Historical permission checks remain.

    def setUp(self):
        private_media(self)
        seed_statuses()
        self.admin = get_user_model().objects.create_superuser('navigation_admin')
        self.client.force_login(self.admin)

    def test_g12_evidence_entry_requires_explicit_private_view_permissions(self):
        from ewaf.evidence import VIEW
        user = self.limited('programs.view_program', 'programs.view_programapplication', 'ewaf.view_rankingrun')
        self.assertNotIn('Criterion evidence &amp; readiness', sidebar(self.client.get(reverse('core:dashboard'))))
        grant(user, *VIEW)
        response = self.client.get(reverse('ewaf:evidence_queue'))
        self.assertEqual(response.status_code, 200)
        self.assert_current(response, 'applications', 'Program Applications & Eligibility')
        self.assertNotIn('Criterion evidence &amp; readiness', sidebar(response))

    def limited(self, *permissions, dashboard=True):
        user = get_user_model().objects.create_user('restricted_navigation', is_staff=True)
        grant(user, *permissions, *(['accounts.access_dashboard'] if dashboard else []))
        self.client.force_login(user)
        return user

    def assert_current(self, response, group, label=None):
        nav = sidebar(response)
        self.assertIn(f'data-group-key="{group}" data-current="true"', nav)
        self.assertEqual(nav.count('data-current="true"'), 1)
        if label:
            current = re.findall(r'<a[^>]*aria-current="page"[^>]*>(.*?)</a>', nav)
            self.assertEqual([html.unescape(value) for value in current], [label])

    def test_eight_modules_in_required_order_on_custom_and_native_admin(self):
        for route in ('core:dashboard', 'admin:index', 'admin:documents_documenttype_changelist'):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(modules(response), MODULES)
            self.assertEqual(sidebar(response).count('<details '), 8)
            self.assertNotIn('>Documents</a>', sidebar(response))
            self.assertNotIn('>Document types</a>', sidebar(response))
            self.assertNotIn('>Document requirements</a>', sidebar(response))

    def test_every_visible_submodule_link_resolves_and_actions_are_not_duplicated(self):
        response = self.client.get(reverse('core:dashboard'))
        urls = [html.unescape(value) for value in re.findall(r'<a href="([^"]+)"', sidebar(response))]
        self.assertEqual(len(urls), len(set(urls)))
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_members_are_one_group_with_the_existing_three_destinations(self):
        response = self.client.get(reverse('members:list'))
        nav = sidebar(response)
        for route in ('member_directory', 'membership:encode', 'membership:review_home'):
            self.assertIn(f'href="{reverse(route)}"', nav)
        self.assertEqual(modules(response).count('Members'), 1)
        self.assert_current(response, 'members', 'Member Directory')
        self.assert_current(self.client.get(reverse('membership:encode')), 'members', 'Onsite registration')
        self.assert_current(self.client.get(reverse('membership:list'), follow=True), 'members', 'Membership reviews')

    def test_restricted_encoder_has_no_privileged_group_even_with_auth_permissions(self):
        self.limited('membership.view_membershipapplication', 'membership.encode_membershipapplication',
                     'auth.view_user', 'auth.change_user', 'auth.view_group', 'auth.change_group')
        response = self.client.get(reverse('membership:list'), follow=True)
        self.assertEqual(modules(response), ['Dashboard', 'Members'])
        self.assertNotIn('Member Directory', sidebar(response))
        for route in ('members:list', 'admin:auth_user_changelist', 'admin:auth_group_changelist',
                      'admin:audit_securityevent_changelist', 'core:application_programs', 'core:content_list'):
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)

    def test_application_review_access_does_not_require_eligibility_or_create_permissions(self):
        self.limited('programs.view_program', 'programs.view_programapplication')
        program = create_program()
        response = self.client.get(reverse('core:application_programs'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('programs:applications', args=[program.pk]))
        self.assert_current(response, 'applications', 'Program Applications & Eligibility')
        self.assertNotIn('Eligibility review', sidebar(response))
        self.assertNotIn('Create program', sidebar(response))
        self.assertNotIn('Prepare program results', sidebar(response))
        self.assertEqual(self.client.get(reverse('programs:applications', args=[program.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('assistance:queue')).status_code, 403)
        self.assertEqual(self.client.get(reverse('programs:photo_queue')).status_code, 403)

    def test_photo_link_requires_all_backend_view_permissions(self):
        user = self.limited('programs.view_program', 'programs.view_applicationphoto')
        response = self.client.get(reverse('core:dashboard'))
        self.assertNotIn('Photo Verification Queue', sidebar(response))
        self.assertEqual(self.client.get(reverse('programs:photo_queue')).status_code, 403)
        grant(user, 'programs.view_programapplication')
        response = self.client.get(reverse('programs:photo_queue'))
        self.assertEqual(response.status_code, 200)
        self.assert_current(response, 'applications', 'Program Applications & Eligibility')
        self.assertNotIn('Photo Verification Queue', sidebar(response))
        self.assertEqual(self.client.get(reverse('programs:photo_review', args=[uuid4()])).status_code, 403)

    def test_private_evidence_and_audit_direct_urls_remain_denied(self):
        self.limited('membership.view_membershipapplication')
        routes = [reverse('programs:photo', args=[uuid4(), uuid4()]),
                  reverse('programs:document', args=[uuid4(), uuid4(), uuid4()]),
                  reverse('membership:document', args=[uuid4()]),
                  reverse('admin:admin_logentry_changelist')]
        for route in routes:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 403)

    def test_results_preparation_navigation_requires_its_complete_existing_gate(self):
        user = self.limited('announcements.view_announcement', 'announcements.add_announcement',
                            'announcements.change_announcement', 'programs.view_program', 'programs.view_programapplication')
        response = self.client.get(reverse('announcements:manage_list'), follow=True)
        self.assertNotIn('Prepare program results', sidebar(response))
        self.assertEqual(self.client.get(reverse('announcements:choose_results')).status_code, 403)
        grant(user, 'assistance.view_assistancecase')
        response = self.client.get(reverse('announcements:choose_results'))
        self.assertEqual(response.status_code, 200)
        self.assert_current(response, 'content', 'Announcements')
        item = Announcement.objects.create(title='Synthetic restricted publication', content='Approved synthetic wording.')
        detail = reverse('announcements:manage_detail', args=[item.pk])
        self.assertNotContains(self.client.get(detail), '>Apply publication change</button>')
        self.assertEqual(self.client.post(detail, {'action': 'published', 'version': item.version, 'confirm': 'on'}).status_code, 403)
        item.refresh_from_db()
        self.assertEqual(item.status, 'draft')

    def test_history_remains_protected_and_reports_are_available(self):
        response = self.client.get(reverse('ewaf:configuration'))
        self.assert_current(response, 'selection')
        self.assertNotIn('Historical EWAF information', sidebar(response))
        self.assertContains(response, 'Historical records are preserved')
        self.assertContains(response, 'Open four-criterion EWAF')
        self.assertNotContains(response, 'Reports and exports are not yet available')
        reports = sidebar(response).split('data-group-key="reports"', 1)[1].split('</details>', 1)[0]
        self.assertIn(reverse('reports:members'), reports)
        self.assertNotIn('<button', reports)
        self.assertEqual(self.client.post(reverse('ewaf:configuration')).status_code, 405)

    def test_g15_navigation_requires_explicit_policy_permissions(self):
        from ewaf.scoring_inputs import VIEW
        user = self.limited(*VIEW)
        response = self.client.get(reverse('ewaf:scoring_list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Scoring-policy diagnostics', sidebar(response))
        user.user_permissions.clear()
        grant(user, 'programs.view_program', 'accounts.access_dashboard')
        response = self.client.get(reverse('core:dashboard'))
        self.assertNotIn('Scoring-policy diagnostics', sidebar(response))
        self.assertEqual(self.client.get(reverse('ewaf:scoring_list')).status_code, 403)

    def test_selection_and_release_links_use_existing_filters_and_permissions(self):
        self.limited(*VIEW_PERMISSIONS, 'assistance.decide_assistance')
        response = self.client.get(reverse('assistance:queue') + '?eligibility=eligible')
        self.assertTrue(response.context['selection'])
        self.assert_current(response, 'applications', 'Program Applications & Eligibility')
        self.assertNotIn('Assistance releases', sidebar(response))
        self.assertNotIn('EWAF availability', sidebar(response))
        self.assertEqual(self.client.get(reverse('ewaf:configuration')).status_code, 403)
        self.assertEqual(self.client.get(reverse('assistance:release', args=[uuid4()])).status_code, 403)

    def test_eligibility_only_reviewer_keeps_active_review_group_for_filtered_queue(self):
        self.limited(*VIEW_PERMISSIONS)
        response = self.client.get(reverse('assistance:queue') + '?eligibility=eligible')
        self.assert_current(response, 'applications', 'Program Applications & Eligibility')
        self.assertNotIn('EWAF &amp; Selection', sidebar(response))

    def test_current_indicators_follow_program_event_content_and_native_pages(self):
        cases = [('programs:manage_list', 'programs', 'Program Management'),
                 ('programs:create', 'programs', 'Program Management'),
                 ('events:manage_list', 'programs', 'Events Calendar'),
                 ('events:create', 'programs', 'Events Calendar'),
                 ('events:observances', 'programs', 'Events Calendar'),
                 ('announcements:manage_list', 'content', 'Announcements'),
                 ('core:content_list', 'content', 'Content Management'),
                 ('assistance:statuses', 'administration', None),
                 ('admin:documents_documenttype_changelist', 'administration', None),
                 ('admin:documents_membershipdocumentrequirement_changelist', 'administration', None),
                 ('admin:documents_documenttype_add', 'administration', None),
                 ('admin:documents_membershipdocumentrequirement_add', 'administration', None)]
        for route, group, label in cases:
            with self.subTest(route=route):
                self.assert_current(self.client.get(reverse(route)), group, label)
        response = self.client.get(reverse('assistance:release_programs'))
        self.assert_current(response, 'selection', 'Assistance releases')

    def test_native_admin_without_dashboard_permission_sees_only_allowed_native_actions(self):
        user = self.limited('documents.view_documenttype', dashboard=False)
        for visible, hidden in (('documenttype', 'membershipdocumentrequirement'),
                                ('membershipdocumentrequirement', 'documenttype')):
            user.user_permissions.clear()
            grant(user, 'documents.view_' + visible)
            visible_url = reverse('admin:documents_' + visible + '_changelist')
            hidden_url = reverse('admin:documents_' + hidden + '_changelist')
            response = self.client.get(visible_url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(modules(response), [])
            self.assertNotIn('>Documents</a>', sidebar(response))
            self.assertNotIn(f'href="{visible_url}"', sidebar(response))
            self.assertNotIn(reverse('core:dashboard'), sidebar(response))
            self.assertContains(response, 'aria-label="Document configuration"')
            self.assertNotContains(response, f'href="{hidden_url}"')
            self.assertEqual(self.client.get(hidden_url).status_code, 403)
        self.assertEqual(self.client.get(reverse('core:dashboard')).status_code, 403)

    def test_application_chooser_is_read_only_searchable_paginated_and_private(self):
        program = create_program()
        response = self.client.get(reverse('core:application_programs'), {'q': program.name, 'page': 'invalid'})
        self.assertContains(response, program.name)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.post(reverse('core:application_programs')).status_code, 405)
        self.assertEqual(self.client.head(reverse('core:application_programs')).status_code, 200)
        response = self.client.get(reverse('core:application_programs'), {'q': 'no synthetic matching program'})
        self.assertContains(response, 'No programs found')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('core:application_programs')).status_code, 302)
