from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from members.models import Member, MemberEvent
from members.registration_form import MemberRegistrationForm
from members.profile import profile_snapshot
from .models import ProgramApplication
from .services import submit_application
from .decision_email import recipient_for
from . import test_application_workflow as fixtures


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class ApplicationEmailTests(TestCase):
    setUp = fixtures.ConfirmedApplicationTests.setUp
    identity = fixtures.ConfirmedApplicationTests.identity
    grant = fixtures.ConfirmedApplicationTests.grant
    data = fixtures.ConfirmedApplicationTests.data
    submit = fixtures.ConfirmedApplicationTests.submit

    def test_blank_member_email_is_filled_audited_and_visible_in_editing(self):
        Member.objects.filter(pk=self.member.pk).update(email='')
        self.member.refresh_from_db()
        before = profile_snapshot(self.member)
        intake = self.member.application.email
        version = self.member.version
        application = self.submit(applicant_email='new-contact@example.invalid')
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, 'new-contact@example.invalid')
        self.assertEqual(self.member.version, version + 1)
        self.assertEqual(application.source_snapshot['member_version'], self.member.version)
        self.member.application.refresh_from_db()
        self.assertEqual(self.member.application.email, intake)
        after = profile_snapshot(self.member)
        self.assertEqual({key for key in before if before[key] != after[key]}, {'email'})
        event = MemberEvent.objects.get(member=self.member, action='email_added_from_application')
        self.assertIsNone(event.actor)
        self.assertIn(application.public_reference, event.notes)
        self.assertEqual(event.changes['email'], {'before': '', 'after': self.member.email})
        self.assertEqual(MemberRegistrationForm(instance=self.member)['email'].value(), self.member.email)
        self.client.force_login(self.admin)
        for route in ('members:detail', 'members:edit'):
            response = self.client.get(reverse(route, args=[self.member.pk]))
            self.assertContains(response, self.member.email)
        self.assertEqual(recipient_for(application), (self.member.email, 'application', ''))

    def test_different_application_email_never_overwrites_a_saved_member_email(self):
        Member.objects.filter(pk=self.member.pk).update(email='saved@example.invalid')
        before = Member.objects.values().get(pk=self.member.pk)
        application = self.submit(applicant_email='program-only@example.invalid')
        self.assertEqual(Member.objects.values().get(pk=self.member.pk), before)
        self.assertFalse(MemberEvent.objects.filter(action='email_added_from_application').exists())
        self.assertEqual(recipient_for(application), ('program-only@example.invalid', 'application', ''))

    def test_missing_or_invalid_email_is_rejected_with_no_member_changes(self):
        Member.objects.filter(pk=self.member.pk).update(email='')
        before = Member.objects.values().get(pk=self.member.pk)
        for email in ('', '  ', 'invalid'):
            with self.subTest(email=email), self.assertRaises(ValidationError):
                self.submit(applicant_email=email)
        self.assertFalse(ProgramApplication.objects.exists())
        self.assertEqual(Member.objects.values().get(pk=self.member.pk), before)
        self.assertFalse(MemberEvent.objects.exists())
        self.client.post(self.verify_url, self.identity())
        response = self.client.get(self.apply_url)
        self.assertTrue(response.context['form'].fields['applicant_email'].required)
        response = self.client.post(self.apply_url, self.data(applicant_email=''))
        self.assertContains(response, 'This field is required.')

    def test_audit_failure_rolls_back_email_and_submission(self):
        Member.objects.filter(pk=self.member.pk).update(email='')
        before = Member.objects.values().get(pk=self.member.pk)
        with patch('members.services.MemberEvent.objects.create', side_effect=RuntimeError('Synthetic audit failure')):
            with self.assertRaises(RuntimeError):
                self.submit()
        self.assertEqual(Member.objects.values().get(pk=self.member.pk), before)
        self.assertFalse(ProgramApplication.objects.exists())

    def test_repeat_submission_preserves_first_email_and_audit(self):
        Member.objects.filter(pk=self.member.pk).update(email='')
        self.submit(applicant_email='first@example.invalid')
        self.member.refresh_from_db()
        self.submit(applicant_email='later@example.invalid')
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, 'first@example.invalid')
        self.assertEqual(MemberEvent.objects.filter(action='email_added_from_application').count(), 1)
        self.assertEqual(ProgramApplication.objects.count(), 1)

    def test_staff_update_after_verification_cannot_be_overwritten(self):
        Member.objects.filter(pk=self.member.pk).update(email='')
        grant = self.grant()
        Member.objects.filter(pk=self.member.pk).update(email='staff-saved@example.invalid', version=self.member.version + 1)
        with self.assertRaises(ValidationError):
            submit_application(self.program.pk, grant=grant, data=self.data(), files=MultiValueDict())
        self.member.refresh_from_db()
        self.assertEqual(self.member.email, 'staff-saved@example.invalid')
        self.assertFalse(ProgramApplication.objects.exists())
