"""Only an exact published selection permits recording a new receipt."""
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import close_old_connections, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from announcements.models import Announcement, ProgramResultRevision
from announcements.release_publication import MESSAGE
from announcements.results import results_current
from announcements.testsupport import publish_selection
from members.tests import create_member
from programs.testsupport import application_fixture
from programs.tests import create_program
from . import services, tests as fixtures
from .models import AssistanceRelease


class PublishedReceiptTests(TestCase):
    def setUp(self):
        with patch('assistance.tests.create_program',
                side_effect=lambda **values: create_program(**(values | {'slots': 4}))):
            fixtures.AssistanceTests.setUp(self)
    review = fixtures.AssistanceTests.review
    approve = fixtures.AssistanceTests.approve

    def receipt(self, app=None):
        app = app or self.application
        app.refresh_from_db()
        return services.record_actual_receipt(app.pk, user=self.admin,
            data={'version': app.version, 'program_version': self.program.version})

    def test_selected_but_unpublished_blocks_button_post_and_direct_release(self):
        self.approve(publish=False)
        response = self.client.get(reverse('assistance:program_releases', args=[self.program.pk]))
        self.assertContains(response, 'Publish this selected member in Announcements first.')
        self.assertNotContains(response, 'class="receipt-action-form"')
        with self.assertRaisesMessage(ValidationError, MESSAGE):
            self.receipt()
        with self.assertRaisesMessage(ValidationError, MESSAGE):
            services.record_release(self.application.pk, user=self.admin, data=fixtures.release_data(self.application))
        response = self.client.post(reverse('assistance:release', args=[self.application.pk]),
            {'version': self.application.version, 'program_version': self.program.version}, follow=True)
        self.assertContains(response, MESSAGE)
        self.assertFalse(AssistanceRelease.objects.exists())

    def test_new_selection_waits_but_previously_published_member_can_receive(self):
        self.approve()
        first = Announcement.objects.get(program=self.program)
        added = application_fixture(self.program, create_member('PUBLISH-LATER'))
        services.review_eligibility(added.pk, user=self.admin, data=fixtures.review_data(added))
        services.decide_assistance(added.pk, user=self.admin, data=fixtures.decision_data(added))
        self.assertFalse(results_current(first))
        with self.assertRaisesMessage(ValidationError, MESSAGE):
            self.receipt(added)
        receipt = self.receipt()
        self.assertEqual(receipt.approval_snapshot['result_publication']['revision'], first.result_revision_id)
        second = publish_selection(self.program, self.admin)
        receipt2 = self.receipt(added)
        self.assertEqual(receipt2.approval_snapshot['result_publication']['revision'], second.result_revision_id)
        self.assertEqual(AssistanceRelease.objects.count(), 2)
        with self.assertRaises(ValidationError):
            self.receipt()

    def test_draft_withdrawn_future_unrelated_and_missing_audit_do_not_authorize_receipt(self):
        self.approve()
        item = Announcement.objects.get(program=self.program)
        for changes in ({'status': 'draft'}, {'status': 'archived'}, {'status': 'deleted'},
                        {'published_at': timezone.now() + timedelta(days=1)}):
            with self.subTest(changes=changes), transaction.atomic():
                Announcement.objects.filter(pk=item.pk).update(**changes)
                with self.assertRaisesMessage(ValidationError, MESSAGE):
                    self.receipt()
                transaction.set_rollback(True)
        with transaction.atomic():
            item.events.filter(action='results_published').delete()
            with self.assertRaisesMessage(ValidationError, MESSAGE):
                self.receipt()
            transaction.set_rollback(True)
        original = item.result_revision.public_payload
        for payload in ({**original, 'rows': []}, {**original, 'kind': 'assistance_recipients'},
                        {**original, 'schema': 1}, {**original, 'selection_ready': False}):
            with self.subTest(payload=payload), transaction.atomic():
                ProgramResultRevision.objects.filter(pk=item.result_revision_id).update(public_payload=payload)
                with self.assertRaisesMessage(ValidationError, MESSAGE):
                    self.receipt()
                transaction.set_rollback(True)

    def test_publication_and_release_audit_rollback_preserve_records(self):
        self.approve()
        with patch('assistance.services.record_log', side_effect=ValidationError('Synthetic audit failure')):
            with self.assertRaisesMessage(ValidationError, 'Synthetic audit failure'):
                self.receipt()
        self.assertFalse(AssistanceRelease.objects.exists())
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'SELECTED')


class PublicationReceiptConcurrencyTests(TransactionTestCase):
    setUp = fixtures.AssistanceConcurrencyTests.setUp

    def test_withdrawal_waits_for_a_receipt_that_locked_published_selection(self):
        from announcements import release_publication
        from announcements.services import change_publication
        from programs.testsupport import close_non_ewaf_program
        close_non_ewaf_program(self.program, self.admin)
        services.decide_assistance(self.application.pk, user=self.admin, data=fixtures.decision_data(self.application))
        item = publish_selection(self.program, self.admin)
        self.application.refresh_from_db()
        data = {'version': self.application.version, 'program_version': self.program.version}
        locked, proceed, withdrawing, withdrawn = Event(), Event(), Event(), Event()
        original = release_publication.published_selection

        def hold_publication(*args, **kwargs):
            result = original(*args, **kwargs)
            locked.set()
            if not proceed.wait(10):
                raise RuntimeError('Synthetic publication lock timeout')
            return result

        def record():
            close_old_connections()
            try:
                return services.record_actual_receipt(self.application.pk, user=self.admin, data=data)
            finally:
                close_old_connections()

        def withdraw():
            close_old_connections()
            try:
                withdrawing.set()
                result = change_publication(item.pk, user=self.admin, version=item.version, action='archived')
                withdrawn.set()
                return result
            finally:
                close_old_connections()

        with patch.object(release_publication, 'published_selection', side_effect=hold_publication), ThreadPoolExecutor(2) as pool:
            receipt = pool.submit(record)
            try:
                self.assertTrue(locked.wait(10))
                withdrawal = pool.submit(withdraw)
                self.assertTrue(withdrawing.wait(10))
                self.assertFalse(withdrawn.wait(.2))
            finally:
                proceed.set()
            recorded = receipt.result(timeout=15)
            self.assertEqual(withdrawal.result(timeout=15).status, 'archived')
        self.assertEqual(recorded.approval_snapshot['result_publication']['revision'], item.result_revision_id)
        self.assertEqual(AssistanceRelease.objects.count(), 1)
