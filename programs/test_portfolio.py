"""Read-only portfolio presentation, filtering, and permission regression checks."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assistance.models import AssistanceCase, EligibilityStatus
from members.tests import create_member
from membership.tests import grant
from .models import Program, ProgramApplication
from .tests import create_program


@override_settings(PDAO_ENFORCEMENT_ENABLED=False)
class ProgramPortfolioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('synthetic_portfolio_admin')
        now = timezone.now()
        cls.medical = create_program(name='Medical Access Week', public_code='SP-000001', assistance_type='Healthcare', slots=2,
            starts_at=now + timedelta(days=8), registration_closes_at=now + timedelta(days=4))
        cls.devices = create_program(name='Assistive Device Distribution', public_code='SP-000002', assistance_type='Assistive Devices',
            slots=None, registration_closes_at=now + timedelta(days=2))
        cls.closed = create_program(name='Financial Assistance Q4', public_code='SP-000003', assistance_type='Financial', slots=4,
            registration_opens_at=now - timedelta(days=10), registration_closes_at=now - timedelta(days=1))
        cls.draft = create_program(name='Nutrition Support', assistance_type='Food & Nutrition', slots=3)
        Program.objects.filter(pk=cls.draft.pk).update(status='draft', published_at=None)
        for status in ('cancelled', 'archived'):
            item = create_program(name=f'Synthetic {status} program')
            Program.objects.filter(pk=item.pk).update(status=status)
        cls.applications = []
        for index in range(3):
            member = create_member(f'SYNTH-PORTFOLIO-{index}')
            cls.applications.append(ProgramApplication.objects.create(program=cls.medical, member=member,
                public_reference=f'SYNTH-PORTFOLIO-APP-{index}'))
        for index, program in enumerate((cls.devices, cls.closed)):
            ProgramApplication.objects.create(program=program, member=member,
                public_reference=f'SYNTH-PORTFOLIO-OTHER-{index}')
        EligibilityStatus.objects.get_or_create(code='eligible', defaults={'label': 'Eligible'})
        AssistanceCase.objects.create(application=cls.applications[0], eligibility_id='eligible',
            eligibility_label='Eligible', reviewed_at=now, member_version=0, program_version=0, decision='approved')

    def setUp(self):
        self.client.force_login(self.admin)

    def test_alias_and_existing_route_preserve_actions_and_navigation(self):
        for url in (reverse('program_portfolio'), '/admin/programs/', reverse('programs:manage_list')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'Program portfolio')
            self.assertContains(response, f'href="{reverse("program_builder")}"')
            self.assertNotContains(response, f'href="{reverse("programs:pdao_readiness")}"')
            self.assertContains(response, 'aria-current="page">Program Management')
        self.assertEqual(self.client.post(reverse('program_portfolio')).status_code, 405)

    def test_totals_are_not_inflated_by_application_joins_or_filters(self):
        response = self.client.get(reverse('program_portfolio'), {'q': 'Medical'})
        self.assertEqual([item['value'] for item in response.context['portfolio_metrics']], [6, 3, 5, 1])
        self.assertEqual(response.context['portfolio_capacity'],
            {'applications': 0, 'places': 0, 'percent': None, 'progress': 0, 'unspecified': 0, 'unlimited': 6})
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(response.context['portfolio_deadline'].pk, self.devices.pk)
        self.assertEqual(response.context['portfolio_attention'].pk, self.draft.pk)

    def test_non_ewaf_capacity_is_unlimited_despite_retained_counts(self):
        response = self.client.get(reverse('program_portfolio'), {'q': self.medical.public_code})
        program = response.context['page_obj'][0]
        self.assertIsNone(program.portfolio['demand'])
        self.assertEqual(program.portfolio['progress'], 0)
        self.assertIsNone(program.available_slots)
        self.assertNotContains(response, '150% demand')
        self.assertContains(response, 'Unlimited')
        self.assertNotContains(response, '1 application above capacity')
        self.assertContains(response, '1 allocated')
        self.assertNotContains(response, '100% filled')

    def test_missing_capacity_and_schedule_are_not_fabricated(self):
        response = self.client.get(reverse('program_portfolio'), {'q': self.devices.public_code})
        self.assertContains(response, 'Unlimited')
        self.assertContains(response, 'Not scheduled')
        self.assertIsNone(response.context['page_obj'][0].portfolio['demand'])

    def test_filters_preserve_status_and_registration_semantics(self):
        url = reverse('program_portfolio')
        for params in ({'status': 'closed'}, {'status': 'published', 'registration': 'ended'},
                       {'q': self.closed.public_code, 'assistance_type': 'Financial',
                        'with_applications': '1', 'sort': 'az'}):
            response = self.client.get(url, params)
            self.assertEqual([p.pk for p in response.context['page_obj']], [self.closed.pk])
            self.assertContains(response, 'Registration closed')
            self.assertContains(response, 'data-status="published">Published')
        self.closed.refresh_from_db()
        self.assertEqual(self.closed.status, 'published')
        empty = self.client.get(url, {'q': '<script>unknown program</script>'})
        self.assertContains(empty, 'No programs found')
        self.assertNotContains(empty, '<script>unknown program</script>')

    def test_pagination_retains_filters_and_sort(self):
        for index in range(21):
            create_program(name=f'Synthetic paged program {index:02d}')
        response = self.client.get(reverse('program_portfolio'), {'q': 'Synthetic paged', 'sort': 'az', 'page': '2'})
        self.assertEqual(response.context['page_obj'].paginator.count, 21)
        self.assertEqual(len(response.context['page_obj']), 1)
        self.assertContains(response, 'Synthetic paged program 20')
        self.assertContains(response, 'data-portfolio-page')

    def test_unavailable_program_is_not_a_registration_deadline(self):
        Program.objects.filter(pk=self.devices.pk).update(policy_authorized_at=None)
        response = self.client.get(reverse('program_portfolio'))
        self.assertEqual(response.context['portfolio_deadline'].pk, self.medical.pk)
        Program.objects.filter(status='published').update(policy_authorized_at=None)
        response = self.client.get(reverse('program_portfolio'))
        self.assertIsNone(response.context['portfolio_deadline'])
        self.assertContains(response, 'No open registration')

    def test_permissions_protect_route_allocations_and_actions(self):
        user = get_user_model().objects.create_user('synthetic_portfolio_viewer', is_staff=True)
        grant(user, 'accounts.access_dashboard')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('program_portfolio')).status_code, 403)
        grant(user, 'programs.view_program')
        response = self.client.get(reverse('program_portfolio'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usage restricted')
        self.assertNotContains(response, 'Create program')
        self.assertNotContains(response, 'Review approvals')
        self.assertNotContains(response, 'class="btn portfolio-review-button"')
        self.assertNotContains(response, 'places unallocated')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('program_portfolio')).status_code, 302)

    def test_portfolio_assets_are_scoped_to_program_management(self):
        for route in ('core:home', 'core:dashboard', 'member_directory', 'membership:encode',
                      'programs:create', 'admin:index', 'core:application_programs'):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'css/program-portfolio.css')
            self.assertNotContains(response, 'js/program-portfolio.js')
