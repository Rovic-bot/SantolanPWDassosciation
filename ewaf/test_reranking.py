"""Actual twelve-member workflow: later delivery -> approve weights -> rerank."""
from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path
import subprocess
from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.db import models, transaction
from django.test import override_settings
from django.urls import reverse

from assistance.models import AssistanceRelease
from assistance.services import record_release, void_release
from assistance.tests import release_data
from programs.models import ProgramApplication
from . import test_current_weights as shared, test_synthetic_twelve as fixture
from . import operational_services as service
from .operational_models import OperationalRun, OperationalDecision
from .revised.live_models import DatasetInputReview


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True,
    PDAO_ENFORCEMENT_ENABLED=True, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RerankingAfterDeliveryTests(StaticLiveServerTestCase):
    for _name in ('setUp', 'observe', 'handoff_form', 'register_members', 'program', 'publish',
                  'apply', 'history', 'save_weights', 'bind', 'findings', 'accept', 'generate',
                  'build', 'preview', 'approve', 'assert_scores'):
        locals()[_name] = getattr(shared.CurrentWeightTests, _name)

    def deliver(self, run, label='T02'):
        app = self.apps[label]
        service.record_decision(self.target.pk, user=self.user, run_id=run.pk,
            application_id=app.pk, expected_revision=0, outcome='SELECTED',
            reason='Synthetic reviewed selection before confirmed delivery.')
        return record_release(app.pk, user=self.user, data=release_data(app))

    def second_program(self):
        with patch('django.utils.timezone.now', return_value=fixture.BASE):
            self.target = self.program('SYNTHETIC second cutoff pool', ewaf=True,
                opens=fixture.BASE + timedelta(hours=1), closes=fixture.BASE + timedelta(days=1))
            self.bind()
            self.publish(self.target)
        self.apps = {}
        with patch('django.utils.timezone.now', return_value=fixture.BASE + timedelta(hours=2)):
            for label, member in self.members.items():
                self.apps[label] = self.apply(self.target, member)
        for label in self.members:
            self.accept(label)

    def test_browser_reranks_existing_pools_after_delivery_and_preserves_decisions(self):
        from announcements.generation import generation_preview, generate_results
        from announcements.models import Announcement
        self.build('balanced')
        first, first_apps = self.target, self.apps
        self.second_program()
        second, second_apps = self.target, self.apps
        # Reproduce retained calculations made before this additive contract.
        capture = service.capture
        def old_capture(*args, **kwargs):
            snapshot = capture(*args, **kwargs)
            snapshot.pop('assessment_source_contract', None)
            return snapshot
        frozen = []
        with patch.object(service, 'capture', side_effect=old_capture):
            for program in (first, second):
                self.target = program
                run = self.generate()
                frozen.append((run, deepcopy(run.payload())))
        self.target, self.apps = first, first_apps
        receipt = self.deliver(frozen[0][0])
        before = {'receipts': list(AssistanceRelease.objects.order_by('pk').values()),
            'decisions': list(OperationalDecision.objects.order_by('pk').values()),
            'reviews': list(DatasetInputReview.objects.order_by('pk').values())}
        for program in (first, second):
            page = self.client.get(reverse('ewaf:operational_workspace', args=[program.pk]))
            self.assertTrue(page.context['ready'], page.context['problems'])
            self.assertEqual(page.context['ready_count'], 12)
        browser = subprocess.run(['node', str(Path(settings.BASE_DIR) / 'scripts/ewaf_reranking_browser.cjs')],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(self.output),
                'QA_PROGRAMS': json.dumps([str(first.pk), str(second.pk)]),
                'QA_USERNAME': self.user.username, 'QA_PASSWORD': 'synthetic-only'},
            capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(browser.returncode, 0, browser.stdout + browser.stderr)
        print(browser.stdout)
        for program, apps in ((first, first_apps), (second, second_apps)):
            run = OperationalRun.objects.filter(program=program).first()
            self.assert_scores(run, 'hm', apps)
            self.assertEqual(run.snapshot['eligible'][str(apps['T02'].pk)]['inputs']['PA']['value'], '3')
            self.assertEqual(len(run.calculations), 12)
            manifest = next(row for row in run.snapshot['manifest'] if row['application'] == str(apps['T02'].pk))
            self.assertEqual(manifest['source']['pa']['count'], 3)
            self.assertEqual(manifest['current_source']['pa']['count'], 4)
            self.assertEqual(manifest['post_cutoff_receipts'][0]['release'], str(receipt.pk))
        self.assertEqual(before['receipts'], list(AssistanceRelease.objects.order_by('pk').values()))
        self.assertEqual(before['decisions'], list(OperationalDecision.objects.order_by('pk').values()))
        self.assertEqual(before['reviews'], list(DatasetInputReview.objects.order_by('pk').values()))
        self.assertEqual(Announcement.objects.count(), 0)
        for old, payload in frozen:
            old.refresh_from_db()
            self.assertEqual(old.payload(), payload)
            old.clean()
        run = OperationalRun.objects.filter(program=first).first()
        with self.assertRaisesMessage(ValidationError, 'already recorded'):
            service.record_decision(first.pk, user=self.user, run_id=run.pk,
                application_id=first_apps['T02'].pk, expected_revision=1,
                outcome='SELECTED', reason='Synthetic duplicate must be rejected.')
        with self.assertRaises(ValidationError):
            record_release(first_apps['T02'].pk, user=self.user, data=release_data(first_apps['T02']))
        self.deliver(run, 'T07')
        # An additional delivery does not stale the same cutoff ranking.
        page = self.client.get(reverse('ewaf:operational_workspace', args=[first.pk]))
        self.assertTrue(page.context['result']['active'], page.context['result']['problems'])
        self.assertContains(page, 'Assistance received')
        plan = generation_preview(first.pk, user=self.user)
        self.assertEqual(len(plan['payload']['rows']), 2)
        published = generate_results(first.pk, user=self.user, expected=plan['expected'], version=0)
        self.assertEqual(len(published.result_revision.public_payload['rows']), 2)
        self.assertEqual(AssistanceRelease.objects.count(), 29)

    def test_other_source_changes_and_voids_still_block(self):
        self.build('balanced')
        original = self.generate()
        receipt = self.deliver(original)
        self.approve('ses')
        rerun = self.generate()
        self.assert_scores(rerun, 'ses', self.apps)
        app = self.apps['T02']
        # Raw updates below inject corruption only into the disposable test DB.
        changes = (
            lambda: models.QuerySet.update(ProgramApplication.objects.filter(pk=app.pk), version=99),
            lambda: models.QuerySet.update(AssistanceRelease.objects.filter(pk=receipt.pk),
                released_on=self.configuration.assessment_cutoff.date()),
            lambda: models.QuerySet.update(AssistanceRelease.objects.filter(pk=receipt.pk), approval_snapshot={}),
            lambda: models.QuerySet.update(AssistanceRelease.objects.filter(pk=self.releases[0].pk),
                released_on=fixture.NOW.date()),
        )
        for change in changes:
            with self.subTest(change=change), transaction.atomic():
                change()
                with self.assertRaises(ValidationError):
                    service.context(self.target.pk, user=self.user)
                transaction.set_rollback(True)
        with transaction.atomic():
            app.refresh_from_db()
            void_release(app.pk, receipt.pk, user=self.user,
                data={'version': app.version, 'notes': 'Synthetic actual void requires renewed review.', 'confirm': True})
            with self.assertRaises(ValidationError):
                service.context(self.target.pk, user=self.user)
            transaction.set_rollback(True)
        with transaction.atomic():
            other = self.apps['T01']
            models.QuerySet.update(ProgramApplication.objects.filter(pk=other.pk), status='COMPLETED')
            with self.assertRaises(ValidationError):
                service.context(self.target.pk, user=self.user)
            transaction.set_rollback(True)
        self.assertEqual(self.generate().calculations, rerun.calculations)

    def test_reranking_requires_current_authority_source_token_and_atomic_audit(self):
        self.build('balanced')
        self.deliver(self.generate())
        old = service.context(self.target.pk, user=self.user)
        self.approve('ses')
        count = OperationalRun.objects.count()
        with self.assertRaisesMessage(ValidationError, 'sources or predecessor changed'):
            service.generate(self.target.pk, user=self.user, expected=old,
                reason='Synthetic stale approval token', request_key=uuid4())
        staff = get_user_model().objects.create_user('synthetic-no-ranking-permission', is_staff=True)
        with self.assertRaises(PermissionDenied):
            service.context(self.target.pk, user=staff)
        with patch('ewaf.evidence_services.ProgramLog.objects.create', side_effect=ValidationError('audit unavailable')):
            with self.assertRaises(ValidationError):
                self.generate()
        self.assertEqual(OperationalRun.objects.count(), count)
        self.assert_scores(self.generate(), 'ses', self.apps)
