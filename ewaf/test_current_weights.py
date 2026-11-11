"""Current shared approval -> existing programs -> frozen, replayable rankings."""
from copy import deepcopy
from datetime import timedelta
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.urls import reverse

from membership.tests import grant
from . import test_synthetic_twelve as fixture
from . import operational_services as operational, vault_services as vault, dataset_methods as methods
from .operational_models import OperationalConfiguration, OperationalRun
from .revised.live_models import DatasetInputReview
from .revised import live_math
from .vault_models import VaultRevision


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True,
    PDAO_ENFORCEMENT_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CurrentWeightTests(StaticLiveServerTestCase):
    # Reuse the actual twelve-member registration/review/release workflow, not
    # the superclass's separate scenario tests or its expected fixed bindings.
    setUp = fixture.SyntheticTwelveIntegrationTests.setUp
    observe = fixture.SyntheticTwelveIntegrationTests.observe
    handoff_form = fixture.SyntheticTwelveIntegrationTests.handoff_form
    register_members = fixture.SyntheticTwelveIntegrationTests.register_members
    program = fixture.SyntheticTwelveIntegrationTests.program
    publish = fixture.SyntheticTwelveIntegrationTests.publish
    apply = fixture.SyntheticTwelveIntegrationTests.apply
    history = fixture.SyntheticTwelveIntegrationTests.history
    save_weights = fixture.SyntheticTwelveIntegrationTests.save_weights
    bind = fixture.SyntheticTwelveIntegrationTests.bind
    findings = fixture.SyntheticTwelveIntegrationTests.findings
    accept = fixture.SyntheticTwelveIntegrationTests.accept
    generate = fixture.SyntheticTwelveIntegrationTests.generate
    build = fixture.SyntheticTwelveIntegrationTests.build

    def preview(self, scenario):
        data = {'calculation_method': methods.COMPOSITE, 'weight_method': 'slider-ratio-projection-v1',
            'expected': vault.token(), 'slider_proposal': json.dumps(fixture.proposal(scenario)),
            'reason': 'SYNTHETIC current shared weights ' + scenario}
        result = self.client.post(reverse('ewaf:vault'), data | {'action': 'PREVIEW_WEIGHTS'})
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()['storage_errors'])
        return data | {'weight_review': result.json()['token']}

    def approve(self, scenario):
        data = self.preview(scenario)
        result = self.client.post(reverse('ewaf:vault'), data | {'action': 'LOCKED'})
        self.assertEqual(result.status_code, 302, getattr(result, 'context', None))
        return vault.active(methods.COMPOSITE)

    def assert_scores(self, run, scenario, applications):
        run.clean()
        weights = dict(zip(fixture.CODES, (Fraction(value, 10000) for value in fixture.SCENARIOS[scenario])))
        expected = fixture.oracle(weights)
        for label, app in applications.items():
            actual = run.calculations[str(app.pk)]
            self.assertEqual(Fraction(actual['score_exact']) * 100, expected[label]['score'])
            self.assertEqual(actual['comparison']['business_rank'], expected[label]['rank'])
            self.assertEqual({trace['criterion']: Fraction(trace['weight']) for trace in actual['traces']}, weights)

    def test_all_five_current_approvals_apply_to_two_existing_programs_and_preserve_history(self):
        self.build('balanced')
        first, first_apps = self.target, self.apps
        first_run = self.generate()
        original_payload = deepcopy(first_run.payload())
        with patch('django.utils.timezone.now', return_value=fixture.BASE):
            self.target = self.program('SYNTHETIC second existing program', ewaf=True,
                opens=fixture.BASE + timedelta(hours=1), closes=fixture.BASE + timedelta(days=1))
            self.bind()
            self.publish(self.target)
        self.apps = {}
        with patch('django.utils.timezone.now', return_value=fixture.BASE + timedelta(hours=2)):
            for label, member in self.members.items():
                self.apps[label] = self.apply(self.target, member)
        for label in self.members:
            self.accept(label)
        second, second_apps = self.target, self.apps
        self.generate()
        frozen = {
            'configurations': list(OperationalConfiguration.objects.order_by('pk').values()),
            'reviews': list(DatasetInputReview.objects.order_by('pk').values()),
        }
        for scenario in fixture.SCENARIOS:
            old_context = operational.context(first.pk, user=self.user)
            approved = self.approve(scenario)
            with self.assertRaisesMessage(ValidationError, 'sources or predecessor changed'):
                operational.generate(first.pk, user=self.user, expected=old_context,
                    reason='SYNTHETIC stale browser must reload', request_key=uuid4())
            for program, applications in ((first, first_apps), (second, second_apps)):
                self.target = program
                run = self.generate()
                self.assertEqual(run.snapshot['approved_weights']['id'], approved.pk)
                self.assert_scores(run, scenario, applications)
                page = self.client.get(reverse('ewaf:operational_workspace', args=[program.pk]))
                self.assertEqual(page.context['shared_weights']['id'], approved.pk)
                self.assertNotContains(page, 'Shared configuration')
                self.assertContains(page, f'applicant={applications["T01"].pk}')
                from .program_cards import configuration_summary
                cards = configuration_summary(program)
                self.assertEqual({row['code']: row['percent'] for row in cards['rows']},
                    {code: f'{value / 100:.2f}' for code, value in fixture.proposal(scenario)['weights'].items()})
            first_run.refresh_from_db()
            self.assertEqual(first_run.payload(), original_payload)
            self.assert_scores(first_run, 'balanced', first_apps)
            self.assertEqual(frozen['configurations'], list(OperationalConfiguration.objects.order_by('pk').values()))
            self.assertEqual(frozen['reviews'], list(DatasetInputReview.objects.order_by('pk').values()))
        # A saved draft is not an approval and cannot change the next calculation.
        self.target = first
        context = operational.context(first.pk, user=self.user)
        vault.record_ses_weights(user=self.user, expected=vault.token(), proposal=fixture.proposal('balanced'),
            reason='SYNTHETIC draft only', status='DRAFT', method=methods.COMPOSITE)
        self.assertEqual(context, operational.context(first.pk, user=self.user))
        self.assert_scores(self.generate(), 'hm', first_apps)
        self.approve('balanced')
        browser = subprocess.run(['node', str(Path(settings.BASE_DIR) / 'scripts/ewaf_current_weights_browser.cjs')],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(self.output),
                'QA_PROGRAMS': json.dumps([str(first.pk), str(second.pk)]),
                'QA_USERNAME': self.user.username, 'QA_PASSWORD': 'synthetic-only'},
            capture_output=True, text=True, encoding='utf-8', timeout=180)
        self.assertEqual(browser.returncode, 0, browser.stdout + browser.stderr)
        print(browser.stdout)
        for program, applications in ((first, first_apps), (second, second_apps)):
            self.assert_scores(OperationalRun.objects.filter(program=program).first(), 'ses', applications)

    def test_applicant_information_uses_member_profile_current_inputs_and_ledger(self):
        from programs.applicant_information import money
        from members.profile import profile_sections
        from .revised import live_evidence
        self.build('balanced')
        for label, application in self.apps.items():
            response = self.client.get(reverse('programs:application_detail', args=[self.target.pk, application.pk]))
            review = DatasetInputReview.objects.filter(application=application).first()
            values = {row['label']: row['value'] for row in response.context['household_information']}
            self.assertEqual(values['Monthly household income'], money(review.inputs['SES']['value']))
            self.assertEqual(values['Number of household members'], review.inputs['HM']['value'])
            self.assertEqual(values['Employment status'], review.inputs['ES']['value'])
            self.assertEqual(values['Previous assistance received'], review.inputs['PA']['value'])
            self.assertEqual(values['Household 4Ps participation'], 'Verified Yes' if review.inputs['SES']['household_four_ps'] else 'Verified No')
            self.assertEqual(response.context['profile_sections'], [section for section in profile_sections(application.member)
                if section[0] != 'Information for assessment (digital only)'])
            self.assertNotContains(response, 'Scoring evidence')
        iris = self.apps['T09']
        configuration = operational.latest_configuration(self.target)
        live_evidence.record(iris.pk, user=self.user, expected=live_evidence.review_token(iris, configuration),
            findings={}, selections={}, state='NEEDS_REVIEW', reason='SYNTHETIC unresolved household information', confirmed=True)
        url = reverse('programs:application_detail', args=[self.target.pk, iris.pk])
        response = self.client.get(url)
        values = {row['label']: row['value'] for row in response.context['household_information']}
        self.assertEqual(values['Monthly household income'], 'PHP 37,000.00')
        self.assertEqual(values['Previous assistance received'], 'History review pending')
        self.assertNotIn('Verified', values['Household 4Ps participation'])
        restricted = get_user_model().objects.create_user('synthetic_applicant_viewer', is_staff=True)
        grant(restricted, 'accounts.access_dashboard', 'programs.view_program', 'programs.view_programapplication')
        self.client.force_login(restricted)
        response = self.client.get(url)
        self.assertNotIn('household_information', response.context)
        self.assertNotContains(response, '37,000.00')
        self.assertNotContains(response, 'Verified No')

    def test_rounding_proposal_can_be_approved_repeatedly_without_manual_draft(self):
        from .test_current_ahp import ROUNDING_PROPOSAL
        from .weight_input import CURRENT_METHOD
        self.build('balanced')
        initial_run = self.generate()
        frozen = deepcopy(initial_run.payload())
        vault.record_ses_weights(user=self.user, expected=vault.token(), proposal=ROUNDING_PROPOSAL,
            reason='SYNTHETIC reproduction of the rejected precision draft', status='DRAFT', method=methods.COMPOSITE)
        url = reverse('ewaf:vault')
        self.assertNotContains(self.client.get(url), 'Save weight draft')
        for proposal in (ROUNDING_PROPOSAL, fixture.proposal('ses'), ROUNDING_PROPOSAL):
            data = {'calculation_method': methods.COMPOSITE, 'weight_method': 'slider-ratio-projection-v1',
                'expected': vault.token(), 'slider_proposal': json.dumps(proposal), 'reason': 'SYNTHETIC repeat approval'}
            preview = self.client.post(url, data | {'action': 'PREVIEW_WEIGHTS'})
            self.assertEqual(preview.status_code, 200)
            self.assertEqual(preview.json()['storage_errors'], [])
            result = self.client.post(url, data | {'action': 'LOCKED', 'weight_review': preview.json()['token']})
            self.assertEqual(result.status_code, 302)
            approved = vault.active(methods.COMPOSITE)
            self.assertEqual(approved.policy['weight_input']['method'], CURRENT_METHOD)
            run = self.generate()
            expected = fixture.oracle({code: Fraction(value) for code, value in approved.validation['weights'].items()})
            self.assertEqual(run.snapshot['approved_weights']['id'], approved.pk)
            for label, application in self.apps.items():
                self.assertEqual(Fraction(run.calculations[str(application.pk)]['score_exact']) * 100, expected[label]['score'])
                self.assertEqual(run.calculations[str(application.pk)]['comparison']['business_rank'], expected[label]['rank'])
            initial_run.refresh_from_db()
            self.assertEqual(initial_run.payload(), frozen)
            initial_run.clean()
        browser = subprocess.run(['node', str(Path(settings.BASE_DIR) / 'scripts/applicant_vault_browser.cjs')],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.target.pk),
                'QA_APPLICANT': str(self.apps['T09'].pk), 'QA_USERNAME': self.user.username,
                'QA_PASSWORD': 'synthetic-only'}, capture_output=True, text=True, encoding='utf-8', timeout=180)
        self.assertEqual(browser.returncode, 0, browser.stdout + browser.stderr)
        print(browser.stdout)
        latest = OperationalRun.objects.filter(program=self.target).first()
        approved = vault.active(methods.COMPOSITE)
        self.assertEqual(latest.snapshot['approved_weights']['id'], approved.pk)
        expected = fixture.oracle({code: Fraction(value) for code, value in approved.validation['weights'].items()})
        for label, application in self.apps.items():
            self.assertEqual(Fraction(latest.calculations[str(application.pk)]['score_exact']) * 100, expected[label]['score'])

    def test_select_and_publish_masked_results_preserves_scores_and_delivery(self):
        from assistance.models import AssistanceRelease
        from announcements.generation import generation_preview, generate_results
        from announcements.models import Announcement, ProgramResultRevision
        from announcements.results import results_current
        from .operational_models import OperationalDecision
        from .operational_forms import SelectAssistanceForm
        self.build('balanced')
        run = self.generate()
        frozen = deepcopy(run.payload())
        releases = AssistanceRelease.objects.count()
        url = reverse('ewaf:operational_workspace', args=[self.target.pk])
        data = {'action': 'SELECT_ASSISTANCE', 'decision-run_id': run.pk,
            'decision-application_id': self.apps['T07'].pk, 'decision-expected_revision': 0}
        response = self.client.get(url)
        self.assertContains(response, 'Select for assistance', count=12)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        decision = OperationalDecision.objects.get()
        self.assertEqual(decision.reason, SelectAssistanceForm.audit_reason)
        self.assertEqual(decision.outcome, 'SELECTED')
        self.assertEqual(AssistanceRelease.objects.count(), releases)
        plan = generation_preview(self.target.pk, user=self.user)
        self.assertEqual(len(plan['pending']), 11)
        self.assertEqual(len(plan['payload']['applicants']), 12)
        self.assertEqual(plan['payload']['rows'][0]['reference'], self.apps['T07'].public_reference)
        from announcements.generation import PERMISSIONS
        publisher = get_user_model().objects.create_user('publication_only', is_staff=True)
        grant(publisher, 'accounts.access_dashboard', *PERMISSIONS)
        with self.assertRaisesMessage(ValidationError, 'selection reviewer'):
            generation_preview(self.target.pk, user=publisher)
        with patch('announcements.results.record_event', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                generate_results(self.target.pk, user=self.user, expected=plan['expected'], version=plan['version'])
        self.assertEqual(OperationalDecision.objects.count(), 1)
        self.assertFalse(Announcement.objects.exists())
        self.assertFalse(ProgramResultRevision.objects.exists())
        result_url = reverse('announcements:prepare_results', args=[self.target.pk])
        page = self.client.get(result_url)
        self.assertContains(page, 'Publish results')
        self.assertContains(page, 'Application decisions remain unchanged')
        response = self.client.post(result_url, {'action': 'GENERATE_RESULTS',
            'expected': plan['expected'], 'version': plan['version']})
        self.assertEqual(response.status_code, 302)
        item = Announcement.objects.get(program=self.target)
        self.assertEqual(item.status, 'published')
        self.assertTrue(results_current(item))
        self.assertEqual(OperationalDecision.objects.filter(outcome='NOT_SELECTED').count(), 11)
        self.assertEqual(AssistanceRelease.objects.count(), releases)
        # A publisher can review completed decisions without receiving private
        # scoring access or authority to create beneficiary decisions.
        self.assertEqual(generation_preview(self.target.pk, user=publisher)['pending'], [])
        from django.test import Client
        for route in ('announcements:detail', 'core:result_detail'):
            response = Client().get(reverse(route, args=[item.pk]))
            self.assertContains(response, 'col-lg-6', count=2)
            for label, app in self.apps.items():
                self.assertContains(response, app.public_reference, count=2 if label == 'T07' else 1)
                self.assertNotContains(response, app.member.full_name)
                self.assertNotContains(response, app.status_token)
            self.assertNotContains(response, 'score_exact')
        with self.assertRaises(ValidationError):
            generate_results(self.target.pk, user=self.user, expected=plan['expected'], version=plan['version'])
        self.assertEqual(ProgramResultRevision.objects.count(), 1)
        run.refresh_from_db()
        self.assertEqual(run.payload(), frozen)

    def test_publish_after_confirmed_delivery_preserves_pool_and_release(self):
        from assistance.services import record_release
        from assistance.tests import release_data
        from assistance.models import AssistanceRelease
        from announcements.generation import generation_preview, generate_results
        from announcements.models import Announcement
        from announcements.results import results_current
        from .operational_models import OperationalDecision
        self.build('balanced')
        run = self.generate()
        frozen = deepcopy(run.payload())
        application = self.apps['T02']
        # The model default captured timezone.now at import time, outside the
        # fixture clock. Keep approval and receipt on the same synthetic date.
        with patch.object(OperationalDecision._meta.get_field('recorded_at'), 'default', lambda: fixture.NOW):
            operational.record_decision(self.target.pk, user=self.user, run_id=run.pk,
                application_id=application.pk, expected_revision=0, outcome='SELECTED', reason='Synthetic reviewed selection.')
        receipt = record_release(application.pk, user=self.user, data=release_data(application))
        receipt_before = deepcopy(AssistanceRelease.objects.values().get(pk=receipt.pk))
        application.refresh_from_db()
        self.assertEqual(application.status, 'COMPLETED')
        url = reverse('announcements:prepare_results', args=[self.target.pk])
        response = self.client.get(url)
        self.assertContains(response, 'Publish results')
        self.assertContains(response, 'program-grid')
        self.assertNotContains(response, 'APPLICATION_NOT_CANDIDATE')
        self.assertNotContains(response, 'APPLICATION_REVIEW_UNRESOLVED')
        self.assertEqual(len(response.context['roster']['applicants']), 12)
        self.assertEqual(len(response.context['roster']['rows']), 1)
        ranking = self.client.get(reverse('ewaf:operational_workspace', args=[self.target.pk]))
        self.assertTrue(ranking.context['result']['active'], ranking.context['result']['problems'])
        # Exercise the exact reported lifecycle through the actual Admin UI.
        browser = subprocess.run(['node', str(Path(settings.BASE_DIR) / 'scripts/result_publication_browser.cjs')],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_PROGRAM': str(self.target.pk),
                'QA_USERNAME': self.user.username, 'QA_PASSWORD': 'synthetic-only',
                'QA_SECOND': str(self.apps['T07'].pk), 'QA_REFERENCE': application.public_reference},
            capture_output=True, text=True, encoding='utf-8', timeout=180)
        self.assertEqual(browser.returncode, 0, browser.stdout + browser.stderr)
        print(browser.stdout)
        item = Announcement.objects.get(program=self.target)
        self.assertEqual(item.status, 'published')
        self.assertTrue(results_current(item))
        self.assertEqual(len(item.result_revision.public_payload['applicants']), 12)
        self.assertEqual(len(item.result_revision.public_payload['rows']), 2)
        self.assertEqual(OperationalDecision.objects.filter(outcome='NOT_SELECTED').count(), 0)
        self.assertEqual(AssistanceRelease.objects.values().get(pk=receipt.pk), receipt_before)
        self.assertEqual(AssistanceRelease.objects.count(), 28)
        run.refresh_from_db()
        self.assertEqual(run.payload(), frozen)
        application.refresh_from_db()
        self.assertEqual(application.status, 'COMPLETED')
        from django.test import Client
        public = Client().get(reverse('core:result_detail', args=[item.pk]))
        self.assertContains(public, application.public_reference, count=2)
        self.assertNotContains(public, application.member.full_name)
        # Verified-final generation still requires current weights; publication
        # of recorded selections is independent of calculation readiness.
        self.approve('ses')
        with self.assertRaisesMessage(ValidationError, 'weights changed'):
            generation_preview(self.target.pk, user=self.user)
        self.assertTrue(results_current(item))
        blocked = self.client.get(url)
        self.assertEqual(len(blocked.context['roster']['applicants']), 12)
        self.assertEqual(len(blocked.context['roster']['rows']), 2)
        self.assertIsNotNone(blocked.context['preview'])
        self.assertEqual(Announcement.objects.count(), 1)

    def test_selection_and_generation_reject_stale_or_unauthorized_requests(self):
        from announcements.generation import generation_preview, generate_results
        from announcements.models import Announcement
        from .operational_models import OperationalDecision
        self.build('balanced')
        run = self.generate()
        plan = generation_preview(self.target.pk, user=self.user)
        operational.record_decision(self.target.pk, user=self.user, run_id=run.pk,
            application_id=self.apps['T07'].pk, expected_revision=0, outcome='SELECTED', reason='Synthetic selection.')
        with self.assertRaisesMessage(ValidationError, 'changed'):
            generate_results(self.target.pk, user=self.user, expected=plan['expected'], version=plan['version'])
        operational.record_decision(self.target.pk, user=self.user, run_id=run.pk,
            application_id=self.apps['T06'].pk, expected_revision=0, outcome='DEFERRED', reason='Synthetic unresolved review.')
        with self.assertRaisesMessage(ValidationError, 'deferred'):
            generation_preview(self.target.pk, user=self.user)
        viewer = get_user_model().objects.create_user('selection_viewer', is_staff=True)
        from announcements.generation import PERMISSIONS
        grant(viewer, 'accounts.access_dashboard', *operational.VIEW,
              *[code for code in PERMISSIONS if code != 'announcements.publish_announcement'])
        self.client.force_login(viewer)
        response = self.client.post(reverse('ewaf:operational_workspace', args=[self.target.pk]), {
            'action': 'SELECT_ASSISTANCE', 'decision-run_id': run.pk,
            'decision-application_id': self.apps['T01'].pk, 'decision-expected_revision': 0})
        self.assertEqual(response.status_code, 403)
        response = self.client.post(reverse('announcements:prepare_results', args=[self.target.pk]), {
            'action': 'GENERATE_RESULTS', 'expected': plan['expected'], 'version': 0})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(OperationalDecision.objects.count(), 2)
        self.assertFalse(Announcement.objects.exists())
        self.client.force_login(self.user)
        self.approve('ses')
        with self.assertRaisesMessage(ValidationError, 'weights changed'):
            generation_preview(self.target.pk, user=self.user)
        response = self.client.post(reverse('ewaf:operational_workspace', args=[self.target.pk]), {
            'action': 'SELECT_ASSISTANCE', 'decision-run_id': run.pk,
            'decision-application_id': self.apps['T01'].pk, 'decision-expected_revision': 0})
        self.assertContains(response, 'changed')
        self.assertEqual(OperationalDecision.objects.count(), 2)

    def test_preview_authority_stale_edits_and_approval_audit_rollback(self):
        url = reverse('ewaf:vault')
        data = self.preview('ses')
        counts = VaultRevision.objects.count(), LogEntry.objects.count()
        for changes in ({'weight_review': ''}, {'weight_review': 'forged'},
                        {'slider_proposal': json.dumps(fixture.proposal('hm'))}, {'expected': 'stale'}):
            result = self.client.post(url, data | {'action': 'LOCKED'} | changes)
            self.assertEqual(result.status_code, 200)
            self.assertTrue(result.context['form'].errors)
            self.assertEqual(counts, (VaultRevision.objects.count(), LogEntry.objects.count()))
        creator = LogEntry.objects.create
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise RuntimeError('SYNTHETIC approval audit failure')
            return creator(*args, **kwargs)
        with patch.object(LogEntry.objects, 'create', side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                self.client.post(url, data | {'action': 'LOCKED'})
        self.assertEqual(counts, (VaultRevision.objects.count(), LogEntry.objects.count()))
        self.approve('balanced')
        stale = self.client.post(url, data | {'action': 'LOCKED'})
        self.assertTrue(stale.context['form'].errors)
        viewer = get_user_model().objects.create_user('SYNTHETIC-NO-WEIGHT-APPROVAL', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *operational.VIEW)
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(url, data | {'action': 'LOCKED'}).status_code, 403)
        self.client.force_login(self.user)
        data = self.preview('ses')
        approver = get_user_model().objects.create_user('SYNTHETIC-APPROVE-ONLY', is_staff=True)
        grant(approver, 'accounts.access_dashboard', *operational.VIEW, 'ewaf.authorize_operational')
        self.client.force_login(approver)
        self.assertEqual(self.client.post(url, data | {'action': 'LOCKED'}).status_code, 403)

    def test_generate_without_reason_preserves_audit_history_and_permissions(self):
        from .operational_forms import GenerateForm
        self.build('balanced')
        previous = self.generate()
        retained = deepcopy(previous.payload())
        url = reverse('ewaf:operational_workspace', args=[self.target.pk])
        page = self.client.get(url)
        self.assertNotIn('reason', page.context['form'].fields)
        for text in ('Download private calculation (JSON)', 'Shared configuration',
                     'Next ranking:', 'Enter / verify EWAF information',
                     'Decision history', 'Calculation history'):
            self.assertNotContains(page, text)
        data = {'action': 'GENERATE', 'expected': json.dumps(operational.context(self.target.pk, user=self.user)),
            'request_key': str(uuid4())}
        count = OperationalRun.objects.count()
        self.assertEqual(self.client.post(url, data).status_code, 302)
        run = OperationalRun.objects.filter(program=self.target).first()
        self.assertEqual(run.reason, GenerateForm.audit_reason)
        self.assertEqual(run.actor_id, self.user.pk)
        self.assertEqual(run.previous_id, previous.pk)
        self.assert_scores(run, 'balanced', self.apps)
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertEqual(OperationalRun.objects.count(), count + 1)
        previous.refresh_from_db()
        self.assertEqual(previous.payload(), retained)
        previous.clean()
        self.assertEqual(self.client.get(reverse('ewaf:operational_export',
            args=[self.target.pk, previous.pk])).status_code, 200)
        viewer = get_user_model().objects.create_user('SYNTHETIC-RANKING-VIEWER', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', *operational.VIEW)
        self.client.force_login(viewer)
        self.assertEqual(self.client.post(url, data).status_code, 403)
        self.assertEqual(OperationalRun.objects.count(), count + 1)

    def test_frozen_weight_replay_rejects_tampering_and_approval_during_generation_rolls_back(self):
        self.build('balanced')
        self.approve('ses')
        run = self.generate()
        for change in ({'id': 999999}, {'method': methods.SES}, {'contract': 'other'},
                       {'weights': {'SES': '1', 'ES': '0', 'PA': '0', 'HM': '0'}}):
            snapshot = deepcopy(run.snapshot)
            snapshot['approved_weights'].update(change)
            with self.assertRaises(ValidationError):
                live_math.calculations(snapshot, run.configuration)
        old = deepcopy(run.payload())
        self.approve('hm')
        run.refresh_from_db()
        self.assertEqual(run.payload(), old)
        self.assert_scores(run, 'ses', self.apps)
        with operational.fence(self.target.pk, self.user) as (actor, program, applications):
            with self.assertRaisesMessage(ValidationError, 'Vault weights changed'):
                operational._current(program, applications, actor, run.pk)
        counts = OperationalRun.objects.count(), VaultRevision.objects.count(), LogEntry.objects.count()
        original = operational.policy.calculations
        def racing(snapshot, configuration):
            self.approve('pa')
            return original(snapshot, configuration)
        expected = operational.context(self.target.pk, user=self.user)
        with patch.object(operational.policy, 'calculations', side_effect=racing):
            # Retained-run replay may now detect this injected approval during
            # preflight. Both fences must reject it and roll back every write.
            with self.assertRaisesMessage(ValidationError, 'changed'):
                operational.generate(self.target.pk, user=self.user, expected=expected,
                    reason='SYNTHETIC approval changes during calculation', request_key=uuid4())
        self.assertEqual(counts, (OperationalRun.objects.count(), VaultRevision.objects.count(), LogEntry.objects.count()))
