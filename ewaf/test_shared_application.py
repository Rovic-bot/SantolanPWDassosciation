"""Synthetic central-approval integration; never activate working data."""
from copy import deepcopy
from datetime import timedelta
from fractions import Fraction
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from membership.tests import grant
from programs.models import Program
from programs.services import save_program, change_publication
from programs.tests import program_data
from programs.test_approved_terms import TermsHelpers
from . import operational_services as operational, vault_services as vault
from .operational_models import OperationalConfiguration as Configuration, OperationalRun, OperationalDecision
from .revised import contracts, live_services as service, shared_application as shared
from .revised.live_models import SharedDatasetPolicy as Policy
from . import test_composite_ses as composite_tests
from .dataset_methods import COMPOSITE


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class SharedApplicationTests(TransactionTestCase):
    draft = composite_tests.CompositeSesWorkflowTests.draft
    approve = composite_tests.CompositeSesWorkflowTests.approve
    applicant = composite_tests.CompositeSesWorkflowTests.applicant
    accept = composite_tests.CompositeSesWorkflowTests.accept
    generate = composite_tests.CompositeSesWorkflowTests.generate
    choose = composite_tests.CompositeSesWorkflowTests.choose

    def setUp(self):
        composite_tests.CompositeSesWorkflowTests.setUp(self)
        self.content['program_application'] = {'version': shared.VERSION, 'scope': shared.SCOPE,
            'cutoff_rule': 'application_close', 'cutoff_at': ''}

    def another_program(self, name='SYNTHETIC shared program'):
        with patch('django.utils.timezone.now', return_value=self.base):
            program = save_program(user=self.user, data=program_data(name=name, ewaf_applicable=True,
                benefit='SYNTHETIC benefit', slots=1, selection_method='SYNTHETIC human decision after EWAF',
                registration_opens_at=self.base + timedelta(hours=1), registration_closes_at=self.base + timedelta(days=1)))
            change_publication(program.pk, user=self.user, version=program.version,
                action='authorize_policy', notes='SYNTHETIC program authority')
        program.refresh_from_db()
        helper = TermsHelpers(); helper.program, helper.officer = program, self.user; helper.reconcile()
        return program

    def publish_intake(self, program=None, user=None):
        program = program or self.program
        with patch('django.utils.timezone.now', return_value=self.base):
            change_publication(program.pk, user=user or self.user, version=program.version,
                action='published', notes='SYNTHETIC authorized publication')
        program.refresh_from_db()

    def test_one_shared_approval_binds_all_ready_matching_programs_and_is_idempotent(self):
        second = self.another_program()
        before = {row.pk: row.payload() for row in Configuration.objects.all()}
        policy = self.approve()
        for program in (self.program, second):
            row = operational.latest_configuration(program)
            self.assertEqual(row.dataset_policy_id, policy.pk)
            self.assertEqual(row.assessment_cutoff, program.registration_closes_at)
            self.assertEqual(row.validation['weights'], self.weights.validation['weights'])
            self.assertEqual(row.policy['program_application'], self.content['program_application'])
        self.assertFalse(Configuration.objects.filter(program=self.income_program, dataset_policy=policy).exists())
        for key, payload in before.items():
            self.assertEqual(Configuration.objects.get(pk=key).payload(), payload)
        count = Configuration.objects.count(), LogEntry.objects.count()
        self.assertEqual(shared.apply_all(policy, user=self.user), 0)
        self.assertEqual(count, (Configuration.objects.count(), LogEntry.objects.count()))

    def test_new_program_uses_shared_approval_without_ewaf_permission_or_manual_binding(self):
        self.approve()
        program = self.another_program()
        publisher = get_user_model().objects.create_user('SYNTHETIC-PUBLISHER', is_staff=True)
        grant(publisher, 'accounts.access_dashboard', 'programs.view_program', 'programs.publish_program')
        self.assertFalse(publisher.has_perm('ewaf.authorize_operational'))
        self.publish_intake(program, user=publisher)
        row = operational.latest_configuration(program)
        self.assertEqual(row.policy['method'], COMPOSITE)
        self.assertEqual(row.assessment_cutoff, program.registration_closes_at)
        self.assertEqual(program.status, 'published')

    def test_new_composite_program_reuses_approved_rules_after_main_weights_change(self):
        policy = self.approve()
        retained = deepcopy(policy.payload())
        from .test_synthetic_twelve import proposal
        for state in ('DRAFT', 'LOCKED'):
            new = vault.record_ses_weights(user=self.user, expected=vault.token(), proposal=proposal('hm'),
                reason='SYNTHETIC current main weights; unchanged evidence rules', status=state, method=COMPOSITE)
        count = Policy.objects.count()
        self.program = self.another_program('SYNTHETIC new program after shared weight approval')
        self.publish_intake()
        self.configuration = operational.latest_configuration(self.program)
        self.assertEqual(self.configuration.dataset_policy_id, policy.pk)
        self.assertEqual(Policy.objects.count(), count)
        a, proof_a = self.applicant('SHARED-NEW-A')
        b, proof_b = self.applicant('SHARED-NEW-B', prior=True)
        self.accept(a, proof_a, low=True)
        self.accept(b, proof_b)
        run = self.generate()
        self.assertEqual(run.snapshot['approved_weights']['id'], new.pk)
        self.assertEqual({trace['criterion']: trace['weight'] for trace in run.calculations[str(a.pk)]['traces']},
            new.validation['weights'])
        policy.refresh_from_db()
        self.assertEqual(policy.payload(), retained)

    def test_published_composite_intake_can_receive_shared_rules_with_new_approved_weights(self):
        self.publish_intake()
        a, proof_a = self.applicant('SHARED-OPEN-A')
        b, proof_b = self.applicant('SHARED-OPEN-B', prior=True)
        original = Configuration.objects.filter(program=self.program).first()
        original_payload = deepcopy(original.payload())
        from .test_synthetic_twelve import proposal
        for state in ('DRAFT', 'LOCKED'):
            self.weights = vault.record_ses_weights(user=self.user, expected=vault.token(), proposal=proposal('pa'),
                reason='SYNTHETIC weights for an existing intake', status=state, method=COMPOSITE)
        policy = self.approve()
        self.configuration = operational.latest_configuration(self.program)
        self.assertEqual(self.configuration.dataset_policy_id, policy.pk)
        self.accept(a, proof_a, low=True)
        self.accept(b, proof_b)
        run = self.generate()
        self.assertEqual({trace['criterion']: trace['weight'] for trace in run.calculations[str(a.pk)]['traces']},
            self.weights.validation['weights'])
        original.refresh_from_db()
        self.assertEqual(original.payload(), original_payload)

    def test_intake_then_shared_approval_accepted_inputs_rank_and_human_decision(self):
        self.publish_intake()
        a, proof_a = self.applicant('SHARED-A')
        b, proof_b = self.applicant('SHARED-B', prior=True)
        old = Configuration.objects.filter(program=self.program).first()
        self.assertFalse(old.dataset_policy_id)
        self.approve()
        self.configuration = operational.latest_configuration(self.program)
        self.accept(a, proof_a, low=True)
        self.accept(b, proof_b)
        run = self.generate()
        trace = next(t for t in run.calculations[str(a.pk)]['traces'] if t['criterion'] == 'SES')
        self.assertEqual(Fraction(trace['normalized']['exact']), Fraction(9, 10))
        self.assertEqual(Fraction(trace['contribution']['exact']),
            Fraction(self.configuration.validation['weights']['SES']) * Fraction(9, 10))
        self.assertEqual(len(run.calculations[str(a.pk)]['traces']), 4)
        self.assertFalse(OperationalDecision.objects.exists())
        self.choose(run, a)
        self.assertEqual(OperationalDecision.objects.count(), 1)
        self.assertEqual(Configuration.objects.get(pk=old.pk).vault_revision_id, self.weights.pk)

    def test_new_weight_approval_updates_unstarted_matching_drafts_only(self):
        old = Configuration.objects.filter(program=self.program).first()
        old_payload = old.payload()
        self.publish_intake(self.income_program)
        opened = Configuration.objects.filter(program=self.income_program).first()
        for state in ('DRAFT', 'LOCKED'):
            new = vault.record_ses_weights(user=self.user, expected=vault.token(), proposal=composite_tests.proposal(),
                reason='SYNTHETIC next shared weights', status=state, method=COMPOSITE)
        latest = Configuration.objects.filter(program=self.program).first()
        self.assertEqual(latest.vault_revision_id, new.pk)
        self.assertEqual(latest.previous_id, old.pk)
        self.assertEqual(Configuration.objects.get(pk=old.pk).payload(), old_payload)
        self.assertEqual(Configuration.objects.filter(program=self.income_program).first().pk, opened.pk)

    def test_shared_approval_does_not_replace_bound_policy_or_prior_run(self):
        first = self.approve()
        self.configuration = operational.latest_configuration(self.program)
        retained = self.configuration.payload()
        second = self.approve()
        self.assertNotEqual(first.pk, second.pk)
        self.assertEqual(operational.latest_configuration(self.program).payload(), retained)
        self.assertEqual(shared.apply_all(first, user=self.user), 0)

    def test_missing_global_cutoff_and_unapproved_policy_cannot_bind(self):
        for invalid in (None, {}, {'scope': 'one_program'}, {'version': shared.VERSION}):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                self.draft(self.content | {'program_application': invalid})
        self.content['program_application']['cutoff_rule'] = ''
        draft = self.draft()
        with self.assertRaisesMessage(ValidationError, 'shared assessment cutoff'):
            self.approve(draft)
        self.assertIsNone(shared.apply(self.program, user=self.user))
        self.assertFalse(Configuration.objects.filter(program=self.program, dataset_policy__isnull=False).exists())

    def test_disabled_workflows_and_unavailable_schema_do_not_apply_or_write(self):
        self.approve()
        for flag in ('EWAF_VAULT_ENABLED', 'EWAF_DATASET_POLICY_ENABLED'):
            with self.subTest(flag=flag), override_settings(**{flag: False}):
                before = Configuration.objects.count(), LogEntry.objects.count()
                self.assertIsNone(shared.apply(self.program, user=self.user))
                self.assertEqual(before, (Configuration.objects.count(), LogEntry.objects.count()))
        with patch.object(service, 'schema_available', return_value=False):
            before = Configuration.objects.count(), LogEntry.objects.count()
            self.assertIsNone(shared.apply(self.program, user=self.user))
            self.assertEqual(before, (Configuration.objects.count(), LogEntry.objects.count()))

    def test_explicit_fixed_cutoff_is_used_without_changing_program_dates(self):
        self.content['program_application'].update(cutoff_rule='fixed', cutoff_at=self.cutoff.isoformat())
        close = self.program.registration_closes_at
        self.approve()
        self.assertEqual(operational.latest_configuration(self.program).assessment_cutoff, self.cutoff)
        self.program.refresh_from_db()
        self.assertEqual(self.program.registration_closes_at, close)

    def test_invalid_cutoff_preserves_intake_and_reports_blocker(self):
        self.content['program_application'].update(cutoff_rule='fixed', cutoff_at=self.base.isoformat())
        self.approve()
        row = Configuration.objects.filter(program=self.program).first()
        self.assertFalse(row.dataset_policy_id)
        self.assertIn('approved application close', ' '.join(shared.status(self.program, row)['problems']))
        self.publish_intake()
        self.assertEqual(self.program.status, 'published')
        self.assertFalse(Configuration.objects.filter(program=self.program).first().dataset_policy_id)

    def test_future_policy_waits_then_applies_centrally_without_get_writes(self):
        start = timezone.now() + timedelta(days=1)
        self.content['choices']['effective_from']['value'] = start.isoformat()
        policy = self.approve()
        self.assertFalse(Configuration.objects.filter(program=self.program).first().dataset_policy_id)
        before = Configuration.objects.count(), LogEntry.objects.count()
        page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
        self.assertNotContains(page, 'Shared configuration')
        self.assertFalse(page.context['ready'])
        self.assertNotContains(page, 'Assign approved calculation rules')
        self.assertEqual(before, (Configuration.objects.count(), LogEntry.objects.count()))
        with patch('django.utils.timezone.now', return_value=start + timedelta(seconds=1)):
            self.assertEqual(shared.apply_all(policy, user=self.user), 1)

    def test_approval_and_partial_application_roll_back_on_binding_audit_failure(self):
        self.another_program()
        draft = self.draft()
        before = Policy.objects.count(), Configuration.objects.count(), LogEntry.objects.count()
        original, calls = service.persist, []
        def fail_second(row):
            calls.append(row)
            if len(calls) == 2:
                raise ValidationError('SYNTHETIC binding audit failure')
            return original(row)
        with patch.object(service, 'persist', side_effect=fail_second):
            with self.assertRaisesMessage(ValidationError, 'binding audit failure'):
                self.approve(draft)
        self.assertEqual(len(calls), 2)
        self.assertEqual(before, (Policy.objects.count(), Configuration.objects.count(), LogEntry.objects.count()))

    def test_global_approval_requires_authority_and_stale_requests_do_not_write(self):
        reviewer = get_user_model().objects.create_user('SYNTHETIC-REVIEWER', is_staff=True)
        grant(reviewer, 'accounts.access_dashboard', *operational.VIEW, 'ewaf.authorize_operational')
        draft = self.draft()
        with self.assertRaises(PermissionDenied):
            service.approve(draft.pk, user=reviewer, expected=draft.digest, reviewed_groups=['A', 'B', 'C'], reason='SYNTHETIC')
        policy = self.approve(draft)
        before = Configuration.objects.count(), LogEntry.objects.count()
        with self.assertRaises(ValidationError):
            self.approve(draft)
        page = self.client.post(reverse('ewaf:dataset_policy_review', args=[policy.pk]),
            {'action': 'APPLY_SHARED', 'expected': 'stale'})
        self.assertContains(page, 'Reload the approved shared policy')
        self.assertEqual(before, (Configuration.objects.count(), LogEntry.objects.count()))

    def test_policy_editor_and_review_show_global_rule_and_preserve_old_policy_contract(self):
        page = self.client.get(reverse('ewaf:dataset_policies'))
        self.assertContains(page, 'Shared assessment cutoff rule')
        policy = self.approve()
        page = self.client.get(reverse('ewaf:dataset_policy_review', args=[policy.pk]))
        self.assertContains(page, 'Shared application to programs')
        self.assertContains(page, 'Apply shared configuration to ready programs')
        old = deepcopy(self.content); old.pop('program_application')
        draft = self.draft(old)
        retained = self.approve(draft)
        self.assertNotIn('program_application', retained.content)
        self.assertEqual(shared.apply_all(retained, user=self.user), 0)
