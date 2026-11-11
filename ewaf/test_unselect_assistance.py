"""Undo selections through an audited revision, never by erasing an award."""
from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from assistance.services import record_release, reserved_slots
from assistance.tests import release_data
from membership.tests import grant
from programs.models import ProgramLog
from programs.tests import create_program
from . import operational_services as service, test_automatic_member_inputs as fixtures
from .operational_models import OperationalDecision, OperationalRun


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class UnselectAssistanceTests(TransactionTestCase):
    setUp = fixtures.AutomaticMemberInputsTests.setUp
    draft = fixtures.AutomaticMemberInputsTests.draft
    approve = fixtures.AutomaticMemberInputsTests.approve
    bind = fixtures.AutomaticMemberInputsTests.bind
    publish = fixtures.AutomaticMemberInputsTests.publish
    generate = fixtures.AutomaticMemberInputsTests.generate
    applicant = fixtures.AutomaticMemberInputsTests.applicant
    pool = fixtures.AutomaticMemberInputsTests.pool

    def selected(self):
        a, b = self.pool()
        run = self.generate()
        decision = service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
            application_id=a.pk, expected_revision=0, outcome='SELECTED', reason='Synthetic selected applicant.')
        return a, b, run, decision

    def undo(self, application, run, revision, **overrides):
        return service.unselect_assistance(self.program.pk, user=self.user, run_id=run.pk,
            application_id=application.pk, expected_revision=revision, **overrides)

    def url(self, run):
        return reverse('ewaf:operational_workspace', args=[self.program.pk]) + f'?run={run.pk}'

    def post(self, application, run, revision, **extra):
        return self.client.post(self.url(run), {'action': 'UNSELECT_ASSISTANCE',
            'decision-run_id': run.pk, 'decision-application_id': application.pk,
            'decision-expected_revision': revision, **extra}, follow=True)

    def panel(self, response):
        return response.content.decode().split('id="readiness"', 1)[1].split('</aside>', 1)[0]

    def test_button_replaces_selected_review_and_undo_restores_selection_and_capacity(self):
        a, _, run, selected = self.selected()
        retained, original = deepcopy(run.payload()), deepcopy(selected.payload())
        before = reserved_slots(self.program)
        page = self.client.get(self.url(run), {'review': str(a.pk)})
        self.assertIn('Unselect for assistance', self.panel(page))
        self.assertNotIn('Review selection', self.panel(page))
        self.assertNotIn('name="decision-reason"', self.panel(page))
        # Extra client fields cannot turn this button into another decision.
        response = self.post(a, run, selected.revision, **{'decision-outcome': 'SELECTED'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_input']['application'], str(a.pk))
        self.assertIn('Select for assistance', self.panel(response))
        self.assertNotIn('Unselect for assistance', self.panel(response))
        self.assertNotIn('Review selection', self.panel(response))
        self.assertEqual(response.context['result']['selected_row']['decision_key'], 'awaiting')
        latest = OperationalDecision.objects.filter(application=a).first()
        self.assertEqual((latest.outcome, latest.previous_id), ('DEFERRED', selected.pk))
        self.assertEqual(latest.review['selection_reversed'], selected.pk)
        self.assertEqual(latest.review['selection_action'], 'unselected')
        self.assertEqual(latest.actor_id, self.user.pk)
        latest.clean()
        self.assertEqual(reserved_slots(self.program), before - 1)
        selected.refresh_from_db(); run.refresh_from_db()
        self.assertEqual(selected.payload(), original)
        self.assertEqual(run.payload(), retained)
        reselected = service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
            application_id=a.pk, expected_revision=latest.revision, outcome='SELECTED', reason='Synthetic reselection.')
        self.assertEqual(reselected.previous_id, latest.pk)
        self.assertEqual(reserved_slots(self.program), before)
        self.assertEqual(OperationalRun.objects.filter(program=self.program).count(), 1)

    def test_retries_are_idempotent_and_old_forms_cannot_reverse_a_new_selection(self):
        a, _, run, selected = self.selected()
        undone = self.undo(a, run, selected.revision)
        count = OperationalDecision.objects.count(), ProgramLog.objects.count()
        self.assertEqual(self.undo(a, run, selected.revision).pk, undone.pk)
        self.assertEqual(count, (OperationalDecision.objects.count(), ProgramLog.objects.count()))
        reselected = service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
            application_id=a.pk, expected_revision=undone.revision, outcome='SELECTED', reason='Synthetic reselection.')
        stale = self.post(a, run, selected.revision)
        self.assertTrue(stale.context['result']['selected_row']['unselect_form'].errors)
        self.assertEqual(OperationalDecision.objects.filter(application=a).first().pk, reselected.pk)

    def test_changed_scoring_inputs_do_not_trap_selection_but_reselection_is_revalidated(self):
        a, _, run, selected = self.selected()
        a.member.household_members += 1
        a.member.version += 1
        a.member.save(update_fields=['household_members', 'version'])
        page = self.client.get(self.url(run), {'review': str(a.pk)})
        self.assertFalse(page.context['result']['active'])
        self.assertIn('Unselect for assistance', self.panel(page))
        undone = self.undo(a, run, selected.revision)
        with self.assertRaises(ValidationError):
            service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                application_id=a.pk, expected_revision=undone.revision, outcome='SELECTED', reason='Synthetic stale selection.')
        self.assertEqual(OperationalDecision.objects.filter(application=a).first().pk, undone.pk)

    def test_actual_release_cannot_be_undone_by_selection_button(self):
        a, _, run, selected = self.selected()
        record_release(a.pk, user=self.user, data=release_data(a))
        before = OperationalDecision.objects.count()
        page = self.client.get(self.url(run), {'review': str(a.pk)})
        self.assertNotIn('Unselect for assistance', self.panel(page))
        with self.assertRaisesMessage(ValidationError, 'Actual assistance is already recorded'):
            self.undo(a, run, selected.revision)
        self.assertEqual(OperationalDecision.objects.count(), before)

    def test_permissions_program_scope_and_selected_state_are_enforced(self):
        a, b, run, selected = self.selected()
        with self.assertRaises(ValidationError):
            self.undo(b, run, selected.revision)
        other = create_program(ewaf_applicable=True)
        with self.assertRaises(ValidationError):
            service.unselect_assistance(other.pk, user=self.user, run_id=run.pk,
                application_id=a.pk, expected_revision=selected.revision)
        viewer = get_user_model().objects.create_user('SYNTHETIC-UNSELECT-VIEWER', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *service.VIEW)
        self.client.force_login(viewer)
        self.assertNotContains(self.client.get(self.url(run)), 'Unselect for assistance')
        self.assertEqual(self.post(a, run, selected.revision).status_code, 403)
        self.assertEqual(OperationalDecision.objects.filter(application=a).first().pk, selected.pk)

    def test_failed_audit_rolls_back_unselection(self):
        a, _, run, selected = self.selected()
        before = OperationalDecision.objects.count(), ProgramLog.objects.count()
        with patch('programs.models.ProgramLog.objects.create', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.undo(a, run, selected.revision)
        self.assertEqual(before, (OperationalDecision.objects.count(), ProgramLog.objects.count()))
        self.assertEqual(OperationalDecision.objects.filter(application=a).first().pk, selected.pk)
