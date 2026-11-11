"""Removed EWAF screens retain safe bookmarks, never writable form endpoints."""
from copy import deepcopy

from django.contrib.auth import get_user_model
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse

from programs.models import ProgramLog
from programs.tests import create_program
from . import test_automatic_member_inputs as fixtures
from .operational_models import OperationalConfiguration, OperationalDecision, OperationalRun
from .revised.live_models import DatasetInputReview, SharedDatasetPolicy


@override_settings(EWAF_DATASET_POLICY_ENABLED=True, EWAF_DATASET_SCORING_ENABLED=True,
    EWAF_VAULT_ENABLED=True, PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class RetiredScreensTests(TransactionTestCase):
    setUp = fixtures.AutomaticMemberInputsTests.setUp
    draft = fixtures.AutomaticMemberInputsTests.draft
    approve = fixtures.AutomaticMemberInputsTests.approve
    bind = fixtures.AutomaticMemberInputsTests.bind
    publish = fixtures.AutomaticMemberInputsTests.publish
    generate = fixtures.AutomaticMemberInputsTests.generate
    applicant = fixtures.AutomaticMemberInputsTests.applicant
    pool = fixtures.AutomaticMemberInputsTests.pool

    def urls(self, application):
        return [reverse('ewaf:dataset_inputs', args=[application.pk]),
            reverse('ewaf:dataset_policy_review', args=[self.configuration.dataset_policy_id]),
            reverse('ewaf:dataset_policies'),
            reverse('ewaf:operational_calculation_guide', args=[self.program.pk])]

    def counts(self):
        return [model.objects.count() for model in (DatasetInputReview, SharedDatasetPolicy,
            OperationalConfiguration, OperationalRun, OperationalDecision, ProgramLog)]

    def test_old_bookmarks_redirect_and_submissions_cannot_change_records(self):
        a, _ = self.pool()
        run = self.generate()
        retained = deepcopy(run.payload())
        counts = self.counts()
        workspace = reverse('ewaf:operational_workspace', args=[self.program.pk])
        targets = [workspace + '#readiness', reverse('ewaf:vault'), reverse('ewaf:vault'), workspace + '#results']
        for url, target in zip(self.urls(a), targets):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, target, fetch_redirect_response=False)
                self.assertIn('no-store', response['Cache-Control'])
                self.assertEqual(self.client.post(url, {'state': 'ACCEPTED', 'action': 'APPLY_SHARED'}).status_code, 405)
        guide = self.client.get(self.urls(a)[-1], {'run': run.pk})
        self.assertRedirects(guide, workspace + f'?run={run.pk}#results', fetch_redirect_response=False)
        self.assertEqual(self.counts(), counts)
        run.refresh_from_db()
        self.assertEqual(run.payload(), retained)

    def test_removed_input_form_is_also_retired_for_manual_policy_versions(self):
        from .revised.member_record_evidence import content_for_records
        self.content = content_for_records(self.document_content)
        self.publish()
        a = self.applicant('RETIRED-MANUAL')
        before = self.counts()
        url = self.urls(a)[0]
        self.assertRedirects(self.client.get(url),
            reverse('ewaf:operational_workspace', args=[self.program.pk]) + '#readiness', fetch_redirect_response=False)
        self.assertEqual(self.client.post(url, {'state': 'ACCEPTED'}).status_code, 405)
        self.assertEqual(self.counts(), before)

    def test_bookmarks_keep_permissions_and_program_scoping(self):
        a, _ = self.pool()
        run = self.generate()
        limited = Client()
        restricted = get_user_model().objects.create_user('SYNTHETIC-RETIRED-RESTRICTED', is_staff=True)
        limited.force_login(restricted)
        for url in self.urls(a):
            self.assertEqual(Client().get(url).status_code, 302)
            self.assertEqual(limited.get(url).status_code, 403)
        other = create_program(ewaf_applicable=True)
        self.assertEqual(self.client.get(reverse('ewaf:operational_calculation_guide', args=[other.pk]), {'run': run.pk}).status_code, 404)
        self.assertEqual(self.client.get(self.urls(a)[-1], {'run': 'invalid'}).status_code, 404)

    def test_active_screens_have_no_retired_links_and_cards_keep_recorded_values(self):
        self.pool()
        run = self.generate()
        before = self.counts()
        for url in (reverse('ewaf:operational_workspace', args=[self.program.pk]),
                    reverse('ewaf:operational_breakdown', args=[self.program.pk]), reverse('ewaf:vault')):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            for path in ('/dataset-inputs/', '/policies/dataset/', '/calculation-guide/'):
                self.assertNotContains(response, path)
        workspace = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
        self.assertContains(workspace, 'data-input-state="ready"')
        self.assertContains(workspace, 'Member record inputs')
        cards = workspace.content.decode().split('id="readiness"', 1)[1].split('</aside>', 1)[0]
        self.assertIn('Recorded No', cards)
        self.assertNotIn('Verified No', cards)
        self.assertNotContains(workspace, 'Review ranking inputs')
        self.assertEqual(self.counts(), before)
        run.refresh_from_db()
        run.clean()
