"""Program builder uses existing permissions, form validation and audited saves."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from membership.tests import grant
from .forms import ProgramSetupForm
from .models import Program, ProgramLog, ProgramRequirement
from .publication_guidance import STANDARD_GUIDANCE
from .tests import program_data, create_program
from .test_ui_cleanup import seed_catalog


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
class ProgramBuilderTests(TestCase):
    def setUp(self):
        seed_catalog()
        self.admin = get_user_model().objects.create_superuser('synthetic_builder_admin')
        self.client.force_login(self.admin)
        self.url = reverse('program_builder')
        self.headers = {'HTTP_X_PROGRAM_BUILDER': '1'}

    def data(self, **overrides):
        result = {key: value for key, value in program_data(benefit='Synthetic community support.', **overrides).items() if value is not None}
        result.update({'requirements-TOTAL_FORMS': '0', 'requirements-INITIAL_FORMS': '0'})
        # HTTP datetime-local values are local wall time, not UTC strings.
        for name in ('registration_opens_at', 'registration_closes_at', 'starts_at', 'ends_at'):
            if name in result:
                result[name] = timezone.localtime(result[name]).strftime('%Y-%m-%dT%H:%M')
        return result

    def questions(self, data):
        data['requirements-TOTAL_FORMS'] = '3'
        for index, kind in enumerate(('text', 'document', 'acknowledgement')):
            data.update({f'requirements-{index}-label': f'Synthetic question {index + 1}',
                         f'requirements-{index}-kind': kind, f'requirements-{index}-instructions': 'Synthetic instructions.',
                         f'requirements-{index}-is_required': 'on'})
        return data

    def test_blank_disability_selection_includes_all_types_without_rewriting_terms(self):
        from members.disability_catalog import current_types
        from members.tests import create_member
        from .services import require_disability, change_publication
        response = self.client.post(self.url, self.data(eligible_disability_types=[]), **self.headers)
        self.assertEqual(response.status_code, 200)
        program = Program.objects.get()
        self.assertTrue(program.allows_all_disability_types)
        self.assertFalse(program.eligible_disability_types.exists())
        types = list(current_types().filter(is_active=True))
        self.assertEqual(list(program.eligibility_profile_types), types)
        for item in types:
            member = create_member(f'ALL-TYPES-{item.pk}')
            member.disability_type = item
            member.save(update_fields=['disability_type'])
            member.disability_types.set([item])
            require_disability(program, member)
        change_publication(program.pk, user=self.admin, version=program.version, action='published')
        program.refresh_from_db()
        before = (program.version, program.history.count())
        private = self.client.get(reverse('programs:manage_detail', args=[program.pk]))
        self.assertContains(private, 'All disability types are automatically included')
        self.assertContains(private, '<small>Included</small>', count=len(types), html=True)
        public = Client().get(reverse('programs:detail', args=[program.pk]))
        for item in types:
            self.assertContains(public, item.name)
        program.refresh_from_db()
        self.assertEqual((program.version, program.history.count()), before)
        self.assertFalse(program.eligible_disability_types.exists())

    def test_selected_disability_types_remain_restricted_in_profile_and_screening(self):
        from members.disability_catalog import current_types
        from members.tests import create_member
        from .services import require_disability
        visual = current_types().get(name='Visual Disability')
        cancer = current_types().get(name='Cancer (RA 11215)')
        program = create_program(eligible_disability_types=[visual.pk])
        self.assertFalse(program.allows_all_disability_types)
        self.assertEqual(list(program.eligibility_profile_types), [visual])
        member = create_member('RESTRICTED-TYPE')
        member.disability_type = cancer
        member.save(update_fields=['disability_type'])
        member.disability_types.set([cancer])
        with self.assertRaisesMessage(ValidationError, 'do not match'):
            require_disability(program, member)
        page = self.client.get(reverse('programs:manage_detail', args=[program.pk]))
        self.assertNotContains(page, 'All disability types are automatically included')
        self.assertContains(page, '<small>Included</small>', count=1, html=True)

    def test_create_and_edit_share_simplified_builder(self):
        for url in (self.url, self.url + '/', reverse('programs:create')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            for name in ProgramSetupForm().fields:
                self.assertContains(response, f'name="{name}"')
            for name in ProgramSetupForm.omitted_fields:
                self.assertNotContains(response, f'name="{name}"')
            self.assertContains(response, 'Add Requirements')
            self.assertNotContains(response, 'Additional documents or questions')
            self.assertContains(response, 'Draft program setup')
            self.assertContains(response, 'aria-current="page">Program Management')
            self.assertNotContains(response, 'name="budget"')
            self.assertContains(response, 'data-range="registration"')
            self.assertContains(response, 'data-range="delivery"')
            self.assertNotContains(response, 'Build a program')
            self.assertNotContains(response, 'Programs &middot; New draft')
        item = create_program()
        response = self.client.get(reverse('programs:edit', args=[item.pk]))
        self.assertContains(response, 'program-builder.js')
        self.assertContains(response, '<h1>Edit program</h1>')
        self.assertContains(response, 'Update program details')
        self.assertContains(response, 'aria-label="Update status"')
        for name in ProgramSetupForm(instance=item).fields:
            self.assertContains(response, f'name="{name}"')
        for name in ProgramSetupForm.omitted_fields:
            self.assertNotContains(response, f'name="{name}"')
        for url in ('/', reverse('event_workspace'), reverse('program_portfolio')):
            self.assertNotContains(self.client.get(url), 'program-builder.css')

    def test_save_in_place_is_private_and_requirements_are_not_duplicated(self):
        data = self.questions(self.data())
        data.update(status='published', policy_authorized_at=timezone.now().isoformat())
        response = self.client.post(self.url, data, **self.headers)
        self.assertContains(response, 'data-saved="true"')
        item = Program.objects.get()
        self.assertEqual(item.status, 'draft')
        self.assertIsNone(item.published_at)
        self.assertIsNone(item.policy_authorized_at)
        self.assertEqual(item.configured_requirements.count(), 3)
        self.assertContains(response, 'Draft saved')
        version = item.version
        changed = self.data(name='Updated synthetic title', version=version, notes='Clarified draft title.')
        response = self.client.post(reverse('programs:edit', args=[item.pk]), changed, **self.headers)
        self.assertContains(response, 'data-saved="true"')
        item.refresh_from_db()
        self.assertEqual(Program.objects.count(), 1)
        self.assertEqual(item.name, 'Updated synthetic title')
        self.assertEqual(item.configured_requirements.count(), 3)
        self.assertGreater(item.version, version)
        self.assertContains(response, 'Program updated')
        self.assertTrue(ProgramLog.objects.filter(program=item, action='created').exists())
        self.assertTrue(ProgramLog.objects.filter(program=item, action='updated', notes='Clarified draft title.').exists())
        self.assertContains(self.client.get(reverse('programs:edit', args=[item.pk]) + '?builder=1'), 'data-program-builder')
        self.assertContains(self.client.get(reverse('programs:edit', args=[item.pk])), 'program-builder.js')

    def test_simplified_draft_can_be_reviewed_and_published_without_removed_fields(self):
        data = self.questions(self.data())
        for name in ProgramSetupForm.omitted_fields:
            data.pop(name, None)
        response = self.client.post(self.url, data, **self.headers)
        self.assertContains(response, 'data-saved="true"')
        item = Program.objects.get()
        self.assertEqual(item.status, 'draft')
        self.assertEqual(item.configured_requirements.count(), 3)
        self.assertEqual(item.requirements, '')
        for name, text in STANDARD_GUIDANCE.items():
            self.assertEqual(getattr(item, name), text)
            self.assertEqual(item.history.get(action='created').changes[name], {'before': '', 'after': text})
        self.assertIsNone(item.policy_authorized_at)
        detail_url = reverse('programs:manage_detail', args=[item.pk])
        review = self.client.get(detail_url)
        self.assertTrue(review.context['detail_ready'])
        for text in STANDARD_GUIDANCE.values():
            self.assertContains(review, text)
        self.assertRedirects(self.client.post(detail_url,
            {'action': 'published', 'version': item.version}), detail_url)
        item.refresh_from_db()
        self.assertEqual(item.status, 'published')
        self.assertEqual(item.policy_authorized_by, self.admin)
        self.assertTrue(item.registration_available)
        public = self.client.get(reverse('programs:detail', args=[item.pk]))
        self.assertNotContains(public, STANDARD_GUIDANCE['selection_method'])
        self.assertNotContains(public, 'Photo instructions')
        self.assertNotContains(public, 'A current calendar photo remains required.')

    def test_removed_fields_preserve_retained_values_and_ignore_forged_input(self):
        from .services import save_program
        item = save_program(user=self.admin, data=self.data())
        original = {name: getattr(item, name) for name in ProgramSetupForm.omitted_fields}
        data = self.data(name='Corrected draft title', version=item.version,
                         notes='Corrected the title only.')
        data.update({name: 'Forged replacement' for name in ProgramSetupForm.omitted_fields})
        response = self.client.post(reverse('programs:edit', args=[item.pk]), data, **self.headers)
        self.assertContains(response, 'data-saved="true"')
        item.refresh_from_db()
        self.assertEqual(item.name, 'Corrected draft title')
        for name, value in original.items():
            self.assertEqual(getattr(item, name), value)
        changes = item.history.get(action='updated').changes
        self.assertTrue(set(ProgramSetupForm.omitted_fields).isdisjoint(changes))

    def test_stale_save_cannot_overwrite_a_draft(self):
        self.client.post(self.url, self.data(), **self.headers)
        item = Program.objects.get()
        response = self.client.post(reverse('programs:edit', args=[item.pk]), self.data(version=0, name='Stale title'), **self.headers)
        self.assertContains(response, 'This program changed')
        self.assertNotContains(response, 'data-saved="true"')
        item.refresh_from_db()
        self.assertNotEqual(item.name, 'Stale title')

    def test_invalid_fields_and_dates_stay_in_form_without_saving(self):
        data = self.data(name='')
        data['registration_closes_at'] = data['registration_opens_at']
        response = self.client.post(self.url, data, **self.headers)
        self.assertNotContains(response, 'This field is required.')
        self.assertContains(response, 'Applications must close after they open.')
        self.assertEqual(Program.objects.count(), 0)
        self.assertContains(response, 'data-bound="true"')

    def test_requirements_failure_rolls_back_whole_draft(self):
        with patch('programs.services.save_requirement', side_effect=ValidationError('Synthetic audit failure')):
            response = self.client.post(self.url, self.questions(self.data()), **self.headers)
        self.assertContains(response, 'Synthetic audit failure')
        self.assertEqual(Program.objects.count(), 0)
        self.assertEqual(ProgramRequirement.objects.count(), 0)
        self.assertEqual(ProgramLog.objects.count(), 0)
        data = self.data()
        data['requirements-TOTAL_FORMS'] = '51'
        self.assertNotContains(self.client.post(self.url, data, **self.headers), 'data-saved="true"')
        self.assertEqual(Program.objects.count(), 0)

    def test_permissions_and_csrf_remain_enforced(self):
        staff = get_user_model().objects.create_user('synthetic_builder_viewer', is_staff=True)
        grant(staff, 'accounts.access_dashboard', 'programs.view_program')
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        grant(staff, 'programs.add_program')
        self.assertEqual(self.client.post(self.url, self.questions(self.data()), **self.headers).status_code, 403)
        self.assertEqual(Program.objects.count(), 0)
        self.assertContains(self.client.post(self.url, self.data(), **self.headers), 'data-saved="true"')
        item = Program.objects.get()
        self.assertEqual(self.client.post(reverse('programs:edit', args=[item.pk]), self.data(version=item.version), **self.headers).status_code, 403)
        secure = Client(enforce_csrf_checks=True)
        secure.force_login(self.admin)
        self.assertEqual(secure.post(self.url, self.data(), **self.headers).status_code, 403)

    def test_published_builder_preserves_locked_terms_and_publish_permission(self):
        item = create_program(benefit='Synthetic public support.')
        url = reverse('programs:edit', args=[item.pk])
        published_at, authorized_at = item.published_at, item.policy_authorized_at
        response = self.client.get(url)
        self.assertContains(response, 'Update program details, capacity and dates here.')
        self.assertContains(response, '<span class="builder-badge">Published</span>')
        self.assertContains(response, '<dd class="builder-private">Public</dd>')
        data = self.data(name='Updated published program', version=item.version, notes='Corrected public title.')
        response = self.client.post(url, data, **self.headers)
        self.assertContains(response, 'data-saved="true"')
        item.refresh_from_db()
        self.assertEqual(item.name, 'Updated published program')
        self.assertEqual(item.status, 'published')
        self.assertEqual(item.published_at, published_at)
        self.assertEqual(item.policy_authorized_at, authorized_at)
        self.assertTrue(item.history.filter(action='updated').exists())
        editor = get_user_model().objects.create_user('synthetic_builder_editor', is_staff=True)
        grant(editor, 'accounts.access_dashboard', 'programs.view_program', 'programs.change_program')
        self.client.force_login(editor)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, self.data(version=item.version), **self.headers).status_code, 403)

    def test_javascript_disabled_submission_still_uses_existing_save(self):
        response = self.client.post(self.url, self.data())
        item = Program.objects.get()
        self.assertRedirects(response, reverse('programs:manage_detail', args=[item.pk]), fetch_redirect_response=False)
        self.assertEqual(item.status, 'draft')
