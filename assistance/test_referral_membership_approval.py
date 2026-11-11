"""The desk accepts both retained, audited Association approval workflows."""
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from members.models import Member
from membership.test_registration_decisions import DecisionHelpers
from . import referral_services as service
from .referral_models import ReferralGrant
from .test_referrals import Fixtures


@override_settings(REFERRAL_ENABLED=True,
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AssociationApprovalReferralTests(DecisionHelpers, Fixtures, TestCase):
    def setUp(self):
        Fixtures.setUp(self)
        self.setup_decisions()
        intake = self.make(data={'contact_number': '09170000001'})
        self.intake = self.decide(intake, data=DecisionHelpers.data(
            self, intake, contact_number='09170000001'))
        self.member = Member.objects.select_related('application').get(
            application=self.intake.membership_application)
        self.verification = dict(control_number=self.member.control_number,
                                 full_name=self.member.full_name)

    def test_new_association_approval_can_verify_and_submit_without_prpwd(self):
        application = self.member.application
        self.assertIsNone(application.prpwd_verified)
        self.assertIsNone(application.prpwd_verified_at)
        response = self.client.post(reverse('assistance:referral_verify'), {
            'control_number': ' ' + self.member.control_number + ' ',
            'full_name': '  ' + self.member.full_name.upper() + '  ',
        })
        self.assertRedirects(response, reverse('assistance:referral_apply'))
        ticket = self.submit()
        self.assertEqual(ticket.member_id, self.member.pk)
        application.refresh_from_db()
        self.assertIsNone(application.prpwd_verified)
        self.assertIsNone(application.prpwd_verified_at)

    def test_audited_approval_still_requires_exact_identity_and_active_membership(self):
        with self.assertRaises(ValidationError):
            self.verified(full_name='Wrong name')
        with self.assertRaises(ValidationError):
            self.verified(control_number='Wrong number')
        self.member.is_active = False
        self.member.save()
        with self.assertRaises(ValidationError):
            self.verified()
        self.assertFalse(ReferralGrant.objects.exists())

    def test_changed_approval_invalidates_existing_grant(self):
        token = self.verified()
        application = self.member.application
        application.status = 'pending'
        application.save()
        with self.assertRaises(ValidationError):
            service.submit_ticket(token.pk, self.binding, data=self.data)
        with self.assertRaises(ValidationError):
            self.verified()

    def test_decision_from_unrelated_actor_does_not_replace_missing_prpwd(self):
        application = self.member.application
        application.decided_by = self.admin
        application.save()
        with self.assertRaises(ValidationError):
            self.verified()

    def test_email_settings_link_permission_and_development_delivery_notice(self):
        settings_url = reverse('assistance:referral_email_settings')
        self.client.force_login(self.viewer)
        self.assertNotContains(self.client.get(reverse('assistance:referral_inbox')), settings_url)
        self.assertEqual(self.client.get(settings_url).status_code, 403)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse('assistance:referral_inbox')), settings_url)
        self.assertContains(self.client.get(settings_url), 'Test mail capture is active.')
