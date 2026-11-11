"""Persistent applicant inputs preserve explicit, permission-checked selection."""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from assistance.services import review_eligibility
from assistance.tests import review_data
from membership.tests import grant
from . import operational_services, test_automatic_member_inputs as fixtures
from .operational_models import OperationalDecision, OperationalRun


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class ApplicantPanelTests(TransactionTestCase):
    setUp = fixtures.AutomaticMemberInputsTests.setUp
    draft = fixtures.AutomaticMemberInputsTests.draft
    approve = fixtures.AutomaticMemberInputsTests.approve
    bind = fixtures.AutomaticMemberInputsTests.bind
    publish = fixtures.AutomaticMemberInputsTests.publish
    generate = fixtures.AutomaticMemberInputsTests.generate
    applicant = fixtures.AutomaticMemberInputsTests.applicant
    pool = fixtures.AutomaticMemberInputsTests.pool

    def workspace(self, **query):
        return self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]), query)

    def visible_panel(self, response):
        return response.content.decode().split('id="readiness"', 1)[1].split('</aside>', 1)[0]

    def test_first_row_and_explicit_row_show_matching_inputs_without_popup_or_writes(self):
        a, b = self.pool()
        run = self.generate()
        retained = deepcopy(run.payload())
        first = self.workspace()
        self.assertEqual(first.context['selected_input']['application'], first.context['result']['rows'][0]['application'])
        second = self.workspace(review=str(b.pk))
        self.assertEqual(second.context['selected_input']['application'], str(b.pk))
        self.assertEqual(second.context['result']['selected_row']['application'], str(b.pk))
        self.assertContains(second, 'name="decision-application_id" value="' + str(b.pk) + '"')
        self.assertContains(second, 'Select for assistance')
        self.assertNotContains(second, '<dialog')
        self.assertNotContains(second, 'ewaf-review-link')
        self.assertNotContains(second, 'ewaf-input-grid')
        self.assertNotContains(second, 'ewaf-applicant-picker-form')
        self.assertNotContains(second, 'id="applicant-picker"')
        self.assertFalse(any(item['needs_review'] for item in second.context['inventory']))
        self.assertEqual(second.context['workspace_notice'], '')
        self.assertEqual(self.visible_panel(second).count('class="ewaf-input-card"'), 1)
        self.assertEqual({item['application'] for item in second.context['applicant_panels']}, {str(a.pk), str(b.pk)})
        for item in second.context['applicant_panels']:
            self.assertEqual(item['input']['application'], item['row']['application'])
            self.assertEqual(str(item['row']['select_form'].initial['application_id']), item['application'])
        self.assertFalse(OperationalDecision.objects.exists())
        run.refresh_from_db()
        self.assertEqual(run.payload(), retained)

    def test_selection_post_keeps_applicant_errors_and_success_in_panel(self):
        a, _ = self.pool()
        run = self.generate()
        url = reverse('ewaf:operational_workspace', args=[self.program.pk])
        data = {'action': 'SELECT_ASSISTANCE', 'decision-run_id': run.pk,
            'decision-application_id': str(a.pk), 'decision-expected_revision': 999}
        bad = self.client.post(url, data)
        self.assertEqual(bad.status_code, 200)
        self.assertEqual(bad.context['selected_input']['application'], str(a.pk))
        self.assertTrue(bad.context['result']['selected_row']['select_form'].errors)
        self.assertFalse(OperationalDecision.objects.exists())
        good = self.client.post(url, data | {'decision-expected_revision': 0}, follow=True)
        self.assertEqual(good.status_code, 200)
        self.assertEqual(good.context['selected_input']['application'], str(a.pk))
        self.assertContains(good, 'Selected for assistance')
        self.assertEqual(OperationalDecision.objects.get(application=a).run_id, run.pk)
        self.assertEqual(OperationalRun.objects.filter(program=self.program).count(), 1)

    def test_new_ranking_shows_eligible_applicants_awaiting_selection_and_retains_prior_decisions(self):
        a, b = self.pool()
        old_run = self.generate()
        for application, outcome in ((a, 'SELECTED'), (b, 'NOT_SELECTED')):
            operational_services.record_decision(self.program.pk, user=self.user,
                run_id=old_run.pk, application_id=application.pk, expected_revision=0,
                outcome=outcome, reason='Synthetic decision for the previous ranking.')
        current_run = self.generate()
        decisions = list(OperationalDecision.objects.order_by('pk').values())
        runs = list(OperationalRun.objects.order_by('pk').values())
        page = self.workspace(run=current_run.pk, review=str(b.pk), decision='awaiting')
        self.assertEqual(page.context['result']['rows'].paginator.count, 2)
        for row in page.context['result']['rows']:
            self.assertEqual(row['decision_key'], 'awaiting')
            self.assertEqual(row['decision_label'], 'Eligible \u00b7 Awaiting selection')
            self.assertTrue(row['has_previous_decision'])
            self.assertEqual(row['select_form'].initial['expected_revision'], 1)
        panel = self.visible_panel(page)
        self.assertIn('Previous selection decision', panel)
        self.assertIn('Not selected &middot; Ranking 1', panel)
        self.assertNotContains(page, 'Previous ranking decisions')
        self.assertEqual(self.workspace(run=current_run.pk, decision='not_selected').context['result']['rows'].paginator.count, 0)
        self.assertEqual(self.workspace(run=current_run.pk, decision='selected').context['result']['rows'].paginator.count, 0)
        self.assertEqual(list(OperationalDecision.objects.order_by('pk').values()), decisions)
        self.assertEqual(list(OperationalRun.objects.order_by('pk').values()), runs)
        # A real decision for this ranking replaces the pending label.
        operational_services.record_decision(self.program.pk, user=self.user,
            run_id=current_run.pk, application_id=b.pk, expected_revision=1,
            outcome='NOT_SELECTED', reason='Synthetic current ranking decision.')
        latest = self.workspace(run=current_run.pk, review=str(b.pk))
        self.assertEqual(latest.context['result']['selected_row']['decision_label'], 'Not selected')
        self.assertFalse(latest.context['result']['selected_row']['has_previous_decision'])

    def test_filters_empty_state_and_excluded_applicant_do_not_show_another_selection(self):
        a, b = self.pool()
        self.generate()
        empty = self.workspace(q='NO-MATCH-SYNTHETIC')
        self.assertIsNone(empty.context['selected_input'])
        self.assertNotContains(empty, 'name="action" value="SELECT_ASSISTANCE"')
        review_eligibility(b.pk, user=self.user, data=review_data(b, eligibility='ineligible',
            other_requirements='fail', notes='SYNTHETIC failed mandatory program requirement.'))
        excluded = self.workspace(review=str(b.pk))
        self.assertEqual(excluded.context['selected_input']['input_state'], 'excluded')
        self.assertEqual(excluded.context['result']['selected_row']['decision_label'], 'Awaiting selection')
        self.assertContains(excluded, 'Pool excluded')
        self.assertNotIn('name="action" value="SELECT_ASSISTANCE"', self.visible_panel(excluded))
        self.assertEqual(self.workspace(review='not-this-program').status_code, 404)

    def test_unranked_inputs_remain_available_and_selection_permission_is_enforced(self):
        a, b = self.pool()
        unranked = self.workspace(review=str(b.pk))
        self.assertEqual(unranked.context['selected_input']['application'], str(b.pk))
        self.assertEqual({item['application'] for item in unranked.context['unranked_applicants']}, {str(a.pk), str(b.pk)})
        self.assertContains(unranked, 'data-applicant="' + str(b.pk) + '" class="is-selected"')
        self.assertContains(unranked, 'data-applicant-open')
        self.assertNotContains(self.workspace(), 'name="action" value="SELECT_ASSISTANCE"')
        self.generate()
        viewer = get_user_model().objects.create_user('SYNTHETIC-PANEL-VIEWER', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *operational_services.VIEW)
        self.client.force_login(viewer)
        page = self.workspace(review=str(a.pk))
        self.assertContains(page, 'Selection permission required.')
        self.assertNotContains(page, 'name="action" value="SELECT_ASSISTANCE"')

    def test_changed_applicant_has_review_marker_and_short_explanation_without_altering_ranking(self):
        a, b = self.pool()
        run = self.generate()
        retained = deepcopy(run.payload())
        a.member.household_monthly_income = Decimal('12500')
        a.member.version += 1
        a.member.save(update_fields=['household_monthly_income', 'version'])
        page = self.workspace(review=str(a.pk))
        items = {item['application']: item for item in page.context['inventory']}
        rows = {item['application']: item for item in page.context['result']['rows']}
        self.assertTrue(items[str(a.pk)]['needs_review'])
        self.assertTrue(rows[str(a.pk)]['needs_review'])
        self.assertFalse(items[str(b.pk)]['needs_review'])
        self.assertFalse(rows[str(b.pk)]['needs_review'])
        self.assertEqual(page.context['workspace_notice'], '1 applicant needs review; select a marked row to see why.')
        self.assertContains(page, 'Check updated information and identity evidence.')
        self.assertContains(page, 'class="ewaf-needs-review"', count=1)
        for text in ('Review the flagged applicants before ranking.',
                     'These scores retain their original weights and inputs.',
                     'The member or program record changed after eligibility was reviewed.',
                     'Generate a current ranking before making a selection.'):
            self.assertNotContains(page, text)
        self.assertFalse(page.context['result']['active'])
        self.assertFalse(OperationalDecision.objects.exists())
        run.refresh_from_db()
        self.assertEqual(run.payload(), retained)

    def test_new_applicant_outside_saved_ranking_is_selectable_from_left(self):
        self.pool()
        self.generate()
        new = self.applicant('AUTO-NEW', low=True)
        page = self.workspace(review=str(new.pk))
        self.assertEqual(page.context['selected_input']['application'], str(new.pk))
        self.assertIsNone(page.context['result']['selected_row'])
        self.assertEqual([item['application'] for item in page.context['unranked_applicants']], [str(new.pk)])
        self.assertContains(page, 'data-applicant="' + str(new.pk) + '" class="is-selected"')
        self.assertNotIn('name="action" value="SELECT_ASSISTANCE"', self.visible_panel(page))
        self.assertEqual(len(self.workspace(q='NO-MATCH').context['unranked_applicants']), 0)

    def test_read_reuses_one_pool_inspection_but_post_and_next_read_check_changes(self):
        from .revised import live_evidence
        a, b = self.pool()
        run = self.generate()
        with patch.object(live_evidence, 'inventory', wraps=live_evidence.inventory) as inspection:
            first = self.workspace(review=str(a.pk))
            self.assertTrue(first.context['result']['active'])
            self.assertEqual(inspection.call_count, 1)
        a.member.household_monthly_income = Decimal('12500')
        a.member.version += 1
        a.member.save(update_fields=['household_monthly_income', 'version'])
        url = reverse('ewaf:operational_workspace', args=[self.program.pk])
        with patch.object(live_evidence, 'inventory', wraps=live_evidence.inventory) as inspection:
            post = self.client.post(url, {'action': 'SELECT_ASSISTANCE', 'decision-run_id': run.pk,
                'decision-application_id': str(a.pk), 'decision-expected_revision': 0})
            self.assertGreater(inspection.call_count, 1)
        self.assertFalse(OperationalDecision.objects.exists())
        self.assertTrue(post.context['result']['selected_row']['select_form'].errors)
        with patch.object(live_evidence, 'inventory', wraps=live_evidence.inventory) as inspection:
            fresh = self.workspace(review=str(a.pk))
            self.assertEqual(inspection.call_count, 1)
        self.assertTrue(fresh.context['selected_input']['needs_review'])
        self.assertFalse(fresh.context['result']['active'])
        filtered = self.workspace(q=b.public_reference)
        self.assertEqual([item['application'] for item in filtered.context['applicant_panels']], [str(b.pk)])
