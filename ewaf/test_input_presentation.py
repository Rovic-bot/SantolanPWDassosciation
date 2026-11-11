from decimal import Decimal
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from members.tests import create_member
from programs.models import ProgramApplication
from programs.tests import create_program
from .input_presentation import input_details, registered_values
from .presentation import messages_for_officers


class InputPresentationTests(SimpleTestCase):
    def setUp(self):
        self.member = SimpleNamespace(household_monthly_income=Decimal('0.00'),
            registration_profile={'four_ps_member': 'No'}, employment_status='unemployed', household_members=1)
        self.application = SimpleNamespace(pk=uuid4(), member=self.member, member_id=1, status='ELIGIBLE')
        self.configuration = SimpleNamespace(status='LOCKED', policy={}, dataset_policy_id=None, vault_revision_id=None)

    def test_registered_zero_and_no_remain_distinct_from_missing_values(self):
        rows = registered_values(self.member)
        self.assertEqual([row['value'] for row in rows], ['PHP 0.00', 'No', 'Unemployed', 1])
        self.member.household_monthly_income = None
        self.member.household_members = None
        self.member.registration_profile = {}
        self.member.employment_status = ''
        self.assertEqual([row['value'] for row in registered_values(self.member)], ['Not recorded'] * 4)

    def test_registration_display_does_not_accept_inputs_or_supply_scores(self):
        for config in (None, self.configuration):
            row = input_details(self.application, config, None, can_review=True)
            self.assertEqual(row['accepted_values'], [])
            self.assertEqual(len(row['registered_values']), 4)
            self.assertNotIn('score', row)

    def test_draft_and_source_only_rules_do_not_link_to_an_unavailable_review(self):
        self.configuration.status = 'DRAFT'
        row = input_details(self.application, self.configuration, None, can_review=True)
        self.assertEqual(row['input_review_url'], '')
        self.assertIn('configuration pending', row['input_status'])
        self.configuration.status = 'LOCKED'
        self.configuration.policy = {'configuration_scope': 'weights_and_sources'}
        self.assertEqual(input_details(self.application, self.configuration, None, can_review=True)['input_review_url'], '')

    def test_retired_input_review_links_are_absent_for_every_configuration(self):
        for dataset, vault in ((None, None), (None, 1), (1, 1)):
            self.configuration.dataset_policy_id, self.configuration.vault_revision_id = dataset, vault
            self.assertEqual(input_details(self.application, self.configuration, None, can_review=True)['input_review_url'],
                '')
            self.assertEqual(input_details(self.application, self.configuration, None, can_review=False)['input_review_url'], '')
        for status in ('SUBMITTED', 'CLOSED', 'INELIGIBLE'):
            self.application.status = status
            self.assertEqual(input_details(self.application, self.configuration, None, can_review=True)['input_review_url'], '')

    def test_accepted_inputs_keep_reviewed_values_instead_of_current_registration_values(self):
        accepted = {'inputs': {'HM': {'value': '3', 'unit': 'persons'}}}
        row = input_details(self.application, self.configuration, accepted, can_review=True)
        self.assertEqual(row['accepted_values'][0]['value'], '3')
        self.assertEqual(row['registered_values'][-1]['value'], 1)
        self.assertEqual(accepted['inputs']['HM']['value'], '3')

    def test_messages_distinguish_membership_from_scoring_configuration(self):
        messages = messages_for_officers(['MEMBERSHIP_PROVENANCE_REVIEW_REQUIRED', 'CRITERION_MISSING', 'TERMS_CHANGED'])
        self.assertIn('member record', messages[0])
        self.assertIn('member record and scoring configuration', messages[1])
        self.assertIn('program settings', messages[2])

    def composite_configuration(self):
        from .dataset_methods import COMPOSITE
        self.configuration.dataset_policy_id = 1
        self.configuration.policy = {'method': COMPOSITE, 'income_months': 3, 'pa_months': 12, 'pa_scope': 'all_programs'}
        self.configuration.assessment_cutoff = datetime(2026, 11, 15, 9, tzinfo=timezone.utc)
        self.configuration.source = {'terms': {'program': {'registration_closes_at': '2026-11-15T09:00:00+00:00'}}}

    def test_registered_criteria_match_the_scoring_layout_without_fabricating_acceptance(self):
        self.composite_configuration()
        row = input_details(self.application, self.configuration, None, can_review=True,
            source={'pa': {'successful': []}, 'dataset_program_applications': []})
        self.assertEqual([item['code'] for item in row['registered_scoring_values']], ['ES', 'HM', 'PA', 'SES'])
        self.assertEqual([item['value'] for item in row['registered_scoring_values']], ['Unemployed', 1, 0, '0.00'])
        self.assertIn('registered household 4Ps: No', row['registered_scoring_values'][-1]['detail'])
        self.assertEqual(row['accepted_values'], [])
        self.assertNotIn('ready for ranking', row['input_status'])

    def test_registered_pa_obeys_the_bound_period_cutoff_and_program_scope(self):
        self.composite_configuration()
        source = {'dataset_program_applications': ['app-a'], 'pa': {'successful': [
            {'released_on': '2026-11-01', 'recorded_at': '2026-11-01T00:00:00+00:00', 'application_id': 'app-a'},
            {'released_on': '2026-11-02', 'recorded_at': '2026-11-02T00:00:00+00:00', 'application_id': 'app-b'},
            {'released_on': '2025-10-01', 'recorded_at': '2025-10-01T00:00:00+00:00', 'application_id': 'app-a'},
            {'released_on': '2026-11-01', 'recorded_at': '2026-11-16T00:00:00+00:00', 'application_id': 'app-a'},
            {'released_on': '2026-11-16', 'recorded_at': '2026-11-16T00:00:00+00:00', 'application_id': 'app-a'},
        ]}}
        def count():
            return input_details(self.application, self.configuration, None, can_review=True,
                source=source)['registered_scoring_values'][2]['value']
        self.assertEqual(count(), 2)
        self.configuration.policy['pa_scope'] = 'this_program'
        self.assertEqual(count(), 1)

    def test_unavailable_ledger_does_not_default_to_zero(self):
        self.composite_configuration()
        row = input_details(self.application, self.configuration, None, can_review=True)
        self.assertEqual(row['registered_scoring_values'][2]['value'], 'Not recorded')


class RankingRegistrationPageTests(TestCase):
    def setUp(self):
        self.officer = get_user_model().objects.create_superuser('synthetic-ranking-inputs')
        self.member = create_member('SYNTHETIC-RANKING-INPUTS')
        self.member.household_monthly_income = Decimal('7654.32')
        self.member.household_members = 7
        self.member.registration_profile = {'four_ps_member': 'No'}
        self.member.save()
        self.program = create_program(ewaf_applicable=True)
        self.application = ProgramApplication.objects.create(program=self.program, member=self.member,
            public_reference='SYNTHETIC-REGISTRATION-INPUT', status='ELIGIBLE')
        self.url = reverse('ewaf:operational_workspace', args=[self.program.pk])

    def test_private_page_loads_current_member_values_without_writes_or_claiming_acceptance(self):
        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        self.client.force_login(self.officer)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        writes = [row['sql'] for row in queries if row['sql'].lstrip().split()[0].upper() in ('INSERT', 'UPDATE', 'DELETE')]
        self.assertEqual(writes, [])
        from django.utils.html import strip_tags
        text_content = ' '.join(strip_tags(response.content.decode()).split())
        for text in ('PHP 7,654.32', 'Household members:7', '4Ps member:No', 'Scoring configuration pending'):
            self.assertIn(text, text_content)
        for text in ('ewaf-input-card',
                     reverse('members:detail', args=[self.member.pk])):
            self.assertContains(response, text)
        self.assertNotContains(response, 'Complete the input review')
        self.assertNotContains(response, 'Accepted scoring inputs')
        self.assertNotContains(response, 'Review ranking inputs')
        self.assertFalse(response.context['ready'])
        self.assertIn('no-store', response['Cache-Control'])
        self.member.household_members = 8
        self.member.save(update_fields=['household_members'])
        updated_text = strip_tags(self.client.get(self.url).content.decode())
        self.assertIn('Household members:8', updated_text)

    def test_registration_inputs_require_staff_workspace_permissions(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        viewer = get_user_model().objects.create_user('synthetic-ranking-restricted', is_staff=True)
        self.client.force_login(viewer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, '7,654.32', status_code=403)

    def test_readiness_respects_external_approval_setting_without_accepting_member_inputs(self):
        from .readiness import evaluate
        with override_settings(PDAO_ENFORCEMENT_ENABLED=False):
            result = evaluate(self.application)
        codes = {item['code'] for item in result['reasons']['governance']}
        self.assertNotIn('BINDING_INVALID', codes)
        self.assertNotIn('TERMS_CHANGED', codes)
        self.assertFalse(result['operational_ready'])
        self.assertFalse(result['criterion_completeness'])
        self.assertIn('MEMBERSHIP_PROVENANCE_REVIEW_REQUIRED',
            {item['code'] for item in result['reasons']['eligibility']})
        with override_settings(PDAO_ENFORCEMENT_ENABLED=True):
            enforced = evaluate(self.application)
        codes = {item['code'] for item in enforced['reasons']['governance']}
        self.assertIn('BINDING_INVALID', codes)
        self.assertIn('TERMS_CHANGED', codes)
