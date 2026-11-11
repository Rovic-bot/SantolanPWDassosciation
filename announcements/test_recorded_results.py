from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from assistance.models import AssistanceRelease
from assistance.services import record_release
from assistance.tests import release_data
from members.tests import create_member
from membership.tests import grant
from programs.models import ProgramApplication
from programs.testsupport import application_fixture
from ewaf.operational_testsupport import OperationalHelpers
from ewaf.operational_models import OperationalDecision
from .admin_results import admin_projection
from .generation import PERMISSIONS, generation_preview
from .models import Announcement, AnnouncementEvent, ProgramResultRevision
from .recorded_results import collect_recorded_results, recorded_preview, publish_recorded_results
from .results import prepare_results, results_current
from .services import change_publication
from . import test_results as legacy


class RecordedResultsTests(TestCase):
    setUp = legacy.ProgramResultTests.setUp

    def test_popup_publication_returns_refreshed_preview_and_rejects_replay(self):
        url = reverse('announcements:prepare_results', args=[self.program.pk])
        plan = self.client.get(url).context['preview']
        data = {'action': 'PUBLISH_RECORDED_RESULTS', 'expected': plan['expected'], 'version': plan['version']}
        response = self.client.post(url, data, HTTP_X_ANNOUNCEMENT_DIALOG='1', follow=True)
        self.assertEqual(response.redirect_chain, [(url, 302)])
        self.assertContains(response, 'id="program-results-dialog"')
        self.assertContains(response, 'Program results published.')
        self.assertContains(response, 'Results published')
        item = Announcement.objects.get()
        self.assertEqual(item.status, 'published')
        self.assertNotEqual(response.context['preview']['expected'], plan['expected'])
        response = self.client.post(url, data, HTTP_X_ANNOUNCEMENT_DIALOG='1')
        self.assertContains(response, 'recorded results changed')
        self.assertContains(response, 'id="program-results-dialog"')
        self.assertEqual(item.result_revisions.count(), 1)

    def publish(self, plan=None, user=None):
        user = user or self.admin
        plan = plan or recorded_preview(self.program.pk, user=user)
        return publish_recorded_results(self.program.pk, user=user,
            expected=plan['expected'], version=plan['version'])

    def test_publish_pending_reviews_open_period_and_missing_policy_without_changing_records(self):
        pending = application_fixture(self.program, create_member('RECORD-PENDING'))
        self.program.registration_closes_at = timezone.now() + timezone.timedelta(days=1)
        self.program.policy_authorized_at = None
        self.program.save()
        before = list(ProgramApplication.objects.order_by('pk').values())
        with self.assertRaises(ValidationError):
            generation_preview(self.program.pk, user=self.admin)
        item = self.publish()
        self.assertEqual(item.status, 'published')
        self.assertTrue(results_current(item))
        self.assertEqual(list(ProgramApplication.objects.order_by('pk').values()), before)
        self.assertFalse(OperationalDecision.objects.exists())
        self.assertFalse(AssistanceRelease.objects.exists())
        self.assertEqual(len(item.result_revision.public_payload['applicants']), 2)
        self.assertEqual([row['reference'] for row in item.result_revision.public_payload['rows']],
                         [self.application.public_reference])
        self.assertIn('independently of review readiness', item.result_revision.reason)
        self.assertEqual(item.events.count(), 2)
        for route in ('announcements:detail', 'core:result_detail'):
            response = Client().get(reverse(route, args=[item.pk]))
            self.assertContains(response, pending.public_reference)
            self.assertContains(response, 'J*** D*** C***')
            self.assertNotContains(response, self.member.full_name)
            self.assertNotContains(response, pending.member.full_name)

    def test_full_names_in_admin_popup_current_revision_and_history_only(self):
        url = reverse('announcements:prepare_results', args=[self.program.pk])
        response = self.client.get(url)
        self.assertContains(response, self.member.full_name, count=2)
        self.assertNotContains(response, 'J*** D*** C***')
        self.assertContains(response, '<th scope="col">Applicant</th>')
        self.assertContains(response, '<th scope="col">Selected member</th>')
        self.assertFalse(Announcement.objects.exists())
        plan = response.context['preview']
        self.assertEqual(plan['payload']['rows'][0]['name'], 'J*** D*** C***')
        response = self.client.post(url, {'action': 'PUBLISH_RECORDED_RESULTS',
            'expected': plan['expected'], 'version': plan['version']})
        item = Announcement.objects.get()
        self.assertRedirects(response, reverse('announcements:manage_detail', args=[item.pk]))
        response = self.client.get(response.url)
        self.assertContains(response, self.member.full_name, count=4)
        self.assertNotContains(response, 'J*** D*** C***')
        item.result_revision.refresh_from_db()
        self.assertNotIn(self.member.full_name, str(item.result_revision.public_payload))
        # Even signed-in admins see the masked projection on public routes.
        self.assertNotContains(self.client.get(reverse('core:result_detail', args=[item.pk])), self.member.full_name)

    def test_legacy_history_resolves_only_unambiguous_names_without_mutating_payload(self):
        old = prepare_results(self.program.pk, user=self.admin, version=0, reason='Historical decision.')
        payload = deepcopy(old.result_revision.public_payload)
        result = admin_projection(self.program, payload, user=self.admin)
        self.assertEqual(result['rows'][0]['name'], self.member.full_name)
        other = application_fixture(self.program, create_member('RECORDED-COLLISION'))
        other.member.full_name = self.member.full_name
        other.member.save()
        ProgramApplication.objects.filter(pk=other.pk).update(
            public_reference='OLD-' + self.application.public_reference[-4:])
        result = admin_projection(self.program, payload, user=self.admin)
        self.assertEqual(result['rows'][0]['name'], 'Name unavailable in this historical snapshot')
        old.result_revision.refresh_from_db()
        self.assertEqual(payload, old.result_revision.public_payload)

    def test_changed_preview_rejected_and_ui_requires_another_explicit_click(self):
        plan = recorded_preview(self.program.pk, user=self.admin)
        self.member.full_name = 'Updated Member Name'
        self.member.save()
        url = reverse('announcements:prepare_results', args=[self.program.pk])
        response = self.client.post(url, {'action': 'PUBLISH_RECORDED_RESULTS',
            'expected': plan['expected'], 'version': plan['version']})
        self.assertContains(response, 'recorded results changed')
        self.assertFalse(Announcement.objects.exists())
        current = response.context['preview']
        self.assertNotEqual(current['expected'], plan['expected'])
        self.assertEqual(response.context['generation_form'].data['expected'], current['expected'])
        item = self.publish(current)
        with self.assertRaises(ValidationError):
            self.publish(current)
        self.assertEqual(item.result_revisions.count(), 1)

    def test_csrf_permission_revocation_and_private_name_access(self):
        user = get_user_model().objects.create_user('record_publisher', is_staff=True)
        grant(user, 'accounts.access_dashboard', *PERMISSIONS)
        plan = recorded_preview(self.program.pk, user=user)
        url = reverse('announcements:prepare_results', args=[self.program.pk])
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        self.assertEqual(client.post(url, {'action': 'PUBLISH_RECORDED_RESULTS',
            'expected': plan['expected'], 'version': 0}).status_code, 403)
        user.user_permissions.clear()
        with self.assertRaises(PermissionDenied):
            self.publish(plan, user=user)
        editor = get_user_model().objects.create_user('record_editor', is_staff=True)
        grant(editor, 'accounts.access_dashboard', 'announcements.view_announcement')
        self.client.force_login(editor)
        self.assertEqual(self.client.get(url).status_code, 403)
        with self.assertRaises(PermissionDenied):
            admin_projection(self.program, plan['payload'], user=editor)
        self.assertFalse(Announcement.objects.exists())

    def test_publisher_without_selection_permissions_can_publish_recorded_results(self):
        user = get_user_model().objects.create_user('only_record_publisher', is_staff=True)
        grant(user, 'accounts.access_dashboard', *PERMISSIONS)
        application_fixture(self.program, create_member('PUBLISHER-PENDING'))
        self.assertFalse(user.has_perm('assistance.decide_assistance'))
        self.assertEqual(self.publish(user=user).status, 'published')

    def test_audit_failure_rolls_back_publication_and_preserves_existing_revision(self):
        item = self.publish()
        before = deepcopy(Announcement.objects.values().get(pk=item.pk))
        with patch('announcements.results.record_event', side_effect=[None, RuntimeError('Audit failed')]):
            with self.assertRaises(RuntimeError):
                self.publish()
        self.assertEqual(Announcement.objects.values().get(pk=item.pk), before)
        self.assertEqual(ProgramResultRevision.objects.count(), 1)
        self.assertEqual(AnnouncementEvent.objects.count(), 2)

    def test_recorded_publication_does_not_recheck_readiness_but_withholds_changed_lists(self):
        item = self.publish()
        self.member.version += 1
        self.member.save()
        self.program.policy_authorized_at = None
        self.program.version += 1
        self.program.save()
        self.assertTrue(results_current(item))
        application_fixture(self.program, create_member('NEW-RECORDED-APPLICANT'))
        self.assertFalse(results_current(item))
        self.assertEqual(Client().get(reverse('core:result_detail', args=[item.pk])).status_code, 404)
        updated = self.publish()
        self.assertTrue(results_current(updated))
        self.assertEqual(updated.result_revisions.count(), 2)

    def test_confirmed_delivery_keeps_recorded_selection_visible(self):
        item = self.publish()
        record_release(self.application.pk, user=self.admin, data=release_data(self.application))
        self.assertTrue(results_current(item))

    def test_corrupt_payload_and_unsafe_reference_still_block_publication(self):
        item = self.publish()
        revision = item.result_revision
        ProgramResultRevision.objects.filter(pk=revision.pk).update(
            public_payload={**revision.public_payload, 'private_names': True})
        item.refresh_from_db()
        self.assertFalse(results_current(item))
        ProgramApplication.objects.filter(pk=self.application.pk).update(public_reference='!')
        with self.assertRaises(ValidationError):
            recorded_preview(self.program.pk, user=self.admin)

    def test_withdraw_archive_and_delete_retain_publication_controls(self):
        item = self.publish()
        for status in ('draft', 'archived', 'deleted'):
            item = change_publication(item.pk, user=self.admin, version=item.version, action=status)
            self.assertEqual(Client().get(reverse('core:result_detail', args=[item.pk])).status_code, 404)
            if status != 'deleted':
                item = self.publish()
        with self.assertRaises(ValidationError):
            self.publish()

    def test_draft_and_cancelled_program_results_are_available_for_explicit_publication(self):
        for status in ('draft', 'cancelled'):
            self.program.status = status
            self.program.save()
            response = self.client.get(reverse('announcements:manage_list'), {'status': status})
            self.assertContains(response, self.program.name)
            self.assertNotContains(response, 'Saved announcements')
            item = self.publish()
            self.assertTrue(results_current(item))


class RecordedEWAFResultsTests(OperationalHelpers, TransactionTestCase):
    def setUp(self):
        super().setUp()
        legacy.mock_pdf_conversion(self)

    def test_collecting_more_decisions_adds_only_the_required_audit_checks(self):
        self.setup_operational(additional=2)
        self.lock_policy()
        run = self.calculate()
        self.choose(run)
        with CaptureQueriesContext(connection) as first_queries:
            initial, _ = collect_recorded_results(self.program)
        self.assertEqual(len(initial['rows']), 1)

        # Include a revised decision so the predecessor integrity check is
        # exercised alongside applications added to the published selection.
        self.choose(run, expected_revision=1, outcome='NOT_SELECTED')
        for helper in self.helpers[1:]:
            self.choose(run, application_id=helper.application.pk, outcome='NOT_SELECTED')
        with CaptureQueriesContext(connection) as expanded_queries:
            updated, _ = collect_recorded_results(self.program)
        self.assertEqual(updated['rows'], [])
        self.assertEqual(len(updated['applicants']), 3)
        # Each additional artifact still gets its own fresh mandatory audit
        # validation; related application/predecessor reads must not also grow.
        self.assertEqual(len(expanded_queries) - len(first_queries), 2)

    def test_publish_after_ewaf_delivery_preserves_the_receipt_and_calculation(self):
        self.setup_operational()
        self.lock_policy()
        run = self.calculate()
        self.choose(run)
        from announcements.testsupport import publish_selection
        grant(self.officer, *PERMISSIONS)
        publish_selection(self.program, self.officer)
        receipt = record_release(self.application.pk, user=self.officer, data=release_data(self.application))
        before = AssistanceRelease.objects.values().get(pk=receipt.pk)
        frozen = deepcopy(run.payload())
        grant(self.officer, *PERMISSIONS)
        self.client.force_login(self.officer)
        url = reverse('announcements:prepare_results', args=[self.program.pk])
        response = self.client.get(url)
        self.assertContains(response, self.member.full_name)
        plan = response.context['preview']
        response = self.client.post(url, {'action': 'PUBLISH_RECORDED_RESULTS',
            'expected': plan['expected'], 'version': plan['version']})
        self.assertEqual(response.status_code, 302)
        item = Announcement.objects.get()
        self.assertTrue(results_current(item))
        self.assertEqual(len(item.result_revision.public_payload['rows']), 1)
        self.assertEqual(AssistanceRelease.objects.values().get(pk=receipt.pk), before)
        self.assertEqual(OperationalDecision.objects.count(), 1)
        run.refresh_from_db()
        self.assertEqual(run.payload(), frozen)
        self.assertNotContains(Client().get(reverse('core:result_detail', args=[item.pk])), self.member.full_name)

    def test_stale_ranking_and_deferred_decisions_do_not_block_or_change_recorded_results(self):
        self.setup_operational(additional=1)
        self.lock_policy()
        run = self.calculate()
        self.choose(run)
        self.choose(run, application_id=self.helpers[1].application.pk, outcome='DEFERRED')
        # A new run makes retained decisions belong to an earlier ranking.
        self.calculate()
        grant(self.officer, *PERMISSIONS)
        with self.assertRaises(ValidationError):
            generation_preview(self.program.pk, user=self.officer)
        before = list(OperationalDecision.objects.order_by('pk').values())
        frozen = deepcopy(run.payload())
        plan = recorded_preview(self.program.pk, user=self.officer)
        self.assertEqual(len(plan['payload']['rows']), 1)
        item = publish_recorded_results(self.program.pk, user=self.officer,
            expected=plan['expected'], version=plan['version'])
        self.assertTrue(results_current(item))
        self.assertEqual(list(OperationalDecision.objects.order_by('pk').values()), before)
        run.refresh_from_db()
        self.assertEqual(run.payload(), frozen)
        self.assertEqual(OperationalDecision.objects.filter(outcome='DEFERRED').count(), 1)
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_corrupted_recorded_decision_is_not_silently_published(self):
        self.setup_operational()
        self.lock_policy()
        run = self.calculate()
        decision = self.choose(run)
        grant(self.officer, *PERMISSIONS)
        # Simulate storage corruption only in the disposable test database;
        # ordinary ORM updates correctly reject edits to this append-only row.
        with connection.cursor() as cursor:
            cursor.execute('UPDATE ewaf_operationaldecision SET digest = %s WHERE id = %s',
                           ['0' * 64, decision.pk])
        with self.assertRaises(ValidationError):
            recorded_preview(self.program.pk, user=self.officer)
        self.assertFalse(Announcement.objects.exists())
