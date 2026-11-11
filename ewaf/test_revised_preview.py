"""Permission, immutable history and concurrent synthetic preview tests on MySQL."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
import json
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections, models
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from programs.models import Program, ProgramLog, ProgramTermsLock
from scripts.durable_test_runner import require_disposable
from ewaf.operational_services import VIEW
from ewaf.revised import services as s
from ewaf.revised.models import RevisedPreviewRun as Run, RevisedPreviewReview as Review
from ewaf.revised.math import CRITERIA, DEFAULTS


class RevisedPreviewTests(TransactionTestCase):
    def setUp(self):
        require_disposable()
        self.user = get_user_model().objects.create_superuser('synthetic-revised-admin', password='synthetic-only')
        self.program = Program.objects.create(name='Synthetic revised EWAF context', description='Fictional program',
            assistance_type='Fictional', registration_opens_at=timezone.now() - timedelta(days=2),
            registration_closes_at=timezone.now() - timedelta(days=1), slots=1)
        ProgramTermsLock.objects.get_or_create(pk=1)
        self.client.force_login(self.user)
        self.url = reverse('ewaf:revised_preview')

    def retain(self, **overrides):
        return s.retain(self.program.pk, **{'user': self.user, 'expected': s.token(self.program),
            'request_key': uuid4(), 'reason': 'Synthetic arithmetic review only.', **overrides})

    def post_data(self, **overrides):
        return {**dict(zip(CRITERIA, DEFAULTS)), 'mode': 'DOCUMENT_EXAMPLE', 'classify': 'on',
            'request_key': uuid4(), 'expected': s.token(self.program),
            'reason': 'Synthetic form review.', 'action': 'PREVIEW', **overrides}

    def staff(self, name='synthetic-viewer', extra=()):
        user = get_user_model().objects.create_user(name, is_staff=True)
        for key in ('accounts.access_dashboard', *VIEW, 'ewaf.view_revisedpreview', *extra):
            app, code = key.split('.')
            user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=code))
        return user


    def test_permission_denial_on_page_calculation_history_review_and_exports(self):
        run = self.retain()
        viewer = self.staff()
        self.client.force_login(viewer)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('ewaf:operational_programs'))
        self.assertNotIn(b'83.90', response.content)
        self.assertEqual(self.client.post(self.url, self.post_data()).status_code, 405)
        self.assertEqual(self.client.get(reverse('ewaf:revised_run', args=[run.pk])).status_code, 200)
        self.assertEqual(self.client.post(reverse('ewaf:revised_run', args=[run.pk]), {}).status_code, 403)
        self.assertEqual(self.client.get(reverse('ewaf:revised_export', args=[run.pk])).status_code, 403)
        viewer.is_active = False; viewer.save()
        with self.assertRaises(PermissionDenied):
            s.preview(user=viewer)
        outsider = get_user_model().objects.create_user('synthetic-no-authority', is_staff=True)
        self.client.force_login(outsider)
        for url in (self.url, reverse('ewaf:revised_run', args=[run.pk]), reverse('ewaf:revised_export', args=[run.pk])):
            self.assertEqual(self.client.get(url).status_code, 403)

    def test_anonymous_csrf_and_no_public_ranks(self):
        run = self.retain()
        anonymous = Client()
        for url in (self.url, reverse('ewaf:revised_run', args=[run.pk]), reverse('ewaf:revised_export', args=[run.pk])):
            response = anonymous.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertNotIn(b'83.90', response.content)
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url, self.post_data()).status_code, 403)
        for url in ('/', '/programs/', '/announcements/'):
            response = anonymous.get(url)
            self.assertNotIn(b'83.90', response.content)
            self.assertNotIn(b'Internal rank', response.content)

    def test_retained_run_records_full_context_replays_and_has_no_selection_effects(self):
        from ewaf.operational_models import OperationalRun, OperationalDecision, OperationalConfiguration
        from assistance.models import AssistanceRelease, AssistanceCase
        counts = [model.objects.count() for model in (OperationalRun, OperationalDecision, OperationalConfiguration, AssistanceRelease, AssistanceCase)]
        run = self.retain()
        run.clean()
        self.assertEqual(run.actor_id, self.user.pk)
        self.assertEqual(run.program_id, self.program.pk)
        self.assertEqual(run.pool['expected_ids'], ['A', 'B', 'C'])
        self.assertEqual(run.pool['cutoff'], '2026-10-25T00:00:00+00:00')
        self.assertEqual(run.result['normalization'], 'dataset-minmax-v1')
        self.assertEqual([row['rank'] for row in run.result['applicants']], [1, 2, 3])
        self.assertIn('zero comparison tolerance', run.result['precision'])
        self.assertTrue(LogEntry.objects.filter(pk=run.audit_entry_id).exists())
        self.assertEqual(counts, [model.objects.count() for model in (OperationalRun, OperationalDecision, OperationalConfiguration, AssistanceRelease, AssistanceCase)])
        self.assertFalse(run.result['official'])

    def test_new_draft_and_run_leave_predecessor_and_approved_engines_untouched(self):
        first = self.retain(); original = first.payload()
        values = dict(zip(CRITERIA, DEFAULTS)); values['HI'] = '40.00'
        second = self.retain(mode='DRAFT_SENSITIVITY', proposed=values)
        first.refresh_from_db(); first.clean(); second.clean()
        self.assertEqual(first.payload(), original)
        self.assertEqual(second.previous_id, first.pk)
        self.assertEqual(second.revision, 2)
        self.assertNotEqual(first.result['applicants'][0]['score_0_100'], second.result['applicants'][0]['score_0_100'])
        self.assertFalse(s.current(first)); self.assertTrue(s.current(second))

    def test_stale_preview_context_or_review_is_rejected(self):
        expected = s.token(self.program)
        run = self.retain()
        with self.assertRaises(ValidationError):
            self.retain(expected=expected)
        review_expected = s.review_token(run)
        s.review(run.pk, user=self.user, expected=review_expected, finding='REVIEWED', reason='Synthetic independent review')
        with self.assertRaises(ValidationError):
            s.review(run.pk, user=self.user, expected=review_expected, finding='REVIEWED', reason='Stale review')
        self.program.version += 1; self.program.save()
        original = run.payload()
        self.assertFalse(s.current(run))
        with self.assertRaises(ValidationError):
            s.review(run.pk, user=self.user, expected=s.review_token(run), finding='REVIEWED', reason='Changed program context')
        run.refresh_from_db(); self.assertEqual(run.payload(), original)
        response = self.client.get(reverse('ewaf:revised_run', args=[run.pk]))
        self.assertContains(response, 'Historical preview')

    def test_request_retry_is_idempotent_but_mismatched_payload_is_rejected(self):
        key, expected = uuid4(), s.token(self.program)
        one = self.retain(request_key=key, expected=expected)
        two = self.retain(request_key=key, expected=expected)
        self.assertEqual(one.pk, two.pk)
        with self.assertRaises(ValidationError):
            self.retain(request_key=key, expected=expected, reason='Different request content')
        self.assertEqual(Run.objects.count(), 1)

    def test_run_and_review_audit_failure_roll_back(self):
        before = LogEntry.objects.count()
        with patch('ewaf.revised.services.LogEntry.objects.create', side_effect=ValidationError('audit failed')):
            with self.assertRaisesMessage(ValidationError, 'audit failed'):
                self.retain()
        self.assertFalse(Run.objects.exists()); self.assertEqual(LogEntry.objects.count(), before)
        run = self.retain()
        with patch('ewaf.revised.services.LogEntry.objects.create', side_effect=ValidationError('audit failed')):
            with self.assertRaises(ValidationError):
                s.review(run.pk, user=self.user, expected=s.review_token(run), finding='REVIEWED', reason='Synthetic review')
        self.assertFalse(Review.objects.exists())

    def test_permission_revocation_during_write_rolls_back_run_and_audit(self):
        persist = s.persist
        def revoke(row):
            result = persist(row)
            get_user_model().objects.filter(pk=self.user.pk).update(is_active=False)
            return result
        before = LogEntry.objects.count()
        with patch.object(s, 'persist', side_effect=revoke):
            with self.assertRaises(PermissionDenied):
                self.retain()
        self.assertFalse(Run.objects.exists()); self.assertEqual(LogEntry.objects.count(), before)

    def test_no_mutation_manual_scores_or_fake_review_approval(self):
        run = self.retain()
        with self.assertRaises(ValidationError):
            run.save()
        with self.assertRaises(ValidationError):
            Run.objects.filter(pk=run.pk).update(result={})
        with self.assertRaises(ValidationError):
            run.delete()
        with self.assertRaises(ValidationError):
            s.review(run.pk, user=self.user, expected=s.review_token(run), finding='SELECTED', reason='Cannot choose')
        models.QuerySet.update(Run.objects.filter(pk=run.pk), result={})
        run.refresh_from_db()
        with self.assertRaises(ValidationError):
            run.clean()

    def test_review_history_is_locked_and_never_authorizes_official_use(self):
        run = self.retain()
        first = s.review(run.pk, user=self.user, expected=s.review_token(run), finding='REVIEWED', reason='Synthetic reviewed arithmetic')
        second = s.review(run.pk, user=self.user, expected=s.review_token(run), finding='CORRECTIONS_REQUESTED', reason='Synthetic display correction')
        self.assertEqual(second.previous_id, first.pk); first.clean(); second.clean()
        with self.assertRaises(ValidationError):
            first.save()
        with self.assertRaises(ValidationError):
            s.require_official_ready(self.program)

    def test_private_export_exact_snapshot_csv_xlsx_and_audit(self):
        run = self.retain()
        url = reverse('ewaf:revised_export', args=[run.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['record']['result'], run.result)
        self.assertFalse(data['official'])
        self.assertTrue({'no-store', 'private'} <= set(response['Cache-Control'].split(', ')))
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('attachment;', response['Content-Disposition'])
        csv = self.client.get(url, {'format': 'csv'})
        self.assertContains(csv, '7537/120')
        self.assertContains(csv, 'DOCUMENT_EXAMPLE')
        from openpyxl import load_workbook
        xlsx = self.client.get(url, {'format': 'xlsx'})
        workbook = load_workbook(BytesIO(xlsx.content), read_only=True)
        rows = list(workbook.active.values)
        self.assertEqual(len(rows), 16)
        self.assertIn('7537/120', {row[8] for row in rows[1:]})
        workbook.close()
        self.assertEqual(LogEntry.objects.filter(change_message__startswith='revised_preview_export').count(), 3)
        with patch('ewaf.revised.services.LogEntry.objects.create', side_effect=ValidationError('audit failed')):
            denied = self.client.get(url)
            self.assertEqual(denied.status_code, 400)
            self.assertNotIn(b'7537/120', denied.content)


    def test_retired_preview_rejects_new_runs_and_retained_history_stays_available(self):
        url = self.url + '?program=' + str(self.program.pk)
        response = self.client.post(url, self.post_data(action='RETAIN'))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(Run.objects.exists())
        run = self.retain()
        response = self.client.post(reverse('ewaf:revised_run', args=[run.pk]), {
            'expected': s.review_token(run), 'finding': 'REVIEWED', 'reason': 'Synthetic HTTP review'})
        self.assertEqual(response.status_code, 302); self.assertEqual(Review.objects.count(), 1)
        with patch.object(s, 'available', return_value=False):
            self.assertRedirects(self.client.get(self.url), reverse('ewaf:operational_programs'))
            self.assertEqual(self.client.get(reverse('ewaf:revised_run', args=[run.pk])).status_code, 503)

    def concurrent(self, function):
        barrier = Barrier(2)
        def worker(index):
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                return ('ok', function(index).pk)
            except ValidationError:
                return ('stale', None)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(worker, (0, 1)))

    def test_concurrent_retention_accepts_one_new_revision(self):
        expected = s.token(self.program)
        results = self.concurrent(lambda index: s.retain(self.program.pk, user=self.user, expected=expected,
            request_key=uuid4(), reason='Synthetic concurrent request'))
        self.assertEqual(sorted(item[0] for item in results), ['ok', 'stale'])
        self.assertEqual(Run.objects.count(), 1)

    def test_concurrent_identical_retry_returns_one_record(self):
        expected, key = s.token(self.program), uuid4()
        results = self.concurrent(lambda index: s.retain(self.program.pk, user=self.user, expected=expected,
            request_key=key, reason='Synthetic identical request'))
        self.assertEqual(results[0], results[1]); self.assertEqual(results[0][0], 'ok')
        self.assertEqual(Run.objects.count(), 1)

    def test_concurrent_reviews_accept_one_version(self):
        run = self.retain(); expected = s.review_token(run)
        results = self.concurrent(lambda index: s.review(run.pk, user=self.user, expected=expected,
            finding='REVIEWED', reason='Synthetic concurrent review'))
        self.assertEqual(sorted(item[0] for item in results), ['ok', 'stale'])
        self.assertEqual(Review.objects.count(), 1)


from ewaf.operational_testsupport import OperationalHelpers


class LegacyPreviewIsolationTests(OperationalHelpers, TransactionTestCase):
    def test_preview_retention_review_and_export_do_not_invalidate_operational_run(self):
        require_disposable()
        self.setup_operational()
        self.lock_policy()
        original_run = self.calculate()
        decision = self.choose(original_run)
        from ewaf import operational_services as legacy
        source_token = legacy.context(self.program.pk, user=self.officer)
        original_payload, original_decision = original_run.payload(), decision.payload()
        original_logs = list(ProgramLog.objects.filter(program=self.program).order_by('pk').values())
        original_publication = legacy.publication_snapshot(self.program)
        preview = s.retain(self.program.pk, user=self.officer, expected=s.token(self.program),
            request_key=uuid4(), reason='Independent synthetic method review.')
        s.review(preview.pk, user=self.officer, expected=s.review_token(preview), finding='REVIEWED',
                 reason='Synthetic review is not a new source assessment.')
        s.export(preview.pk, user=self.officer)
        self.assertEqual(legacy.context(self.program.pk, user=self.officer), source_token)
        with legacy.fence(self.program.pk, self.officer) as (actor, program, applications):
            self.assertEqual(legacy._current(program, applications, actor, original_run.pk).pk, original_run.pk)
        original_run.refresh_from_db(); decision.refresh_from_db()
        self.assertEqual(original_run.payload(), original_payload)
        self.assertEqual(decision.payload(), original_decision)
        self.assertEqual(list(ProgramLog.objects.filter(program=self.program).order_by('pk').values()), original_logs)
        self.assertEqual(legacy.publication_snapshot(self.program), original_publication)
