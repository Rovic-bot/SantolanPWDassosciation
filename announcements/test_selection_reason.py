"""Required public explanations without changing decisions or historical results."""
from copy import deepcopy
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from members.tests import create_member
from programs.tests import create_program
from programs.testsupport import application_fixture
from .generation import generate_results
from .models import Announcement, AnnouncementEvent, ProgramResultRevision
from .recorded_results import recorded_preview, publish_recorded_results
from .results import prepare_results, publish_results, results_current


REASON = 'Members meet the program criteria, and this assistance addresses their assessed support needs.'


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class SelectionReasonTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('selection-reason-admin')
        self.client.force_login(self.admin)
        self.program = create_program(ewaf_applicable=True, slots=10)
        self.application = application_fixture(self.program, create_member('SELECTION-REASON'))
        self.url = reverse('announcements:prepare_results', args=[self.program.pk])
        self.queue = patch('announcements.certificate_delivery.queue_certificates').start()
        self.addCleanup(patch.stopall)

    def data(self, reason=REASON):
        plan = recorded_preview(self.program.pk, user=self.admin)
        return {'version': plan['version'], 'expected': plan['expected'], 'selection_reason': reason}

    def publish(self, reason=REASON):
        return publish_recorded_results(self.program.pk, user=self.admin, **self.data(reason))

    def test_missing_blank_and_overlong_reason_rejected_without_writes(self):
        for reason in ('', ' \n\t ', 'x' * 2001, None):
            with self.subTest(reason=repr(reason)[:20]):
                with self.assertRaises(ValidationError):
                    self.publish(reason)
                response = self.client.post(self.url, {'action': 'PUBLISH_RECORDED_RESULTS',
                    **self.data(reason or '')})
                self.assertEqual(response.status_code, 200)
                self.assertIn('selection_reason', response.context['generation_form'].errors)
                self.assertContains(response, 'id="program-results-dialog"')
                self.assertFalse(Announcement.objects.exists())
                self.assertFalse(ProgramResultRevision.objects.exists())
                self.assertFalse(AnnouncementEvent.objects.exists())
        self.queue.assert_not_called()

    def test_http_publication_saves_public_explanation_and_masks_names(self):
        response = self.client.post(self.url, {'action': 'PUBLISH_RECORDED_RESULTS',
            **self.data('  ' + REASON + '\n')}, HTTP_X_ANNOUNCEMENT_DIALOG='1', follow=True)
        self.assertEqual(response.redirect_chain, [(self.url, 302)])
        self.assertContains(response, 'Program results published.')
        item = Announcement.objects.get()
        self.assertEqual(item.result_revision.public_payload['selection_reason'], REASON)
        self.assertTrue(results_current(item))
        self.assertEqual(response.context['generation_form']['selection_reason'].value(), REASON)
        self.queue.assert_called_once()
        for url in (reverse('core:announcements') + '?category=results',
                    reverse('announcements:detail', args=[item.pk]) + '?popup=1'):
            page = Client().get(url)
            self.assertContains(page, 'Why these members were selected')
            self.assertContains(page, REASON)
            self.assertNotContains(page, self.application.member.full_name)
            self.assertNotContains(page, item.result_revision.reason)

    def test_reason_is_escaped_on_public_results(self):
        item = self.publish('<script>alert("unsafe")</script>')
        page = Client().get(reverse('core:announcements') + '?category=results')
        self.assertContains(page, '&lt;script&gt;')
        self.assertNotContains(page, '<script>alert(')
        self.assertTrue(results_current(item))

    def test_stale_preview_keeps_reason_and_requires_explicit_new_submission(self):
        old = self.data()
        application_fixture(self.program, create_member('SELECTION-REASON-LATER'))
        response = self.client.post(self.url, {'action': 'PUBLISH_RECORDED_RESULTS', **old})
        self.assertContains(response, 'recorded results changed')
        form = response.context['generation_form']
        self.assertEqual(form['selection_reason'].value(), REASON)
        self.assertNotEqual(form['expected'].value(), old['expected'])
        self.assertFalse(Announcement.objects.exists())
        self.publish()
        with self.assertRaises(ValidationError):
            publish_recorded_results(self.program.pk, user=self.admin, **old)
        self.assertEqual(ProgramResultRevision.objects.count(), 1)

    def test_direct_and_legacy_generation_paths_require_reason(self):
        item = prepare_results(self.program.pk, user=self.admin, version=0, recorded=True,
            reason='Private draft justification is not a public selection reason.')
        with self.assertRaisesMessage(ValidationError, 'Explain why'):
            publish_results(item.pk, user=self.admin, version=item.version)
        with self.assertRaisesMessage(ValidationError, 'Explain why'):
            generate_results(self.program.pk, user=self.admin, expected='unused', version=item.version)
        item.refresh_from_db()
        self.assertEqual(item.status, 'draft')
        self.assertEqual(item.events.count(), 1)
        self.queue.assert_not_called()

    def test_legacy_publication_keeps_its_original_payload_and_digest(self):
        item = prepare_results(self.program.pk, user=self.admin, version=0, recorded=True,
            reason='Legacy synthetic publication.')
        original = deepcopy(item.result_revision.public_payload)
        # Simulate a publication made before explanations were required, only in
        # the disposable test DB. Do not invent reasons for historical records.
        Announcement.objects.filter(pk=item.pk).update(status='published', published_at=timezone.now())
        item.refresh_from_db()
        self.assertTrue(results_current(item))
        self.assertEqual(item.result_revision.public_payload, original)
        self.assertContains(Client().get(reverse('core:announcements') + '?category=results'), self.program.name)

    def test_tampered_reason_or_version_is_withheld(self):
        item = self.publish()
        revision = item.result_revision
        for change in ({'selection_reason': 'Changed without a revision'},
                       {'selection_reason_version': 99}, {'selection_reason_version': True},
                       {'selection_reason': ''}):
            ProgramResultRevision.objects.filter(pk=revision.pk).update(public_payload={**revision.public_payload, **change})
            item.refresh_from_db()
            self.assertFalse(results_current(item))

    def test_reason_changes_create_immutable_revisions_and_audit_failure_rolls_back(self):
        item = self.publish()
        first = item.result_revision
        original = deepcopy(first.public_payload)
        item = self.publish('Updated explanation after another review of the same selection.')
        first.refresh_from_db()
        self.assertEqual(first.public_payload, original)
        self.assertNotEqual(item.result_revision.source_digest, first.source_digest)
        self.assertTrue(results_current(item))
        before = Announcement.objects.values().get(pk=item.pk)
        self.queue.reset_mock()
        with patch('announcements.results.record_event', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.publish('A new reason that must roll back with the failed audit.')
        self.assertEqual(Announcement.objects.values().get(pk=item.pk), before)
        self.assertEqual(item.result_revisions.count(), 2)
        self.assertEqual(item.events.count(), 4)
        self.queue.assert_not_called()

    def test_csrf_and_publication_permissions_are_preserved(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post(self.url, {'action': 'PUBLISH_RECORDED_RESULTS', **self.data()}).status_code, 403)
        viewer = get_user_model().objects.create_user('reason-viewer', is_staff=True)
        with self.assertRaises(PermissionDenied):
            publish_recorded_results(self.program.pk, user=viewer, **self.data())
        self.assertFalse(Announcement.objects.exists())
        self.queue.assert_not_called()
