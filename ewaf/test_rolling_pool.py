"""Owner-authorized local test rules; synthetic data in disposable MySQL only."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from fractions import Fraction
from unittest.mock import patch
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from programs.models import ProgramApplication, ProgramLog
from . import operational_services as service
from .evidence_services import persist, reasoned
from .operational_models import OperationalConfiguration, OperationalRun, OperationalDecision
from .revised import rolling_pool as rolling, live_math, live_services, contracts
from .revised.live_models import DatasetInputReview
from .test_automatic_member_inputs import AutomaticMemberInputsTests as Automatic


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class RollingPoolTests(TransactionTestCase):
    draft = Automatic.draft
    approve = Automatic.approve
    bind = Automatic.bind
    publish = Automatic.publish
    applicant = Automatic.applicant
    generate = Automatic.generate

    def setUp(self):
        # Match the local, externally-unbound programs. The shared fixture also
        # serves external-approval tests, which deliberately protect all dates.
        with patch('programs.test_approved_terms.TermsHelpers.reconcile', return_value=None):
            Automatic.setUp(self)
        self.content['choices']['pool_rule'] = {'value': rolling.RULE, 'specified': True}
        self.content['choices']['constant_rule'] = {'value': rolling.ZERO_CONSTANTS, 'specified': True}
        self.content['choices']['method_rules'] = {'value': rolling.ZERO_METHOD, 'specified': True}
        self.content['registration_inputs']['employment']['student'] = 'Unemployed'
        self.open_at = self.base + timedelta(hours=4)

    def pool(self):
        self.publish()
        a = self.applicant('ROLL-A', low=True, employment_status='student', household_monthly_income=Decimal('100'))
        b = self.applicant('ROLL-B', employment_status='unemployed', household_monthly_income=Decimal('100'))
        return a, b

    def test_open_intake_http_ranking_uses_student_mapping_zero_constants_and_frozen_history(self):
        import json
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b = self.pool()
            before = list(ProgramApplication.objects.filter(program=self.program).values())
            url = reverse('ewaf:operational_workspace', args=[self.program.pk])
            page = self.client.get(url)
            self.assertTrue(page.context['ready'])
            self.assertContains(page, 'Registration is open.')
            self.assertNotContains(page, 'Calculation waits until')
            applications_page = self.client.get(reverse('programs:applications', args=[self.program.pk]))
            self.assertNotContains(applications_page, '<th>Verification</th>', html=True)
            self.assertContains(applications_page, '<th>Eligibility</th>', html=True)
            token = service.context(self.program.pk, user=self.user)
        with patch('django.utils.timezone.now', return_value=self.open_at + timedelta(minutes=5)):
            response = self.client.post(url, {'action': 'GENERATE', 'expected': json.dumps(token), 'request_key': str(uuid4())})
            self.assertEqual(response.status_code, 302)
            run = OperationalRun.objects.get(program=self.program)
            run.clean()
            self.assertTrue(rolling.provisional(run.snapshot))
            self.assertEqual(rolling.observed_at(run.snapshot), self.open_at + timedelta(minutes=5))
            self.assertEqual(run.snapshot['eligible'][str(a.pk)]['inputs']['ES']['value'], 'Unemployed')
            self.assertEqual(Fraction(run.calculations[str(a.pk)]['score_exact']), Fraction(self.configuration.validation['weights']['HM']))
            for result in run.calculations.values():
                for trace in result['traces']:
                    self.assertEqual(trace['weight'], self.configuration.validation['weights'][trace['criterion']])
                    if trace['criterion'] != 'HM':
                        self.assertEqual(trace['normalized']['exact'], '0')
                        self.assertEqual(trace['contribution']['exact'], '0')
                        self.assertEqual(trace['constant_rule'], rolling.ZERO_CONSTANTS)
            self.assertFalse(rolling.selection_waiting(run.snapshot, run.configuration))
            page = self.client.get(url + f'?run={run.pk}&review={a.pk}')
            self.assertTrue(page.context['result']['can_decide'])
            self.assertContains(page, 'Select for assistance')
            self.assertNotContains(page, 'Final beneficiary selection follows')
            retained = deepcopy(run.payload())
            later = self.generate()
            run.refresh_from_db(); run.clean()
            self.assertEqual(run.payload(), retained)
            self.assertEqual(later.previous_id, run.pk)
            self.assertFalse(DatasetInputReview.objects.filter(program=self.program).exists())
            self.assertFalse(OperationalDecision.objects.filter(program=self.program).exists())
            self.assertEqual(list(ProgramApplication.objects.filter(program=self.program).values()), before)
            guide = self.client.get(reverse('ewaf:operational_calculation_guide', args=[self.program.pk]) + f'?run={later.pk}')
            self.assertRedirects(guide, url + f'?run={later.pk}#results')

    def test_select_during_registration_through_http_retains_ranking_and_audited_timing(self):
        from announcements.results import collect_results
        from assistance.models import AssistanceRelease
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b = self.pool()
            run = self.generate()
            retained = deepcopy(run.payload())
            dates = self.program.registration_opens_at, self.program.registration_closes_at
            url = reverse('ewaf:operational_workspace', args=[self.program.pk]) + f'?run={run.pk}'
            data = {'action': 'SELECT_ASSISTANCE', 'decision-run_id': run.pk,
                'decision-application_id': str(a.pk), 'decision-expected_revision': 0}
            selected = self.client.post(url, data)
            self.assertEqual(selected.status_code, 302)
            decision = OperationalDecision.objects.get(program=self.program)
            self.assertEqual(decision.outcome, 'SELECTED')
            self.assertEqual(decision.application_id, a.pk)
            self.assertEqual(decision.review['selection_timing'], {'rule': rolling.SELECTION_RULE,
                'registration_open': True, 'ranking_window': run.snapshot[rolling.KEY]})
            decision.clean()
            self.assertEqual(self.client.post(url, data).status_code, 302)
            self.assertEqual(OperationalDecision.objects.filter(program=self.program).count(), 1)
            page = self.client.get(selected.url)
            self.assertContains(page, 'Unselect for assistance')
            self.assertFalse(page.context['result']['selection_waiting'])
            self.program.refresh_from_db()
            self.assertEqual((self.program.registration_opens_at, self.program.registration_closes_at), dates)
            run.refresh_from_db(); run.clean()
            self.assertEqual(run.payload(), retained)
            self.assertFalse(AssistanceRelease.objects.filter(application__program=self.program).exists())
            with self.assertRaisesMessage(ValidationError, 'Publish results only after'):
                collect_results(self.program)

    def test_open_selection_preserves_capacity_and_excludes_pending_applications(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b = self.pool()
            pending = self.applicant('ROLL-PENDING-SELECTION')
            ProgramApplication.objects.filter(pk=pending.pk).update(status='ELIGIBILITY_REVIEW')
            run = self.generate()
            with self.assertRaisesMessage(ValidationError, 'eligible application'):
                service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                    application_id=pending.pk, expected_revision=0, outcome='SELECTED', reason='SYNTHETIC selection')
            service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                application_id=a.pk, expected_revision=0, outcome='SELECTED', reason='SYNTHETIC selection')
            with self.assertRaisesMessage(ValidationError, 'slots are reserved'):
                service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                    application_id=b.pk, expected_revision=0, outcome='SELECTED', reason='SYNTHETIC selection')
            self.assertEqual(OperationalDecision.objects.filter(program=self.program).count(), 1)

    def test_open_selection_requires_both_permissions_and_a_successful_audit(self):
        from django.contrib.auth import get_user_model
        from membership.tests import grant
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b = self.pool()
            run = self.generate()
            for index, permission in enumerate(('ewaf.decide_operational', 'assistance.decide_assistance')):
                viewer = get_user_model().objects.create_user(f'rolling-selection-{index}', is_staff=True)
                grant(viewer, 'accounts.access_dashboard', *service.VIEW, permission)
                with self.assertRaises(PermissionDenied):
                    service.record_decision(self.program.pk, user=viewer, run_id=run.pk,
                        application_id=a.pk, expected_revision=0, outcome='SELECTED', reason='SYNTHETIC selection')
            before = ProgramLog.objects.count()
            with patch('ewaf.evidence_services.ProgramLog.objects.create', side_effect=ValidationError('SYNTHETIC audit failure')):
                with self.assertRaisesMessage(ValidationError, 'audit failure'):
                    service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                        application_id=a.pk, expected_revision=0, outcome='SELECTED', reason='SYNTHETIC selection')
            self.assertEqual(ProgramLog.objects.count(), before)
            self.assertFalse(OperationalDecision.objects.filter(program=self.program).exists())

    def test_open_selection_rejects_changed_sources_and_preserves_earlier_selection(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b = self.pool()
            run = self.generate()
            decision = service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                application_id=a.pk, expected_revision=0, outcome='SELECTED', reason='SYNTHETIC selection')
            retained = deepcopy(decision.payload())
            self.applicant('ROLL-LATER-APPLICANT', low=True)
            with self.assertRaisesMessage(ValidationError, 'sources changed'):
                service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                    application_id=b.pk, expected_revision=0, outcome='SELECTED', reason='SYNTHETIC stale selection')
            newer = self.generate()
            with self.assertRaisesMessage(ValidationError, 'slots are reserved'):
                service.record_decision(self.program.pk, user=self.user, run_id=newer.pk,
                    application_id=b.pk, expected_revision=0, outcome='SELECTED', reason='SYNTHETIC full selection')
            decision.refresh_from_db(); decision.clean()
            self.assertEqual(decision.payload(), retained)

    def test_open_selection_keeps_exact_boundary_ties_held(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.publish()
            a = self.applicant('ROLL-TIE-A', low=True)
            self.applicant('ROLL-TIE-B', low=True)
            run = self.generate()
            self.assertTrue(run.calculations[str(a.pk)]['comparison']['capacity_boundary_tie'])
            with self.assertRaisesMessage(ValidationError, 'holds exact ties'):
                service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                    application_id=a.pk, expected_revision=0, outcome='SELECTED', reason='SYNTHETIC tied selection')
            self.assertFalse(OperationalDecision.objects.filter(program=self.program).exists())

    def test_pending_applications_do_not_block_open_ranking_but_require_resolution_after_close(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b = self.pool()
            pending = self.applicant('ROLL-PENDING')
            ProgramApplication.objects.filter(pk=pending.pk).update(status='ELIGIBILITY_REVIEW')
            run = self.generate()
            self.assertEqual(set(run.calculations), {str(a.pk), str(b.pk)})
            self.assertEqual(len(run.snapshot['manifest']), 3)
        with patch('django.utils.timezone.now', return_value=self.cutoff + timedelta(hours=1)):
            with self.assertRaisesMessage(ValidationError, 'APPLICATION_REVIEW_UNRESOLVED'):
                service.context(self.program.pk, user=self.user)

    def test_new_applicant_invalidates_token_and_prior_current_ranking_without_rewriting_it(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.pool()
            old = self.generate()
            retained = deepcopy(old.payload())
            token = service.context(self.program.pk, user=self.user)
            self.applicant('ROLL-NEW', low=True)
            with self.assertRaisesMessage(ValidationError, 'sources or predecessor changed'):
                service.generate(self.program.pk, user=self.user, expected=token, request_key=uuid4(), reason='SYNTHETIC stale')
            with service.fence(self.program.pk, self.user) as (actor, program, applications):
                with self.assertRaisesMessage(ValidationError, 'sources changed'):
                    service.current_result_run(program, applications, actor, old.pk)
            new = self.generate()
            self.assertEqual(len(new.calculations), 3)
            old.refresh_from_db(); old.clean()
            self.assertEqual(old.payload(), retained)

    def test_missing_eligible_inputs_still_block_and_no_values_are_imputed(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            a, b = self.pool()
            a.member.household_monthly_income = None
            a.member.save(update_fields=['household_monthly_income'])
            with self.assertRaises(ValidationError):
                self.generate()
            self.assertFalse(OperationalRun.objects.filter(program=self.program).exists())

    def test_open_rank_requires_calculation_permission_and_rolls_back_audit_failure(self):
        from django.contrib.auth import get_user_model
        from membership.tests import grant
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.pool()
            viewer = get_user_model().objects.create_user('rolling-viewer', is_staff=True)
            grant(viewer, 'accounts.access_dashboard', *service.VIEW)
            token = service.context(self.program.pk, user=viewer)
            with self.assertRaises(PermissionDenied):
                service.generate(self.program.pk, user=viewer, expected=token, request_key=uuid4(), reason='SYNTHETIC')
            counts = OperationalRun.objects.count(), ProgramLog.objects.count()
            with patch('ewaf.evidence_services.ProgramLog.objects.create', side_effect=ValidationError('SYNTHETIC audit failure')):
                with self.assertRaisesMessage(ValidationError, 'audit failure'):
                    self.generate()
            self.assertEqual(counts, (OperationalRun.objects.count(), ProgramLog.objects.count()))

    def test_frozen_observation_replay_rejects_future_cutoff_and_reuses_request_key(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.pool()
            token, key = service.context(self.program.pk, user=self.user), uuid4()
            first = service.generate(self.program.pk, user=self.user, expected=token, request_key=key, reason='SYNTHETIC retry')
        with patch('django.utils.timezone.now', return_value=self.open_at + timedelta(minutes=10)):
            retry = service.generate(self.program.pk, user=self.user, expected=token, request_key=key, reason='SYNTHETIC retry')
            self.assertEqual(first.pk, retry.pk)
            changed = deepcopy(first.snapshot)
            changed[rolling.KEY]['cutoff'] = str(self.cutoff)
            with self.assertRaises(ValidationError):
                live_math.calculations(changed, first.configuration)
            changed = deepcopy(first.snapshot)
            changed[rolling.KEY]['assessed_at'] = str(self.cutoff)
            with self.assertRaises(ValidationError):
                live_math.calculations(changed, first.configuration)

    def test_single_person_pool_zero_score_then_final_rank_after_close(self):
        with patch('django.utils.timezone.now', return_value=self.open_at):
            self.publish()
            app = self.applicant('ROLL-ONLY', employment_status='student')
            first = self.generate()
            self.assertEqual(Fraction(first.calculations[str(app.pk)]['score_exact']), 0)
        with patch('django.utils.timezone.now', return_value=self.cutoff - timedelta(minutes=1)):
            with self.assertRaisesMessage(ValidationError, 'final ranking after registration closes'):
                service.record_decision(self.program.pk, user=self.user, run_id=first.pk, application_id=app.pk,
                    expected_revision=0, outcome='SELECTED', reason='SYNTHETIC closed intake needs final ranking')
            early = self.generate()
            self.assertFalse(rolling.provisional(early.snapshot))
            self.assertTrue(rolling.selection_waiting(early.snapshot, early.configuration))
        with patch('django.utils.timezone.now', return_value=self.cutoff + timedelta(minutes=1)):
            final = self.generate()
            self.assertFalse(rolling.provisional(final.snapshot))
            self.assertFalse(rolling.selection_waiting(final.snapshot, final.configuration))
            self.assertEqual(final.previous_id, early.pk)
            final.clean()

    def test_policy_revision_preserves_unscored_binding_weights_and_rejects_changed_math(self):
        original = deepcopy(self.content)
        self.content['choices']['pool_rule']['value'] = 'closed_complete'
        self.content['choices']['constant_rule']['value'] = 'block'
        self.content['choices']['method_rules']['value'] = 'dataset_composite_ses_v1'
        self.content['registration_inputs']['employment'].pop('student')
        self.publish()
        retained = self.configuration.payload()
        self.content = original
        approved = self.approve()
        new = self.bind(approved)
        self.configuration.refresh_from_db()
        self.assertEqual(self.configuration.payload(), retained)
        self.assertEqual(new.previous_id, self.configuration.pk)
        self.assertEqual(new.validation, self.configuration.validation)
        invalid = deepcopy(original)
        invalid['choices']['pa_months']['value'] = 1
        self.assertFalse(rolling.same_revision_rules(self.configuration.dataset_policy.content, invalid))

    def test_philippine_time_binding_and_historical_signed_cutoff_roundtrip(self):
        self.cutoff = self.cutoff.astimezone(ZoneInfo('Asia/Manila'))
        self.publish()
        self.configuration.refresh_from_db(); self.configuration.clean()
        previous = self.configuration
        # Reproduce the historical writer's legitimate signed +08:00 payload.
        legacy = persist(OperationalConfiguration(program=self.program, previous=previous,
            revision=previous.revision + 1, status='LOCKED', dataset_policy=previous.dataset_policy,
            assessment_cutoff=self.cutoff, policy=deepcopy(previous.policy), judgments={},
            validation=deepcopy(previous.validation), source=deepcopy(previous.source),
            **reasoned(self.user, 'SYNTHETIC historical timezone representation', True)))
        retained = legacy.payload()
        legacy.refresh_from_db(); legacy.clean()
        self.assertEqual(legacy.payload(), retained)
        legacy.assessment_cutoff += timedelta(minutes=1)
        with self.assertRaisesMessage(ValidationError, 'digest'):
            legacy.clean()

    def test_audited_date_only_correction_keeps_eligibility_without_a_new_review(self):
        from assistance.models import AssistanceCase
        from programs.schedule_services import update_program_schedule
        from .evidence import source_context
        a, b = self.pool()
        before = list(AssistanceCase.objects.filter(application__program=self.program).values())
        changed = update_program_schedule(self.program.pk, user=self.user, values={
            'version': self.program.version, 'notes': 'SYNTHETIC earlier opening, eligibility terms unchanged',
            'registration_opens_at': (self.program.registration_opens_at - timedelta(hours=1)).astimezone(ZoneInfo('Asia/Manila'))})
        a.program = changed
        context = source_context(a)
        self.assertTrue(context['eligibility_schedule_revision']['witnesses'])
        self.assertEqual(list(AssistanceCase.objects.filter(application__program=self.program).values()), before)
        run = self.generate()
        self.assertEqual(len(run.calculations), 2)
        run.clean()
        # The current ranking already accepts this audited date-only revision;
        # actual receipt must use the same rule without rewriting the old review.
        from assistance.services import record_actual_receipt
        from assistance.models import AssistanceRelease
        retained = deepcopy(run.payload())
        for application in (a,):
            service.record_decision(self.program.pk, user=self.user, run_id=run.pk,
                application_id=application.pk, expected_revision=0, outcome='SELECTED',
                reason='SYNTHETIC selection after an audited date correction.')
        for application in (a,):
            application.refresh_from_db()
            receipt = record_actual_receipt(application.pk, user=self.user, data={
                'version': application.version, 'program_version': changed.version})
            self.assertEqual(receipt.approval_snapshot['eligibility_schedule_revision'],
                             context['eligibility_schedule_revision'])
            self.assertEqual(receipt.approval_snapshot['operational_run_id'], run.pk)
        self.assertEqual(AssistanceRelease.objects.filter(application__program=self.program).count(), 1)
        self.assertEqual(list(AssistanceCase.objects.filter(application__program=self.program).values()), before)
        run.refresh_from_db()
        self.assertEqual(run.payload(), retained)

    def test_unexplained_schedule_log_or_member_change_cannot_reuse_eligibility(self):
        from programs.schedule_services import update_program_schedule
        from .evidence import source_context
        from members.models import Member
        a, b = self.pool()
        changed = update_program_schedule(self.program.pk, user=self.user, values={
            'version': self.program.version, 'notes': 'SYNTHETIC date correction',
            'registration_opens_at': self.program.registration_opens_at - timedelta(hours=1)})
        a.program = changed
        witness = source_context(a)['eligibility_schedule_revision']
        Member.objects.filter(pk=a.member_id).update(version=a.member.version + 1)
        from assistance.services import require_current_review
        a.member.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, 'Review eligibility again'):
            require_current_review(a.assistance_case, changed, a.member, allow_schedule_revision=True)
        with self.assertRaisesMessage(ValidationError, 'ELIGIBILITY_STALE'):
            self.generate()
        Member.objects.filter(pk=a.member_id).update(version=a.member.version - 1)
        a.member.refresh_from_db()
        ProgramLog.objects.filter(pk=witness['witnesses'][0]['log']).update(changes={'slots': {'before': 1, 'after': 2}})
        self.assertNotIn('eligibility_schedule_revision', source_context(a))
        with self.assertRaisesMessage(ValidationError, 'Review eligibility again'):
            require_current_review(a.assistance_case, changed, a.member, allow_schedule_revision=True)
        with self.assertRaisesMessage(ValidationError, 'ELIGIBILITY_STALE'):
            self.generate()
