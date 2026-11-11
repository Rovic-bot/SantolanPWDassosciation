from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from ewaf.operational_testsupport import OperationalHelpers
from membership.tests import grant
from .catalog import capacity_context
from .tests import create_program


class ReferenceUITests(OperationalHelpers, TestCase):
    def setUp(self):
        self.setup_operational(additional=1)
        self.client.force_login(self.officer)

    def test_capacity_counts_decisions_not_applications_or_predecessors(self):
        capacity_context(self.program, self.officer)
        self.assertEqual(self.program.allocated_slots, 0)
        self.assertEqual(self.program.applications.count(), 2)
        self.lock_policy()
        run = self.calculate()
        self.choose(run)
        capacity_context(self.program, self.officer)
        self.assertEqual(self.program.allocated_slots, 1)
        self.assertEqual(self.program.available_slots, self.program.slots - 1)
        self.choose(run, expected_revision=1, outcome='NOT_SELECTED')
        capacity_context(self.program, self.officer)
        self.assertEqual(self.program.allocated_slots, 0)
        from ewaf.operational_models import OperationalDecision
        self.assertTrue(OperationalDecision.objects.filter(program=self.program, outcome='SELECTED').exists())

    def test_shared_cards_combine_code_search_filters_and_sort(self):
        create_program(name='Unrelated empty program')
        params = {'q': self.program.public_code, 'assistance_type': self.program.assistance_type,
                  'status': self.program.status, 'with_applications': '1', 'sort': 'az'}
        destinations = (
            ('programs:manage_list', 'programs:manage_detail', 'Open program'),
            ('core:application_programs', 'programs:applications', 'Review program'),
            ('assistance:release_programs', 'assistance:program_releases', 'View Releases'),
        )
        for url, destination, action in destinations:
            response = self.client.get(reverse(url), params)
            self.assertEqual([p.pk for p in response.context['page_obj']], [self.program.pk])
            if url == 'programs:manage_list':
                self.assertContains(response, 'portfolio-program')
                self.assertContains(response, 'Application demand')
                self.assertContains(response, '0 allocated')
            elif url == 'assistance:release_programs':
                self.assertContains(response, 'data-release-portfolio')
                self.assertContains(response, 'Receipts recorded')
            else:
                self.assertContains(response, 'chooser-card')
                self.assertContains(response, 'Application demand')
                self.assertContains(response, 'unallocated')
            self.assertContains(response, f'href="{reverse(destination, args=[self.program.pk])}"')
            self.assertContains(response, action)
        response = self.client.get(reverse('programs:manage_list'), {'q': 'no-such-program'})
        self.assertContains(response, 'data-result-count="0"')
        self.assertContains(response, 'No programs found')

    def test_ewaf_scope_and_configuration_are_preserved_and_releases_include_all_programs(self):
        other = create_program(name='Non-EWAF assistance')
        configuration = self.lock_policy()
        ewaf = self.client.get(reverse('ewaf:operational_programs'))
        self.assertEqual([p.pk for p in ewaf.context['page_obj']], [self.program.pk])
        self.assertContains(ewaf, 'ewaf-state-ready')
        self.assertContains(ewaf, 'Open EWAF')
        releases = self.client.get(reverse('assistance:release_programs'))
        self.assertEqual({p.pk for p in releases.context['page_obj']}, {self.program.pk, other.pk})
        self.assertNotContains(releases, 'program-configuration-status')
        for url in ('ewaf:operational_programs', 'assistance:release_programs'):
            empty = self.client.get(reverse(url), {'q': 'no-such-program'})
            self.assertContains(empty, 'No ')

    def test_applicant_listing_sort_membership_and_profile_identifiers(self):
        url = reverse('programs:applications', args=[self.program.pk])
        response = self.client.get(url, {'sort': 'az', 'membership': 'active'})
        names = [app.member.full_name for app in response.context['page_obj']]
        self.assertEqual(names, sorted(names))
        self.assertContains(response, self.member.control_number)
        self.assertContains(response, 'Verified')
        self.assertEqual(len(self.client.get(url, {'membership': 'archived'}).context['page_obj']), 0)
        detail = self.client.get(reverse('programs:application_detail', args=[self.program.pk, self.application.pk]))
        for label in ('Application review', 'Copy application reference', 'Submitted application',
                      'Application History', 'Download', self.application.public_reference):
            self.assertContains(detail, label)
        self.assertContains(detail, 'data-copy-value="' + self.member.control_number + '"')
        from .review_context import applicant_context
        self.application.member.version += 1
        stale = applicant_context(self.application, self.officer)
        self.assertEqual(stale['review_result'], 'Review needed')
        self.assertEqual(stale['review_code'], 'review')
        self.assertEqual(self.application.assistance_case.eligibility_id, 'eligible')

    def test_limited_users_do_not_receive_sensitive_profile_or_capacity(self):
        user = get_user_model().objects.create_user('reference_limited', is_staff=True)
        grant(user, 'accounts.access_dashboard', 'programs.view_program', 'programs.view_programapplication')
        self.client.force_login(user)
        page = self.client.get(reverse('programs:manage_list'))
        self.assertContains(page, 'Usage restricted')
        detail = self.client.get(reverse('programs:application_detail', args=[self.program.pk, self.application.pk]))
        for private in ('Income &amp; Household', 'Personal Information', 'Disability &amp; Health',
                        'Copy Program Score', 'Edit Profile'):
            self.assertNotContains(detail, private)
        self.assertNotContains(detail, '?preview=1')
        self.assertEqual(self.client.post(reverse('programs:application_detail', args=[self.program.pk, self.application.pk]),
                                         {'action': 'eligibility'}).status_code, 403)
        for url in ('ewaf:operational_programs', 'assistance:release_programs'):
            self.assertEqual(self.client.get(reverse(url)).status_code, 403)
        self.client.logout()
        for url in ('ewaf:operational_programs', 'assistance:release_programs'):
            self.assertEqual(self.client.get(reverse(url)).status_code, 302)
