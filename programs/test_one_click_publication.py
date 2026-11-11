"""Synthetic publication tests; publishing records authority in the same action."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from membership.tests import grant
from scripts.durable_test_runner import require_disposable
from ewaf import vault_services as vault
from ewaf.dataset_methods import COMPOSITE
from ewaf.operational_models import OperationalConfiguration
from ewaf import test_composite_ses as composite_tests
from .models import Program, ProgramLog, PDAOApprovalRecord, ProgramApprovalBinding
from .publication_guidance import STANDARD_GUIDANCE
from .services import save_program, change_publication, require_open
from .tests import program_data


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
                   EWAF_VAULT_ENABLED=True, EWAF_DATASET_POLICY_ENABLED=True)
class OneClickPublicationTests(TransactionTestCase):
    def setUp(self):
        require_disposable()
        self.user = get_user_model().objects.create_superuser('SYNTHETIC-PUBLISH', password='synthetic-only')
        self.program = save_program(user=self.user, data=program_data(benefit='SYNTHETIC purpose'))
        self.url = reverse('programs:manage_detail', args=[self.program.pk])
        self.client.force_login(self.user)

    def test_publish_form_has_one_button_no_reason_confirmation_or_authorize_step(self):
        page = self.client.get(self.url)
        self.assertContains(page, 'id="publish-program-form"')
        form = page.content.decode().split('id="publish-program-form"', 1)[1].split('</form>', 1)[0]
        self.assertIn('value="published">Approve and publish</button>', form)
        self.assertNotIn('name="notes"', form)
        self.assertNotIn('name="confirm"', form)
        self.assertNotContains(page, 'value="authorize_policy"')
        self.assertNotContains(page, '<h2>PDAO approval</h2>', html=True)
        self.assertNotContains(page, 'Record any required external approvals.')
        before_version = self.program.version
        response = self.client.post(self.url, {'action': 'published', 'version': before_version})
        self.assertRedirects(response, self.url)
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'published')
        self.assertEqual(self.program.version, before_version + 1)
        self.assertEqual(self.program.policy_authorized_by, self.user)
        self.assertIsNotNone(self.program.policy_authorized_at)
        self.assertIsNotNone(self.program.published_at)
        self.assertTrue(self.program.registration_available)
        require_open(self.program)
        self.assertTrue(Program.objects.accepting_applications().filter(pk=self.program.pk).exists())
        self.assertFalse(PDAOApprovalRecord.objects.exists())
        self.assertFalse(ProgramApprovalBinding.objects.exists())
        logs = list(self.program.history.filter(action__in=('policy_authorized', 'published')).order_by('pk'))
        self.assertEqual([row.action for row in logs], ['policy_authorized', 'published'])
        self.assertTrue(all(row.actor_id == self.user.pk and row.notes.strip() for row in logs))
        self.assertNotContains(self.client.get(self.url), 'id="publish-program-form"')

    def test_duplicate_stale_submission_cannot_publish_or_authorize_twice(self):
        payload = {'action': 'published', 'version': self.program.version}
        self.client.post(self.url, payload)
        before = ProgramLog.objects.count()
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['publish_form'].errors)
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_optional_description_and_purpose_do_not_block_publication_or_later_editing(self):
        from .forms import ProgramSetupForm
        for blank in ('', '   '):
            with self.subTest(blank=repr(blank)):
                program = save_program(user=self.user, setup_only=True,
                    data=program_data(description=blank, benefit=blank, ewaf_applicable=False))
                url = reverse('programs:manage_detail', args=[program.pk])
                page = self.client.get(url)
                self.assertTrue(page.context['detail_ready'])
                self.assertContains(page, 'Ready for final approval')
                self.assertEqual(program.publication_errors(), {})
                self.assertRedirects(self.client.post(url, {'action': 'published', 'version': program.version}), url)
                program.refresh_from_db()
                self.assertEqual((program.status, program.description, program.benefit), ('published', '', ''))
                self.assertTrue(program.registration_available)
                self.assertContains(self.client.get(reverse('programs:detail', args=[program.pk])), program.name)
                form = ProgramSetupForm(instance=program)
                self.assertFalse(form.fields['description'].required)
                self.assertFalse(form.fields['benefit'].required)
                self.assertEqual(program.history.filter(action='published').count(), 1)
                program.full_clean()

    def test_existing_empty_draft_previews_guidance_without_writes_then_publishes(self):
        Program.objects.filter(pk=self.program.pk).update(selection_method='', photo_instructions='  ')
        before = ProgramLog.objects.count()
        review = self.client.get(self.url)
        self.assertTrue(review.context['detail_ready'])
        self.assertNotContains(review, 'How selection works')
        self.assertNotContains(review, 'Identity evidence')
        for text in STANDARD_GUIDANCE.values():
            self.assertNotContains(review, text)
        self.program.refresh_from_db()
        self.assertEqual(self.program.selection_method, '')
        self.assertEqual(self.program.photo_instructions, '  ')
        self.assertEqual(ProgramLog.objects.count(), before)
        self.assertRedirects(self.client.post(self.url,
            {'action': 'published', 'version': self.program.version}), self.url)
        self.program.refresh_from_db()
        self.assertTrue(self.program.registration_available)
        require_open(self.program)
        self.assertTrue(Program.objects.accepting_applications().filter(pk=self.program.pk).exists())
        audit = self.program.history.get(action='policy_authorized')
        for name, text in STANDARD_GUIDANCE.items():
            self.assertEqual(getattr(self.program, name), text)
            self.assertEqual(audit.changes[name]['after'], text)
        self.assertEqual(audit.changes['selection_method']['before'], '')
        self.assertEqual(audit.changes['photo_instructions']['before'], '  ')

    def test_filling_missing_guidance_preserves_custom_text(self):
        original = self.program.selection_method
        Program.objects.filter(pk=self.program.pk).update(photo_instructions='')
        change_publication(self.program.pk, user=self.user, version=self.program.version, action='published')
        self.program.refresh_from_db()
        self.assertEqual(self.program.selection_method, original)
        self.assertEqual(self.program.photo_instructions, STANDARD_GUIDANCE['photo_instructions'])

    def test_missing_capacity_leaves_draft_guidance_and_authorization_unchanged(self):
        Program.objects.filter(pk=self.program.pk).update(ewaf_applicable=True, slots=None, selection_method='', photo_instructions='')
        before = ProgramLog.objects.count()
        response = self.client.post(self.url, {'action': 'published', 'version': self.program.version})
        self.assertContains(response, 'Slots: Complete this field before publishing.')
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'draft')
        self.assertEqual(self.program.selection_method, '')
        self.assertEqual(self.program.photo_instructions, '')
        self.assertIsNone(self.program.policy_authorized_at)
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_previously_published_or_authorized_terms_are_never_backfilled(self):
        for protected in ({'published_at': timezone.now()},
                          {'policy_authorized_at': timezone.now(), 'policy_authorized_by': self.user}):
            with self.subTest(protected=tuple(protected)):
                Program.objects.filter(pk=self.program.pk).update(selection_method='', photo_instructions='',
                    policy_authorized_at=None, policy_authorized_by=None, published_at=None)
                Program.objects.filter(pk=self.program.pk).update(**protected)
                before = ProgramLog.objects.count()
                page = self.client.get(self.url)
                self.assertFalse(page.context['detail_ready'])
                with self.assertRaises(ValidationError):
                    change_publication(self.program.pk, user=self.user, version=self.program.version, action='published')
                self.program.refresh_from_db()
                self.assertEqual(self.program.status, 'draft')
                self.assertEqual(self.program.selection_method, '')
                self.assertEqual(self.program.photo_instructions, '')
                self.assertEqual(ProgramLog.objects.count(), before)

    def test_external_approval_preserves_its_exact_terms_even_when_guidance_is_missing(self):
        from .test_approved_terms import TermsHelpers
        Program.objects.filter(pk=self.program.pk).update(selection_method='', photo_instructions='')
        self.program.refresh_from_db()
        helper = TermsHelpers()
        helper.program, helper.officer = self.program, self.user
        helper.record()
        self.program.refresh_from_db()
        before = ProgramLog.objects.count()
        with self.assertRaisesMessage(ValidationError, 'protected'):
            change_publication(self.program.pk, user=self.user, version=self.program.version, action='published')
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'draft')
        self.assertEqual(self.program.selection_method, '')
        self.assertEqual(self.program.photo_instructions, '')
        self.assertIsNone(self.program.policy_authorized_at)
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_program_with_applications_cannot_gain_new_guidance_implicitly(self):
        from members.tests import create_member
        from .models import ProgramApplication
        Program.objects.filter(pk=self.program.pk).update(selection_method='', photo_instructions='')
        ProgramApplication.objects.create(program=self.program, member=create_member('GUIDANCE-EXISTING'),
            public_reference='SYNTHETIC-GUIDANCE-EXISTING')
        before = ProgramLog.objects.count()
        with self.assertRaisesMessage(ValidationError, 'existing application records'):
            change_publication(self.program.pk, user=self.user, version=self.program.version, action='published')
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'draft')
        self.assertEqual(self.program.selection_method, '')
        self.assertEqual(self.program.photo_instructions, '')
        self.assertIsNone(self.program.policy_authorized_at)
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_missing_external_approval_is_not_created_by_publish(self):
        before = ProgramLog.objects.count()
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            page = self.client.post(self.url, {'action': 'published', 'version': self.program.version})
        self.assertContains(page, 'explicitly reconciled approval')
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'draft')
        self.assertIsNone(self.program.policy_authorized_at)
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_missing_vault_approval_rolls_back_authorization_and_audit(self):
        Program.objects.filter(pk=self.program.pk).update(ewaf_applicable=True, slots=1, selection_method='', photo_instructions='')
        before = ProgramLog.objects.count()
        page = self.client.post(self.url, {'action': 'published', 'version': self.program.version})
        self.assertContains(page, 'EWAF Configuration Vault')
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'draft')
        self.assertIsNone(self.program.policy_authorized_at)
        self.assertIsNone(self.program.policy_authorized_by)
        self.assertEqual(self.program.selection_method, '')
        self.assertEqual(self.program.photo_instructions, '')
        self.assertEqual(ProgramLog.objects.count(), before)
        self.assertFalse(OperationalConfiguration.objects.filter(program=self.program).exists())

    def test_one_click_uses_approved_weights_while_scoring_rules_are_pending(self):
        for state in ('DRAFT', 'LOCKED'):
            weights = vault.record_ses_weights(user=self.user, expected=vault.token(),
                proposal=composite_tests.proposal(), status=state, method=COMPOSITE,
                reason='SYNTHETIC reviewed weights')
        program = save_program(user=self.user, setup_only=True,
            data=program_data(description='', benefit='', ewaf_applicable=True))
        change_publication(program.pk, user=self.user, version=program.version, action='published')
        program.refresh_from_db()
        self.assertEqual(program.status, 'published')
        config = OperationalConfiguration.objects.filter(program=program).first()
        self.assertEqual(config.vault_revision_id, weights.pk)
        self.assertEqual(config.source['contract'], 'approved_weights_intake_v1')
        self.assertIsNone(config.dataset_policy_id)
        self.assertTrue(program.registration_available)
        require_open(program)
        self.assertFalse(PDAOApprovalRecord.objects.exists())

    def test_existing_empty_ewaf_draft_binds_guidance_before_its_intake_configuration(self):
        from ewaf.intake_policy import require_configuration
        for state in ('DRAFT', 'LOCKED'):
            vault.record_ses_weights(user=self.user, expected=vault.token(),
                proposal=composite_tests.proposal(), status=state, method=COMPOSITE,
                reason='SYNTHETIC reviewed weights')
        program = save_program(user=self.user, data=program_data(benefit='SYNTHETIC existing EWAF', ewaf_applicable=True))
        Program.objects.filter(pk=program.pk).update(selection_method='', photo_instructions='')
        change_publication(program.pk, user=self.user, version=program.version, action='published')
        program.refresh_from_db()
        self.assertEqual(program.status, 'published')
        self.assertEqual(program.selection_method, STANDARD_GUIDANCE['selection_method'])
        self.assertEqual(program.photo_instructions, STANDARD_GUIDANCE['photo_instructions'])
        self.assertIsNotNone(require_configuration(program))
        self.assertTrue(program.registration_available)

    def test_publish_audit_failure_rolls_back_both_actions(self):
        Program.objects.filter(pk=self.program.pk).update(selection_method='', photo_instructions='')
        original = ProgramLog.objects.create
        def fail_publication(**kwargs):
            if kwargs['action'] == 'published':
                raise ValidationError('SYNTHETIC publication audit unavailable')
            return original(**kwargs)
        before = ProgramLog.objects.count()
        with patch.object(ProgramLog.objects, 'create', side_effect=fail_publication):
            with self.assertRaisesMessage(ValidationError, 'audit unavailable'):
                change_publication(self.program.pk, user=self.user, version=self.program.version, action='published')
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'draft')
        self.assertIsNone(self.program.policy_authorized_at)
        self.assertEqual(self.program.selection_method, '')
        self.assertEqual(self.program.photo_instructions, '')
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_permissions_csrf_and_get_do_not_publish(self):
        viewer = get_user_model().objects.create_user('SYNTHETIC-PUBLISH-VIEWER', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'programs.view_program')
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(self.url), 'id="publish-program-form"')
        self.assertEqual(self.client.post(self.url, {'action': 'published', 'version': self.program.version}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            change_publication(self.program.pk, user=viewer, version=self.program.version, action='published')
        secured = Client(enforce_csrf_checks=True); secured.force_login(self.user)
        self.assertEqual(secured.post(self.url, {'action': 'published', 'version': self.program.version}).status_code, 403)
        self.client.force_login(self.user)
        self.client.get(self.url, {'action': 'published'})
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'draft')

    def test_other_status_actions_still_require_their_recorded_reason(self):
        with self.assertRaises(ValidationError):
            change_publication(self.program.pk, user=self.user, version=self.program.version, action='archived')
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'draft')

    def test_concurrent_publish_requests_record_one_publication(self):
        gate = Barrier(2)
        def publish():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=self.user.pk)
                gate.wait(timeout=15)
                change_publication(self.program.pk, user=user, version=self.program.version, action='published')
                return 'published'
            except ValidationError:
                return 'stale'
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: publish(), range(2)))
        self.assertCountEqual(results, ['published', 'stale'])
        self.assertEqual(self.program.history.filter(action='published').count(), 1)
        self.assertEqual(self.program.history.filter(action='policy_authorized').count(), 1)


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
                   EWAF_VAULT_ENABLED=True, EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True)
class OneClickSharedPolicyTests(TransactionTestCase):
    draft = composite_tests.CompositeSesWorkflowTests.draft
    approve = composite_tests.CompositeSesWorkflowTests.approve

    def setUp(self):
        composite_tests.CompositeSesWorkflowTests.setUp(self)

    def test_publish_authorizes_and_applies_central_policy_in_one_transaction(self):
        from ewaf.revised import shared_application as shared
        from ewaf.operational_services import latest_configuration
        from programs.test_approved_terms import TermsHelpers
        self.content['program_application'] = {'version': shared.VERSION, 'scope': shared.SCOPE,
            'cutoff_rule': 'application_close', 'cutoff_at': ''}
        policy = self.approve()
        program = save_program(user=self.user, data=program_data(benefit='SYNTHETIC shared policy', ewaf_applicable=True))
        helper = TermsHelpers(); helper.program, helper.officer = program, self.user; helper.reconcile()
        self.assertIsNone(program.policy_authorized_at)
        change_publication(program.pk, user=self.user, version=program.version, action='published')
        program.refresh_from_db()
        configuration = latest_configuration(program)
        self.assertEqual(program.status, 'published')
        self.assertEqual(program.policy_authorized_by, self.user)
        self.assertEqual(configuration.dataset_policy_id, policy.pk)
        self.assertEqual(configuration.assessment_cutoff, program.registration_closes_at)
        self.assertEqual(configuration.validation['weights'], policy.weight_snapshot['weights'])
