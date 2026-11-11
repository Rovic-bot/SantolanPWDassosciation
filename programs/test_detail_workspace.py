"""Program-profile presentation, access boundaries and preserved publication forms."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from membership.tests import grant
from members.tests import create_member
from .models import Program, ProgramApplication, ProgramRequirement, ProgramLog
from .services import save_program
from .tests import program_data


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
                   EWAF_VAULT_ENABLED=True)
class ProgramDetailWorkspaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.actor = get_user_model().objects.create_superuser('synthetic_profile_admin')
        cls.program = save_program(user=cls.actor, data=program_data(name='Medical Access Week',
            assistance_type='Healthcare & Medical Aid', benefit='Synthetic community health access.', slots=2))
        cls.url = reverse('programs:manage_detail', args=[cls.program.pk])
        cls.alias = reverse('program_detail') + f'?program={cls.program.pk}'
        ProgramRequirement.objects.create(program=cls.program, label='Synthetic evidence', kind='document',
            instructions='Present the approved evidence.', is_required=False, is_active=False)
        for index in range(3):
            ProgramApplication.objects.create(program=cls.program, member=create_member(f'PROFILE-{index}'),
                public_reference=f'PRIVATE-PROFILE-APP-{index}')

    def setUp(self):
        self.client.force_login(self.actor)

    def test_live_profile_aliases_links_and_read_only_render(self):
        before = list(ProgramLog.objects.values_list('pk', flat=True))
        for url in (self.url, self.alias, reverse('program_detail') + f'/?program={self.program.pk}'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'data-program-profile')
            self.assertContains(response, 'Program operations')
            self.assertContains(response, 'Visual Disability')
            self.assertContains(response, 'Synthetic evidence')
            self.assertContains(response, 'Optional')
            self.assertContains(response, 'Inactive')
            for removed in ('aria-label="Program lifecycle"', 'Publication readiness', 'Beneficiary selection'):
                self.assertNotContains(response, removed)
            self.assertNotContains(response, 'Other status changes')
            self.assertContains(response, 'id="program-status-form"')
            self.assertContains(response, reverse('programs:edit', args=[self.program.pk]))
            self.assertContains(response, reverse('programs:applications', args=[self.program.pk]))
            self.assertContains(response, reverse('programs:proposal', args=[self.program.pk]) + '?download=1')
            self.assertIn('no-store', response['Cache-Control'])
            self.assertNotContains(response, 'PRIVATE-PROFILE-APP-')
            self.assertEqual(response.context['detail_completed'], 4)
            self.assertTrue(response.context['detail_ready'])
        self.assertEqual(list(ProgramLog.objects.values_list('pk', flat=True)), before)

    def test_unlimited_capacity_and_ewaf_capacity_are_presented_separately(self):
        response = self.client.get(self.url)
        self.assertIsNone(response.context['detail_capacity']['demand'])
        self.assertContains(response, '<strong>3 / Unlimited</strong>', html=True)
        self.assertNotContains(response, 'data-capacity-available')
        self.assertNotContains(response, 'application above capacity')
        self.assertTrue(response.context['detail_ready'])
        self.assertFalse(response.context['detail_lifecycle'][-1]['done'])
        self.assertEqual([row['label'] for row in response.context['detail_lifecycle']], ['Draft', 'Published'])
        # A separate synthetic EWAF draft must retain a real positive limit.
        Program.objects.filter(pk=self.program.pk).update(ewaf_applicable=True, slots=2)
        response = self.client.get(self.url)
        self.assertEqual(response.context['detail_capacity']['demand'], 150)
        self.assertEqual(response.context['detail_capacity']['progress'], 100)
        self.assertContains(response, '<strong>3</strong> applications', html=True)
        self.assertContains(response, '<span data-capacity-available>2 unallocated</span>', html=True)
        self.assertContains(response, '1 application above capacity')
        Program.objects.filter(pk=self.program.pk).update(slots=None)
        response = self.client.get(self.url)
        self.assertNotContains(response, 'data-capacity-available')
        self.assertFalse(response.context['detail_ready'])

    def test_schedule_capacity_and_assessment_are_visible_without_policy_copy(self):
        from django.utils.formats import date_format
        start = timezone.now() + timedelta(days=4)
        end = start + timedelta(days=1)
        Program.objects.filter(pk=self.program.pk).update(
            starts_at=start, ends_at=end, resubmission_closes_at=end)
        response = self.client.get(self.url)
        for label in ('Schedule &amp; capacity', 'Registration', 'Opens', 'Closes',
                      'Program dates', 'Starts', 'Ends', 'Correction deadline', 'Beneficiary slots', 'Use EWAF'):
            self.assertContains(response, label)
        for value in (self.program.registration_opens_at, self.program.registration_closes_at, start, end):
            self.assertContains(response, date_format(timezone.localtime(value), 'M j, Y'))
            self.assertContains(response, date_format(timezone.localtime(value), 'g:i A'))
        self.assertContains(response, 'Application demand')
        self.assertContains(response, '<dt>Use EWAF</dt><dd>No</dd>', html=True)
        for removed in ('How selection works', 'Identity evidence'):
            self.assertNotContains(response, removed)
        # The collapsed audit history must retain the original policy values.
        visible_details = response.content.decode().split('<details class="profile-history', 1)[0]
        self.assertNotIn(self.program.selection_method, visible_details)
        self.assertNotIn(self.program.photo_instructions, visible_details)

    def test_publication_round_trip_retains_real_authorization_and_reasoned_withdrawal(self):
        response = self.client.post(self.alias, {'version': self.program.version, 'action': 'published'})
        self.assertRedirects(response, self.url)
        program = Program.objects.get(pk=self.program.pk)
        self.assertEqual(program.status, 'published')
        self.assertEqual(program.policy_authorized_by, self.actor)
        page = self.client.get(self.url)
        self.assertEqual(page.context['detail_completed'], 5)
        self.assertContains(page, 'Program is live')
        self.assertNotContains(page, 'aria-current="step"')
        self.assertNotContains(page, 'id="publish-program-form"')
        self.assertContains(page, 'Unpublish and archive', html=True)
        stale = self.client.post(self.url, {'version': self.program.version, 'action': 'published'})
        self.assertTrue(stale.context['publish_form'].errors)
        self.assertContains(stale, 'role="alert"')
        self.assertTrue(ProgramLog.objects.filter(program=program, action='policy_authorized').exists())
        Program.objects.filter(pk=program.pk).update(registration_closes_at=timezone.now() - timedelta(hours=1))
        closed = self.client.get(self.url)
        self.assertContains(closed, 'Program published')
        self.assertNotContains(closed, 'Program is live')
        self.assertNotContains(closed, 'Visible to the public and accepting applications.')

    def test_missing_ewaf_configuration_is_not_faked_or_marked_ready(self):
        Program.objects.filter(pk=self.program.pk).update(ewaf_applicable=True)
        response = self.client.get(self.url)
        self.assertFalse(response.context['detail_ready'])
        self.assertNotContains(response, 'Open Configuration Vault')
        self.assertContains(response, 'Complete program setup')
        self.assertNotContains(response, '70 points')
        blocked = self.client.post(self.url, {'version': self.program.version, 'action': 'published'})
        self.assertTrue(blocked.context['publish_form'].errors)
        self.assertEqual(Program.objects.get(pk=self.program.pk).status, 'draft')

    def test_access_and_action_permissions_and_history_privacy(self):
        viewer = get_user_model().objects.create_user('profile_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'programs.view_program')
        self.client.force_login(viewer)
        Program.objects.filter(pk=self.program.pk).update(ewaf_applicable=True)
        response = self.client.get(self.alias)
        self.assertFalse(response.context['program'].can_view_capacity)
        self.assertNotContains(response, 'data-capacity-available')
        self.assertNotContains(response, '<strong>3</strong> applications', html=True)
        self.assertNotContains(response, '<strong>3 / 2</strong>', html=True)
        self.assertNotContains(response, '150% demand')
        self.assertNotContains(response, '1 application above capacity')
        self.assertContains(response, 'Application demand restricted')
        self.assertNotContains(response, 'slots left')
        self.assertContains(response, 'Detailed history requires a separate permission.')
        for text in ('id="publish-program-form"', 'Edit program', 'Review applications', 'View EWAF configuration'):
            self.assertNotContains(response, text)
        self.assertEqual(self.client.post(self.alias, {'action': 'published', 'version': 0}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.alias).status_code, 302)

    def test_optional_fields_history_expansion_and_invalid_alias(self):
        self.assertRedirects(self.client.get(reverse('program_detail')), reverse('program_portfolio'))
        self.assertEqual(self.client.get(reverse('program_detail'), {'program': 'bad-id'}).status_code, 404)
        self.assertEqual(self.client.post(reverse('program_detail'), {'action': 'published'}).status_code, 404)
        response = self.client.get(self.url, {'page': 1})
        self.assertContains(response, 'id="program-history" open')
        self.assertNotContains(response, 'PDAO approval')
        Program.objects.filter(pk=self.program.pk).update(name='<script>private()</script>', status='archived',
            starts_at=timezone.now() - timedelta(days=3), ends_at=timezone.now() - timedelta(days=1),
            registration_opens_at=timezone.now() - timedelta(days=5),
            registration_closes_at=timezone.now() - timedelta(days=4))
        response = self.client.get(self.url)
        self.assertNotContains(response, '<script>private()')
        self.assertContains(response, 'Program archived')
        self.assertFalse(response.context['detail_lifecycle'][-1]['done'])

    def test_assets_are_scoped_to_details(self):
        for url in (reverse('core:home'), reverse('core:dashboard'), reverse('program_builder')):
            response = self.client.get(url)
            self.assertNotContains(response, 'css/program-detail.css')
            self.assertNotContains(response, 'js/program-detail.js')
        for url in (reverse('program_portfolio'), reverse('application_workspace')):
            response = self.client.get(url)
            self.assertContains(response, 'id="program-details-dialog"')
            self.assertContains(response, 'js/program-dialog.js')
