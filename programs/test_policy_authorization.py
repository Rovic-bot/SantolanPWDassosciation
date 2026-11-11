from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from membership.tests import grant
from .services import change_publication
from .tests import create_program


class PolicyAuthorizationTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('policy_admin')
        self.program = create_program(eligible_disability_types=[])
        self.program.policy_authorized_at = None
        self.program.save(update_fields=['policy_authorized_at'])
        self.client.force_login(self.admin)
        self.review_url = reverse('programs:manage_detail', args=[self.program.pk])

    def authorize(self, **overrides):
        return change_publication(self.program.pk, user=self.admin, version=self.program.version,
            action='authorize_policy', notes='Authorized association selection/photo policy.', **overrides)

    def test_published_legacy_program_can_be_authorized_without_visibility_change(self):
        original = self.program.published_at
        response = self.client.get(self.review_url)
        self.assertContains(response, 'Authorize program policy')
        self.client.post(self.review_url, {'version':self.program.version, 'action':'authorize_policy',
                         'notes':'Reviewed approved policy.', 'confirm':'on'})
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'published')
        self.assertEqual(self.program.published_at, original)
        self.assertEqual(self.program.policy_authorized_by, self.admin)
        self.assertIsNotNone(self.program.policy_authorized_at)
        self.assertEqual(self.program.version, 1)
        self.assertEqual(self.program.history.get().action, 'policy_authorized')
        self.assertNotContains(self.client.get(self.review_url), '>Authorize program policy</option>')

    def test_missing_policy_and_confirmation_do_not_authorize(self):
        self.client.post(self.review_url, {'version':0,'action':'authorize_policy','notes':'Reviewed.'})
        self.program.refresh_from_db(); self.assertIsNone(self.program.policy_authorized_at)
        for field in ('selection_method', 'photo_instructions'):
            original = getattr(self.program, field)
            setattr(self.program, field, '')
            self.program.save(update_fields=[field])
            with self.assertRaises(ValidationError): self.authorize()
            setattr(self.program, field, original)
            self.program.save(update_fields=[field])

    def test_authorization_requires_permission_current_version_and_single_use(self):
        viewer = get_user_model().objects.create_user('policy_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'programs.view_program')
        with self.assertRaises(PermissionDenied):
            change_publication(self.program.pk, user=viewer, version=0, action='authorize_policy', notes='Reviewed.')
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(self.review_url), 'value="authorize_policy"')
        self.assertEqual(self.client.post(self.review_url, {'version':0,'action':'authorize_policy',
            'notes':'Reviewed.','confirm':'on'}).status_code, 403)
        self.program.version = 1
        self.program.save(update_fields=['version'])
        with self.assertRaises(ValidationError):
            change_publication(self.program.pk, user=self.admin, version=0, action='authorize_policy', notes='Reviewed.')
        self.program = self.authorize()
        with self.assertRaises(ValidationError): self.authorize()

    def test_audit_failure_rolls_back_authorization(self):
        with patch('programs.services.record_log', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError): self.authorize()
        self.program.refresh_from_db()
        self.assertIsNone(self.program.policy_authorized_at)
        self.assertEqual(self.program.version, 0)

    def test_announcement_warning_provides_the_recovery_path(self):
        url = reverse('announcements:prepare_results', args=[self.program.pk])
        response = self.client.get(url)
        self.assertContains(response, self.review_url)
        self.assertContains(response, 'Authorize program policy')
        self.assertContains(response, 'Editing program details alone does not authorize the policy')
