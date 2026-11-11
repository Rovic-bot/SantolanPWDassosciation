"""Operational workflow against fictional records in disposable native MySQL."""
from copy import deepcopy
from decimal import Decimal, localcontext
from unittest.mock import patch
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import models
from django.test import TransactionTestCase, Client
from django.urls import reverse

from .operational_testsupport import OperationalHelpers
from .operational_models import OperationalConfiguration as Configuration, OperationalRun as Run, OperationalDecision as Decision
from . import operational_services as service
from .operational_policy import findings
from .four_criterion_development import ahp


class OperationalTests(OperationalHelpers, TransactionTestCase):
    def setUp(self):
        self.setup_operational()
        self.client.force_login(self.officer)

    def test_private_profile_previews_retain_audits_without_invalidating_unchanged_evidence(self):
        from members.models import MemberEvent
        from membership.models import MembershipEvent
        from documents.services import verify_document
        self.lock_policy()
        run = self.calculate()
        original = deepcopy(run.payload())
        document = next(iter(self.criterion_documents.values()))
        before_member = MemberEvent.objects.filter(action='document_downloaded').count()
        before_intake = MembershipEvent.objects.filter(action='document_downloaded').count()
        for url in (reverse('members:document', args=[self.member.pk, document.pk]),
                    reverse('membership:document', args=[document.pk])):
            response = self.client.get(url, {'preview': '1'})
            self.assertEqual(response.status_code, 200)
            response.close()
        self.assertEqual(MemberEvent.objects.filter(action='document_downloaded').count(), before_member + 1)
        self.assertEqual(MembershipEvent.objects.filter(action='document_downloaded').count(), before_intake + 1)
        with service.fence(self.program.pk, self.officer) as (actor, program, applications):
            self.assertEqual(service._current(program, applications, actor, run.pk).pk, run.pk)
        run.refresh_from_db()
        self.assertEqual(run.payload(), original)
        verify_document(document.pk, user=self.officer, member_version=self.member.version,
            verified=True, expires_on=None, reason='Fictional renewed verification must invalidate the old evidence.')
        with self.assertRaises(ValidationError):
            with service.fence(self.program.pk, self.officer) as (actor, program, applications):
                service._current(program, applications, actor, run.pk)

    def test_draft_missing_fields_visible_and_lock_is_explicit(self):
        row = service.record_configuration(self.program.pk, user=self.officer, expected=service.configuration_token(self.program),
            proposed={}, judgments={}, status='DRAFT', reason='Fictional unresolved draft')
        self.assertEqual(row.status, 'DRAFT')
        self.assertTrue(any('SI.bounds.lower' in item for item in findings({}, {})))
        with self.assertRaises(ValidationError):
            self.calculate()
        response = self.client.get(reverse('ewaf:operational_configuration', args=[self.program.pk]), follow=True)
        self.assertContains(response, 'Scoring settings are incomplete or need approval')
        with self.assertRaises(ValidationError):
            service.record_configuration(self.program.pk, user=self.officer, expected=service.configuration_token(self.program),
                proposed=self.proposal, judgments=ahp()['pairs'], status='LOCKED', reason='Fictional no attestation')

    def test_exact_calculation_predecessor_reasoned_decisions_and_separation(self):
        from assistance.models import AssistanceCase, AssistanceRelease
        before = list(AssistanceCase.objects.values())
        self.lock_policy()
        run = self.calculate()
        run.clean()
        self.assertEqual(len(run.calculations), 1)
        row = run.calculations[str(self.application.pk)]
        self.assertEqual([r['criterion'] for r in row['traces']], ['SI', 'ES', 'PA', 'ND'])
        with localcontext() as context:
            context.prec = 50
            self.assertEqual(Decimal(row['score_0_1']), sum(Decimal(t['contribution']) for t in row['traces']))
        decision = self.choose(run)
        decision.clean()
        self.assertEqual(self.choose(run).pk, decision.pk)
        self.assertEqual(list(AssistanceCase.objects.values()), before)
        self.assertFalse(AssistanceRelease.objects.exists())
        successor = self.calculate()
        self.assertEqual(successor.previous_id, run.pk)
        with self.assertRaises(ValidationError):
            self.choose(run, expected_revision=1)
        self.choose(successor, expected_revision=1, outcome='DEFERRED', reason='Fictional re-evaluation after recalculation')
        self.assertEqual(Decision.objects.count(), 2)
        run.refresh_from_db()
        run.clean()
        from django.core.paginator import Paginator
        with patch('ewaf.operational_views.Paginator', side_effect=lambda objects, size: Paginator(objects, 1)):
            response = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]) + '?history_page=2')
        self.assertEqual([row.pk for row in response.context['history']], [run.pk])
        self.assertNotContains(response, 'Calculation and recalculation history')
        self.assertContains(response, 'EWAF Ranking and human selection')

    def test_stale_sources_permissions_and_audit_rollback(self):
        self.lock_policy()
        run = self.calculate()
        restricted = get_user_model().objects.create_user('restricted_operational', is_staff=True)
        with self.assertRaises(PermissionDenied):
            service.context(self.program.pk, user=restricted)
        with patch('programs.models.ProgramLog.objects.create', side_effect=ValidationError('audit failed')):
            with self.assertRaises(ValidationError):
                self.choose(run)
        self.assertFalse(Decision.objects.exists())
        from django.contrib.admin.models import LogEntry, CHANGE
        from django.contrib.contenttypes.models import ContentType
        from documents.models import DocumentType
        LogEntry.objects.create(user=self.officer, content_type=ContentType.objects.get_for_model(DocumentType),
            object_id=str(self.document.requirement.document_type_id), object_repr='Fictional reference', action_flag=CHANGE,
            change_message='Fictional reference changed and restored; retain intervening audit.')
        with self.assertRaises(ValidationError):
            self.choose(run)
        run = self.calculate()
        from members.models import Member
        models.QuerySet.update(Member.objects.filter(pk=self.member.pk), version=self.member.version + 1)
        with self.assertRaises(ValidationError):
            self.choose(run)
        self.assertFalse(Decision.objects.exists())

    def test_immutable_guards_and_tamper_detection(self):
        self.lock_policy()
        run = self.calculate()
        decision = self.choose(run)
        for row in (self.operational_configuration, run, decision):
            with self.assertRaises(ValidationError):
                row.save()
            with self.assertRaises(ValidationError):
                type(row).objects.filter(pk=row.pk).update(reason='tampered')
        models.QuerySet.update(Decision.objects.filter(pk=decision.pk), reason='tampered')
        decision.refresh_from_db()
        with self.assertRaises(ValidationError):
            decision.clean()

    def test_policy_replacement_incomplete_bounds_and_consistency(self):
        self.lock_policy()
        run = self.calculate()
        invalid = deepcopy(self.proposal)
        invalid['criteria']['SI']['bounds']['upper'] = '0'
        with self.assertRaisesMessage(ValidationError, 'SI.bounds'):
            service.record_configuration(self.program.pk, user=self.officer, expected=service.configuration_token(self.program),
                proposed=invalid, judgments=ahp()['pairs'], status='LOCKED', reason='Fictional invalid range', attested=True)
        self.assertEqual(Configuration.objects.count(), 1)
        service.record_configuration(self.program.pk, user=self.officer, expected=service.configuration_token(self.program),
            proposed=invalid, judgments={}, status='DRAFT', reason='Fictional correction pending')
        with self.assertRaises(ValidationError):
            self.choose(run)

    def test_pages_permissions_csrf_and_no_public_data(self):
        self.lock_policy()
        run = self.calculate()
        urls = [reverse('ewaf:operational_programs'), reverse('ewaf:operational_workspace', args=[self.program.pk]),
                reverse('ewaf:operational_configuration', args=[self.program.pk]), reverse('ewaf:operational_run', args=[self.program.pk, run.pk])]
        for url in urls:
            response = self.client.get(url, follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertIn('no-store', response['Cache-Control'])
            self.assertEqual(Client().get(url).status_code, 302)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.officer)
        self.assertEqual(protected.post(urls[-1], {}).status_code, 403)
        self.assertNotContains(self.client.get('/'), run.digest)

    def test_real_configuration_post_recalculation_and_decision_forms(self):
        from .operational_forms import ConfigurationForm
        draft = service.record_configuration(self.program.pk, user=self.officer,
            expected=service.configuration_token(self.program), proposed=self.proposal, judgments=ahp()['pairs'],
            status='DRAFT', reason='Fictional previously recorded scoring definitions')
        form = ConfigurationForm(configuration=draft, initial={'expected': service.configuration_token(self.program)})
        data = {name: (field.value() if field.value() is not None else '') for name, field in ((name, form[name]) for name in form.fields)}
        import json
        for name in ('classifications', 'SI_encoding', 'ES_encoding', 'PA_encoding', 'ND_encoding'):
            if isinstance(data[name], (dict, list)):
                data[name] = json.dumps(data[name])
        data.update(action='LOCKED', reason='Fictional policy entered through the actual Admin form', attested='on')
        url = reverse('ewaf:operational_configuration', args=[self.program.pk])
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, response.content.decode()[:3000])
        configuration = Configuration.objects.first()
        self.assertEqual(configuration.status, 'LOCKED')
        url = reverse('ewaf:operational_workspace', args=[self.program.pk])
        response = self.client.post(url, {'expected': json.dumps(service.context(self.program.pk, user=self.officer)),
            'request_key': str(uuid4()), 'reason': 'Fictional form generation'})
        self.assertEqual(response.status_code, 302)
        run = Run.objects.get()
        url = reverse('ewaf:operational_run', args=[self.program.pk, run.pk])
        response = self.client.post(url, {'decision-run_id': run.pk, 'decision-application_id': str(self.application.pk),
            'decision-expected_revision': 0, 'decision-outcome': 'SELECTED', 'decision-reason': 'Fictional form human decision'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Decision.objects.get().outcome, 'SELECTED')

    def test_publication_explicit_masked_and_withheld_after_recalculation(self):
        from announcements.results import prepare_results, publish_results, results_current, collect_results
        self.lock_policy()
        run = self.calculate()
        with self.assertRaises(ValidationError):
            collect_results(self.program)
        self.choose(run)
        item = prepare_results(self.program.pk, user=self.officer, version=0, reason='Fictional explicit publication preparation')
        self.assertEqual(item.status, 'draft')
        payload = item.result_revision.public_payload
        self.assertNotIn(self.member.full_name, str(payload))
        self.assertNotIn(self.application.public_reference, str(payload))
        self.assertNotIn('score_0_100', str(payload))
        item = publish_results(item.pk, user=self.officer, version=item.version)
        self.assertTrue(results_current(item))
        get_user_model().objects.filter(pk=self.officer.pk).update(is_active=False)
        self.assertFalse(results_current(item))
        get_user_model().objects.filter(pk=self.officer.pk).update(is_active=True)
        self.calculate()
        self.assertFalse(results_current(item))

    def test_final_freshness_failure_rolls_back_calculation_and_decision_audits(self):
        from programs.models import ProgramLog
        self.lock_policy()
        expected = service.context(self.program.pk, user=self.officer)
        before = ProgramLog.objects.count()
        original = service.capture
        calls = []
        def changed(*args, **kwargs):
            value = original(*args, **kwargs)
            calls.append(1)
            if len(calls) > 1:
                raise ValidationError('Injected final freshness failure')
            return value
        with patch('ewaf.operational_services.capture', side_effect=changed), self.assertRaises(ValidationError):
            service.generate(self.program.pk, user=self.officer, expected=expected, reason='Fictional rollback', request_key=uuid4())
        self.assertFalse(Run.objects.exists())
        self.assertEqual(ProgramLog.objects.count(), before)
        run = self.calculate()
        before = ProgramLog.objects.count()
        calls.clear()
        with patch('ewaf.operational_services.capture', side_effect=changed), self.assertRaises(ValidationError):
            self.choose(run)
        self.assertFalse(Decision.objects.exists())
        self.assertEqual(ProgramLog.objects.count(), before)

    def test_policy_date_range_classification_and_stale_config_token(self):
        invalid = deepcopy(self.proposal)
        invalid.update(pa_period='date_range', pa_start='2026-10-10', pa_end='2026-10-01')
        self.assertTrue(any('pa_start' in row for row in findings(invalid, ahp()['pairs'])))
        invalid = deepcopy(self.proposal)
        invalid.update(classification_mode='thresholds', classifications=[{'label': 'fictional', 'lower': '1', 'upper': '100'}])
        self.assertTrue(any('classifications' in row for row in findings(invalid, ahp()['pairs'])))
        expected = service.configuration_token(self.program)
        self.lock_policy(classification_mode='thresholds', classifications=[{'label': 'Fictional reviewed band', 'lower': '0', 'upper': '100'}])
        self.assertEqual(self.calculate().calculations[str(self.application.pk)]['classification'], 'Fictional reviewed band')
        with self.assertRaises(ValidationError):
            service.record_configuration(self.program.pk, user=self.officer, expected=expected, proposed=self.proposal,
                judgments=ahp()['pairs'], status='DRAFT', reason='Fictional stale policy edit')

    def test_expiry_and_revoked_permission_are_checked_against_current_records(self):
        from datetime import timedelta
        from django.utils import timezone
        self.lock_policy()
        run = self.calculate()
        with patch('django.utils.timezone.now', return_value=timezone.now() + timedelta(days=1)):
            with service.fence(self.program.pk, self.officer) as (current, program, applications):
                self.assertEqual(service._current(program, applications, current, run.pk).pk, run.pk)
        with patch('django.utils.timezone.now', return_value=run.valid_until + timedelta(seconds=1)), self.assertRaises(ValidationError):
            self.choose(run)
        get_user_model().objects.filter(pk=self.officer.pk).update(is_active=False)
        with self.assertRaises(PermissionDenied):
            self.choose(run)

    def test_fresh_authorized_second_officer_can_review_without_original_session(self):
        from accounts.authority_services import enlisted
        self.assertFalse(enlisted())
        self.lock_policy()
        run = self.calculate()
        other = get_user_model().objects.create_superuser('fictional_second_operational_officer')
        row = self.choose(run, user=other)
        self.assertEqual(row.actor_id, other.pk)


class OperationalPoolTests(OperationalHelpers, TransactionTestCase):
    def test_concurrent_calculation_requests_have_one_current_successor(self):
        from accounts.tests.test_authority_generation import worker
        self.setup_operational()
        self.lock_policy()
        expected = service.context(self.program.pk, user=self.officer)
        barrier = Barrier(2)
        def calculate():
            barrier.wait()
            try:
                return service.generate(self.program.pk, user=self.officer, expected=expected,
                    reason='Fictional simultaneous calculation', request_key=uuid4()).pk
            except ValidationError as error:
                return error.messages
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [future.result(timeout=60) for future in [pool.submit(worker, calculate), pool.submit(worker, calculate)]]
        self.assertEqual(sum(isinstance(value[1], int) for value in outcomes), 1, outcomes)
        self.assertEqual(Run.objects.count(), 1)

    def test_supported_source_writer_waits_then_invalidates_decision_use(self):
        from accounts.tests.test_authority_generation import worker
        from documents.services import verify_document
        from threading import Event
        from concurrent.futures import TimeoutError
        self.setup_operational()
        self.lock_policy()
        run = self.calculate()
        entered, release, writer_entered = Event(), Event(), Event()
        original = Decision.save
        def hold(row, *args, **kwargs):
            entered.set()
            if not release.wait(20):
                raise AssertionError('Decision test barrier timed out')
            return original(row, *args, **kwargs)
        def change():
            writer_entered.set()
            return verify_document(self.document.pk, user=self.officer, member_version=self.member.version,
                verified=False, expires_on=None, reason='Fictional evidence correction after decision').pk
        with ThreadPoolExecutor(max_workers=2) as pool, patch.object(Decision, 'save', hold):
            decision = pool.submit(worker, lambda: self.choose(run).pk)
            self.assertTrue(entered.wait(20))
            correction = pool.submit(worker, change)
            self.assertTrue(writer_entered.wait(20))
            try:
                with self.assertRaises(TimeoutError):
                    correction.result(timeout=.2)
            finally:
                release.set()
            self.assertIsInstance(decision.result(timeout=30)[1], int)
            self.assertIsInstance(correction.result(timeout=30)[1], int)
        with self.assertRaises(ValidationError):
            self.choose(run, expected_revision=1, outcome='NOT_SELECTED')
        self.assertEqual(Decision.objects.count(), 1)
        Decision.objects.get().clean()

    def test_engineering_pool_limit_blocks_without_partial_results(self):
        self.setup_operational(additional=1)
        self.lock_policy()
        with patch('ewaf.operational_policy.MAX_POOL', 1), self.assertRaisesMessage(ValidationError, 'WHOLE_POOL_UNSUPPORTED'):
            self.calculate()
        self.assertFalse(Run.objects.exists())

    def test_exact_ties_slot_capacity_and_concurrent_decisions(self):
        self.setup_operational(additional=2)
        self.client.force_login(self.officer)
        self.lock_policy()
        run = self.calculate()
        self.assertEqual(len(run.calculations), 3)
        # First applicant and additional applicant 0 share every verified value.
        self.assertEqual(run.calculations[str(self.application.pk)]['comparison']['equal'], 2)
        with self.assertRaisesMessage(ValidationError, 'tie_reason'):
            self.choose(run, tie_reason='')
        response = self.client.post(reverse('ewaf:operational_workspace', args=[self.program.pk]), {
            'action': 'SELECT_ASSISTANCE', 'decision-run_id': run.pk,
            'decision-application_id': self.application.pk, 'decision-expected_revision': 0})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Decision.objects.exists())
        from announcements.generation import generation_preview
        with self.assertRaisesMessage(ValidationError, 'tie procedure'):
            generation_preview(self.program.pk, user=self.officer)
        barrier = Barrier(2)
        from accounts.tests.test_authority_generation import worker
        def choose(identifier):
            barrier.wait()
            try:
                return self.choose(run, application_id=identifier).pk
            except ValidationError as error:
                return error.messages
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, lambda identifier=helper.application.pk: choose(identifier)) for helper in self.helpers[:2]]
            outcomes = [f.result(timeout=60) for f in futures]
        self.assertEqual(sum(isinstance(outcome[1], int) for outcome in outcomes), 1, outcomes)
        self.assertEqual(Decision.objects.filter(outcome='SELECTED').count(), 1)
        remaining = self.helpers[-1].application
        response = self.client.post(reverse('ewaf:operational_workspace', args=[self.program.pk]), {
            'action': 'SELECT_ASSISTANCE', 'decision-run_id': run.pk,
            'decision-application_id': remaining.pk, 'decision-expected_revision': 0})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decision.objects.filter(outcome='SELECTED').count(), 1)

    def test_pending_applicant_blocks_complete_pool_and_hold_blocks_ties(self):
        self.setup_operational(additional=1)
        self.client.force_login(self.officer)
        self.lock_policy(tie_rule='hold')
        run = self.calculate()
        with self.assertRaisesMessage(ValidationError, 'tie_rule'):
            self.choose(run)
        response = self.client.post(reverse('ewaf:operational_workspace', args=[self.program.pk]), {
            'action': 'SELECT_ASSISTANCE', 'decision-run_id': run.pk, 'decision-tie_reason': 'Cannot override a held tie',
            'decision-application_id': self.application.pk, 'decision-expected_revision': 0})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Decision.objects.exists())
        from programs.models import ProgramApplication
        models.QuerySet.update(ProgramApplication.objects.filter(pk=self.helpers[-1].application.pk), status='NEEDS_INFORMATION')
        with self.assertRaisesMessage(ValidationError, 'APPLICATION_REVIEW_UNRESOLVED'):
            self.calculate()
