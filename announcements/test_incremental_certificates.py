"""Republishing 3 -> 4 selections must deliver only the new certificate."""
from unittest.mock import patch

from django.core import mail
from django.db import models
from django.test import TestCase, override_settings
from ewaf.operational_testsupport import OperationalHelpers

from members.tests import create_member
from programs.tests import create_program
from .certificate_delivery import deliver_certificate, retry_certificates
from .certificate_mail import DeliveryFailure
from .certificate_models import SelectionCertificateEmail as Email
from . import test_gmail_certificates as gmail_fixtures
from . import test_certificate_delivery as certificate_fixtures


@override_settings(CERTIFICATE_EMAIL_PROVIDER='gmail', CERTIFICATE_EMAIL_BACKGROUND=False,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class IncrementalCertificateTests(OperationalHelpers, TestCase):
    publish = certificate_fixtures.CertificateDeliveryTests.publish

    def setUp(self):
        with patch('ewaf.evidence_testsupport.create_program',
                side_effect=lambda **values: create_program(**(values | {'slots': 5}))):
            gmail_fixtures.GmailCertificateTests.setUp(self)

    def add_selected(self, number):
        # New selections use the retained EWAF run/decision services, not the
        # retired non-EWAF decision route. Input evidence predates the cutoff.
        def member_fixture(code):
            member = create_member(code)
            member.full_name, member.email = f'Synthetic Recipient {number}', self.member.email
            member.save()
            return member
        # Shallow-copy a plain fixture object, not Django's running TestCase
        # (whose serialization includes the current test result and callbacks).
        fixture = OperationalHelpers()
        fixture.__dict__.update(self.__dict__)
        with patch('django.utils.timezone.now', return_value=self.fixture_time), \
                patch('members.tests.create_member', side_effect=member_fixture):
            helper = fixture.add_four_ready_applicant(f'CERT-INCREMENT-{number}', income=str(number * 10))
        self.choose(self.calculate(), application_id=helper.application.pk)
        return helper.application

    def deliver(self):
        for job in Email.objects.filter(state='queued'):
            deliver_certificate(job.pk)

    def test_three_then_four_selected_only_new_member_gets_email(self):
        self.add_selected(2)
        self.add_selected(3)
        self.publish()
        self.deliver()
        self.assertEqual(len(mail.outbox), 3)
        original = list(Email.objects.order_by('pk').values())
        newcomer = self.add_selected(4)
        self.publish()
        self.deliver()
        self.assertEqual(len(mail.outbox), 4)
        self.assertEqual(Email.objects.count(), 4)
        self.assertEqual(list(Email.objects.exclude(application=newcomer).order_by('pk').values()), original)
        self.assertTrue(all(job.attempt_count == 1 for job in Email.objects.all()))
        self.publish()
        self.deliver()
        self.assertEqual(retry_certificates(self.program.pk, user=self.admin), 0)
        self.assertEqual(len(mail.outbox), 4)
        self.assertEqual(len({message.extra_headers['Message-ID'] for message in mail.outbox}), 4)

    def test_republish_requeues_known_failure_but_keeps_original_attachment(self):
        self.publish()
        job = Email.objects.get()
        with patch('announcements.certificate_delivery.send_certificate',
                side_effect=DeliveryFailure('gmail_connection')):
            self.assertFalse(deliver_certificate(job.pk))
        original = (job.pk, job.revision_id, bytes(job.document), job.recipient)
        self.publish()
        job.refresh_from_db()
        self.assertEqual(job.state, 'queued')
        self.assertEqual((job.pk, job.revision_id, bytes(job.document), job.recipient), original)
        self.deliver()
        self.assertEqual(len(mail.outbox), 1)

    def test_republish_does_not_repeat_uncertain_gmail_delivery(self):
        self.publish()
        job = Email.objects.get()
        with patch('announcements.certificate_delivery.send_certificate',
                side_effect=DeliveryFailure('gmail_uncertain', uncertain=True)) as send:
            self.assertFalse(deliver_certificate(job.pk))
            self.publish()
            self.deliver()
            self.assertEqual(retry_certificates(self.program.pk, user=self.admin), 0)
        self.assertEqual(send.call_count, 1)
        job.refresh_from_db()
        self.assertEqual(job.state, 'uncertain')

    def test_retained_acceptance_or_attempt_prevents_stale_queue_resend(self):
        self.publish()
        job = Email.objects.get()
        self.assertTrue(deliver_certificate(job.pk))
        for clear_accepted in (False, True):
            changes = {'state': 'queued'}
            if clear_accepted:
                changes['accepted_at'] = None
            models.QuerySet.update(Email.objects.filter(pk=job.pk), **changes)
            self.assertFalse(deliver_certificate(job.pk))
            self.publish()
            self.deliver()
            self.assertEqual(retry_certificates(self.program.pk, user=self.admin), 0)
        self.assertEqual(len(mail.outbox), 1)
