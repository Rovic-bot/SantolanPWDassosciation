"""G18-A private, read-only policy guidance and unchanged preparation barriers."""
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from membership.tests import grant
from .configuration_forms import DraftForm
from .configuration_services import VIEW, require_configuration_authorization
from .configuration_testsupport import ConfigurationHelpers
from .evidence_testsupport import EvidenceHelpers
from .policy_reference import REVIEW_ITEMS
from .test_computation_reference import reference_fixture


class PolicyReferenceTests(ConfigurationHelpers, EvidenceHelpers, TestCase):
    def setUp(self):
        self.setup_evidence()
        self.url = reverse('ewaf:policy_review', args=[self.program.pk])
        self.client.force_login(self.officer)

    def all_rows(self):
        return {model._meta.label_lower: list(model.objects.order_by('pk').values()) for model in apps.get_models()}

    def test_get_is_no_store_and_preserves_every_model_without_write_sql(self):
        before = self.all_rows()

        def read_only(execute, sql, params, many, context):
            self.assertTrue(sql.lstrip().upper().startswith('SELECT'), sql[:80])
            return execute(sql, params, many, context)

        with connection.execute_wrapper(read_only):
            response = self.client.get(self.url)
        self.assertContains(response, 'Reference review only')
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(self.all_rows(), before)

    def test_every_unknown_stays_pending_and_no_activation_control_exists(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'Pending Association decision', count=len(REVIEW_ITEMS))
        self.assertEqual({item.key for item in REVIEW_ITEMS}, {
            'authority', 'ahp', 'SI', 'ES', 'PA', 'ND', 'PR', 'evidence',
            'normalization', 'classification', 'ranking', 'workflow',
        })
        for snippet in ('dataset', 'fixed bounds', 'all-equal', 'unrounded', 'no member accounts',
                        'PDAO-ID prerequisite', 'full eligible pool', 'effective date'):
            self.assertContains(response, snippet)
        # The shared shell has a legitimate logout POST outside this review.
        main = response.content.decode().split('<main', 1)[1].split('</main>', 1)[0]
        self.assertNotIn('<form', main)
        self.assertNotContains(response, 'name="score"')
        self.assertNotContains(response, 'name="rank"')

    def test_post_cannot_record_policy_or_activate_anything(self):
        before = self.all_rows()
        self.assertEqual(self.client.post(self.url, {'approved': True, 'operational_ready': True}).status_code, 405)
        self.assertEqual(self.all_rows(), before)

    def test_anonymous_and_dashboard_only_users_cannot_read(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        user = get_user_model().objects.create_user('synthetic_g18_limited', is_staff=True)
        grant(user, 'accounts.access_dashboard')
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_each_existing_configuration_view_permission_is_required(self):
        user = get_user_model().objects.create_user('synthetic_g18_reader', is_staff=True)
        grant(user, 'accounts.access_dashboard', *VIEW)
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        for permission in VIEW:
            with self.subTest(permission=permission):
                user.user_permissions.clear()
                grant(user, 'accounts.access_dashboard', *(p for p in VIEW if p != permission))
                self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_inactive_or_nonstaff_user_cannot_read(self):
        for changes in ({'is_staff': False}, {'is_active': False}):
            user = get_user_model().objects.create_user('synthetic_g18_' + next(iter(changes)), is_superuser=True, **changes)
            self.client.force_login(user)
            self.assertIn(self.client.get(self.url).status_code, (302, 403))

    def test_guidance_discloses_no_member_or_application_values(self):
        response = self.client.get(self.url)
        for value in (str(self.application.pk), self.member.control_number, self.member.full_name):
            self.assertNotContains(response, value)

    def test_draft_and_diagnostics_link_to_review_without_preselected_judgments(self):
        for name, args in [('configuration_detail', [self.program.pk]),
                           ('configuration_action', [self.program.pk, 'draft'])]:
            response = self.client.get(reverse('ewaf:' + name, args=args))
            self.assertContains(response, self.url)
        form = DraftForm()
        comparisons = [field for field in form if field.name.startswith('pair_')]
        self.assertEqual(len(comparisons), 10)
        for field in comparisons:
            self.assertIsNone(field.value())
            self.assertIn('compares criterion importance', field.help_text)
            self.assertIn('Blank remains pending', field.help_text)
        self.assertIn('Socioeconomic Indicator', form.fields['pair_SI_ES'].label)

    def test_reference_validation_review_and_attestation_leave_all_gates_closed(self):
        self.draft(judgments=reference_fixture()['g14_input'])
        self.validate()
        self.review()
        self.authority()
        response = self.client.get(reverse('ewaf:configuration_detail', args=[self.program.pk]))
        result = response.context['result']
        self.assertEqual(result['reference_consistency'], 'PASSED')
        self.assertEqual(result['authority_evidence'], 'RECORDED_NON_EFFECTIVE')
        self.assertFalse(result['effective_authorization'])
        self.assertFalse(result['operational_ready'])
        self.assertContains(self.client.get(self.url), 'Pending Association decision', count=len(REVIEW_ITEMS))
        with self.assertRaises(ValidationError):
            require_configuration_authorization(self.program.pk, user=self.officer)
