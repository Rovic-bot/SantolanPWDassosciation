from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from membership.tests import grant
from members.tests import create_member
from .forms import ProgramSetupForm
from .models import Program, ProgramApplication, ProgramLog
from .services import change_publication, save_program
from .tests import program_data
from .test_ui_cleanup import seed_catalog


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True,
                   EWAF_VAULT_ENABLED=True, EWAF_DATASET_POLICY_ENABLED=True)
class ProgramLifecycleTests(TestCase):
    def setUp(self):
        seed_catalog()
        self.user = get_user_model().objects.create_superuser('lifecycle_admin')
        self.client.force_login(self.user)
        from ewaf import vault_services as vault
        from ewaf.dataset_methods import COMPOSITE
        from ewaf.test_composite_ses import proposal
        for status in ('DRAFT', 'LOCKED'):
            vault.record_ses_weights(user=self.user, expected=vault.token(), proposal=proposal(),
                reason='SYNTHETIC lifecycle test weights; no Association approval.', status=status, method=COMPOSITE)

    def draft_data(self, **changes):
        # Even incomplete drafts require capacity and applicable disability types.
        return {'version': 0, 'slots': 2,
                'eligible_disability_types': program_data()['eligible_disability_types'], **changes}

    def test_partial_draft_saves_and_missing_details_block_publication(self):
        response = self.client.post(reverse('program_builder'), self.draft_data(), HTTP_X_PROGRAM_BUILDER='1')
        self.assertContains(response, 'data-saved="true"')
        program = Program.objects.get()
        self.assertEqual(program.status, 'draft')
        self.assertEqual(program.name, '')
        self.assertIsNone(program.registration_closes_at)
        self.assertIsNone(program.registration_opens_at)
        detail = self.client.get(reverse('programs:manage_detail', args=[program.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertFalse(detail.context['detail_ready'])
        self.assertContains(detail, 'Untitled program')
        with self.assertRaisesMessage(ValidationError, 'before publishing'):
            change_publication(program.pk, user=self.user, version=program.version, action='published')
        program.refresh_from_db()
        self.assertIsNone(program.policy_authorized_at)
        self.assertIsNone(program.published_at)
        self.assertEqual(self.client.get(reverse('programs:detail', args=[program.pk])).status_code, 404)

    def test_partial_draft_can_be_updated_without_reason_or_closing_date(self):
        from django.utils import timezone
        program = save_program(user=self.user, data=self.draft_data())
        program = save_program(pk=program.pk, user=self.user, data=self.draft_data(
            version=program.version, name='Work in progress', registration_opens_at=timezone.now()))
        self.assertIsNotNone(program.registration_opens_at)
        self.assertIsNone(program.registration_closes_at)
        self.assertTrue(program.history.get(action='updated').notes)
        self.assertFalse(program.registration_available)

    def test_invalid_supplied_values_still_fail(self):
        for data in ({'slots': -1}, {'registration_opens_at': 'invalid'}, {'assistance_type': 'unknown'}):
            with self.subTest(data=data), self.assertRaises(ValidationError):
                save_program(user=self.user, data=self.draft_data(**data))
        self.assertFalse(Program.objects.exists())

    def published(self):
        program = save_program(user=self.user, data=program_data(ewaf_applicable=True, benefit='Synthetic benefit'))
        return change_publication(program.pk, user=self.user, version=program.version, action='published')

    def edit_data(self, program, **changes):
        form = ProgramSetupForm(instance=program)
        return {name: '' if form.initial.get(name) is None else form.initial.get(name, '')
                for name in form.fields} | {'notes': 'Correct published details.', **changes}

    def test_published_edit_is_public_audited_and_keeps_authorization(self):
        program = self.published()
        before = (program.published_at, program.policy_authorized_at, program.public_code)
        response = self.client.post(reverse('programs:edit', args=[program.pk]),
            self.edit_data(program, name='Updated published title', description='Corrected public description.',
                           slots=10), HTTP_X_PROGRAM_BUILDER='1')
        self.assertContains(response, 'data-saved="true"')
        program.refresh_from_db()
        self.assertEqual(program.status, 'published')
        self.assertEqual(program.slots, 10)
        self.assertEqual((program.published_at, program.policy_authorized_at, program.public_code), before)
        self.assertContains(self.client.get(reverse('programs:detail', args=[program.pk])), 'Updated published title')
        self.assertIn('name', program.history.get(action='updated').changes)

    def test_published_missing_details_and_failed_audit_do_not_change_record(self):
        program = self.published()
        before = Program.objects.values().get(pk=program.pk)
        with self.assertRaises(ValidationError):
            save_program(pk=program.pk, user=self.user, setup_only=True, data=self.edit_data(program, name=''))
        with patch('programs.services.record_log', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                save_program(pk=program.pk, user=self.user, setup_only=True,
                             data=self.edit_data(program, name='Must roll back'))
        self.assertEqual(Program.objects.values().get(pk=program.pk), before)

    def test_unpublish_returns_editable_draft_and_retains_history(self):
        program = self.published()
        published_at = program.published_at
        application = ProgramApplication.objects.create(program=program, member=create_member('ARCHIVE-KEPT'),
            public_reference='SYNTHETIC-ARCHIVE-KEPT')
        application_before = ProgramApplication.objects.values().get(pk=application.pk)
        url = reverse('programs:manage_detail', args=[program.pk])
        response = self.client.post(url, {'action': 'unpublish', 'version': program.version,
                                         'confirm': 'on', 'notes': 'Withdraw from public listings.'})
        self.assertRedirects(response, url)
        program.refresh_from_db()
        self.assertEqual(program.status, 'draft')
        self.assertEqual(program.published_at, published_at)
        self.assertFalse(program.registration_available)
        self.assertFalse(Program.objects.public().filter(pk=program.pk).exists())
        self.assertTrue(program.history.filter(action='draft').exists())
        self.assertEqual(ProgramApplication.objects.values().get(pk=application.pk), application_before)
        self.assertEqual(program.history.get(action='draft').notes, 'Withdraw from public listings.')
        self.assertEqual(self.client.get(reverse('programs:detail', args=[program.pk])).status_code, 404)
        listing = self.client.get(reverse('program_portfolio'), {'status': 'draft'})
        self.assertContains(listing, program.name)

        self.assertContains(self.client.get(url), 'Edit program')
        response = self.client.post(reverse('programs:edit', args=[program.pk]),
            self.edit_data(program, name='Corrected draft title'), HTTP_X_PROGRAM_BUILDER='1')
        self.assertContains(response, 'data-saved="true"')
        program.refresh_from_db()
        response = self.client.post(url, {'action': 'published', 'version': program.version})
        self.assertRedirects(response, url)
        program.refresh_from_db()
        self.assertEqual(program.status, 'published')
        self.assertEqual(program.name, 'Corrected draft title')
        self.assertEqual(ProgramApplication.objects.values().get(pk=application.pk), application_before)

    def test_archive_buttons_open_a_read_only_review_for_the_current_status(self):
        for published in (True, False):
            program = self.published() if published else save_program(user=self.user, data=self.draft_data())
            action = 'unpublish' if published else 'archived'
            label = 'Unpublish to draft' if published else 'Archive program'
            url = reverse('programs:manage_detail', args=[program.pk])
            review_url = f'{url}?action={action}#program-status-form'
            before = Program.objects.values().get(pk=program.pk)
            history = list(program.history.values())
            detail = self.client.get(url)
            self.assertContains(detail, f'href="{review_url}" data-program-status-review>{label}</a>')
            self.assertNotContains(self.client.get(reverse('program_portfolio')), f'href="{review_url}"')
            review = self.client.get(url, {'action': action})
            self.assertTrue(review.context['archiving'])
            self.assertEqual(review.context['form']['action'].value(), action)
            self.assertTrue(review.context['form']['action'].is_hidden)
            self.assertContains(review, 'data-program-archive-review')
            self.assertContains(review, 'Existing applications and history are kept.')
            self.assertEqual(Program.objects.values().get(pk=program.pk), before)
            self.assertEqual(list(program.history.values()), history)

    def test_incomplete_draft_can_be_archived_with_a_reason_and_confirmation(self):
        program = save_program(user=self.user, data=self.draft_data())
        url = reverse('programs:manage_detail', args=[program.pk])
        response = self.client.post(url + '?action=archived', {'action': 'archived', 'version': program.version,
            'notes': 'An unused draft.', 'confirm': 'on'}, follow=True)
        program.refresh_from_db()
        self.assertEqual(program.status, 'archived')
        self.assertIsNone(program.published_at)
        self.assertContains(response, 'Program archived. Applications and history are retained.')
        self.assertNotContains(response, 'profile-archive-button')
        self.assertNotContains(self.client.get(reverse('program_portfolio'), {'status': 'archived'}),
            f'?action=archived#program-status-form')
        self.assertEqual(program.history.get(action='archived').changes['status'],
            {'before': 'draft', 'after': 'archived'})

    def test_archive_review_requires_reason_confirmation_current_version_and_csrf(self):
        program = self.published()
        url = reverse('programs:manage_detail', args=[program.pk]) + '?action=unpublish'
        data = {'action': 'unpublish', 'version': program.version, 'notes': 'Review withdrawal.', 'confirm': 'on'}
        before = Program.objects.values().get(pk=program.pk)
        for invalid in ({'notes': ''}, {'confirm': ''}, {'version': program.version + 1}, {'action': 'archived'}):
            response = self.client.post(url, {**data, **invalid})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(url, data).status_code, 403)
        self.assertEqual(Program.objects.values().get(pk=program.pk), before)
        self.assertFalse(program.history.filter(action='archived').exists())

    def test_archive_buttons_and_review_require_publication_permission(self):
        program = self.published()
        viewer = get_user_model().objects.create_user('archive_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'programs.view_program')
        self.client.force_login(viewer)
        url = reverse('programs:manage_detail', args=[program.pk])
        for page_url in (url, url + '?action=unpublish', reverse('program_portfolio')):
            response = self.client.get(page_url)
            self.assertNotContains(response, 'Unpublish to draft')
            self.assertNotContains(response, 'data-program-archive-review')
        self.assertEqual(self.client.post(url, {'action': 'unpublish', 'version': program.version,
            'notes': 'Not authorized.', 'confirm': 'on'}).status_code, 403)
        program.refresh_from_db()
        self.assertEqual(program.status, 'published')

    def test_unpublish_checks_permissions_stale_version_and_atomic_audit(self):
        program = self.published()
        editor = get_user_model().objects.create_user('lifecycle_editor', is_staff=True)
        grant(editor, 'accounts.access_dashboard', 'programs.view_program', 'programs.change_program')
        with self.assertRaises(PermissionDenied):
            change_publication(program.pk, user=editor, version=program.version, action='unpublish', notes='Reason')
        with self.assertRaises(ValidationError):
            change_publication(program.pk, user=self.user, version=program.version + 1, action='unpublish', notes='Reason')
        with patch('programs.services.record_log', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                change_publication(program.pk, user=self.user, version=program.version, action='unpublish', notes='Reason')
        program.refresh_from_db()
        self.assertEqual(program.status, 'published')

    def test_cancelled_removed_from_filters_and_direct_draft_action_unpublishes(self):
        program = self.published()
        response = self.client.get(reverse('program_portfolio'), {'status': 'cancelled'})
        self.assertNotIn('cancelled', dict(response.context['statuses']))
        self.assertNotIn('cancelled', dict(response.context['registration_options']))
        self.assertEqual(response.context['status'], '')
        change_publication(program.pk, user=self.user, version=program.version, action='draft', notes='Unpublish')
        program.refresh_from_db()
        self.assertEqual(program.status, 'draft')

    def test_database_rejects_incomplete_public_record(self):
        program = save_program(user=self.user, data=self.draft_data())
        from django.utils import timezone
        with self.assertRaises(IntegrityError), transaction.atomic():
            Program.objects.filter(pk=program.pk).update(status='published', published_at=timezone.now())

    def test_archive_rejects_non_drafts_in_service_and_view(self):
        program = self.published()
        url = reverse('programs:manage_detail', args=[program.pk])
        before = Program.objects.values().get(pk=program.pk)
        with self.assertRaisesMessage(ValidationError, 'Only a draft program'):
            change_publication(program.pk, user=self.user, version=program.version,
                               action='archived', notes='Attempt to bypass draft.')
        response = self.client.post(url, {'action': 'archived', 'version': program.version,
                                         'notes': 'Attempt to bypass draft.', 'confirm': 'on'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertEqual(Program.objects.values().get(pk=program.pk), before)
        self.assertNotContains(self.client.get(url), '?action=archived#program-status-form')

    def test_unpublished_draft_keeps_evaluation_rules_locked_for_existing_applications(self):
        program = self.published()
        selection_method = program.selection_method
        from ewaf.operational_models import OperationalConfiguration
        configurations = list(OperationalConfiguration.objects.filter(program=program).values())
        ProgramApplication.objects.create(program=program, member=create_member('DRAFT-LOCKED'),
                                          public_reference='SYNTHETIC-DRAFT-LOCKED')
        change_publication(program.pk, user=self.user, version=program.version,
                           action='unpublish', notes='Correct public description.')
        program.refresh_from_db()
        save_program(pk=program.pk, user=self.user, setup_only=True,
                     data=self.edit_data(program, selection_method='Replace approved rules'))
        program.refresh_from_db()
        self.assertEqual(program.selection_method, selection_method)
        self.assertEqual(list(OperationalConfiguration.objects.filter(program=program).values()), configurations)
