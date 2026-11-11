"""Manual PRPWD confirmation is distinct from merely opening the registry."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from members.models import Member
from .models import MembershipApplication, MembershipEvent, MembershipSettings
from .registration_models import RegistrationIntake
from .test_registration_decisions import DecisionHelpers
from .test_registration_intake import staff


class PrpwdRegistrationTests(DecisionHelpers, TestCase):
    def setUp(self):
        self.setup_decisions()

    def test_lookup_must_match_current_pwd_and_cannot_be_forged_as_a_result(self):
        intake = self.make()
        for changes in ({'prpwd_lookup_number': ''}, {'prpwd_lookup_number': 'wrong'},
                        {'prpwd_verified': 'true'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.decide(intake, self.data(intake, **changes))
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertFalse(MembershipEvent.objects.exists())

    def test_manual_approval_records_verifier_date_url_and_both_audits(self):
        intake = self.make()
        self.decide(intake)
        app = Member.objects.get().application
        self.assertTrue(app.prpwd_verified)
        self.assertEqual(app.prpwd_verified_by, self.actor)
        self.assertIsNotNone(app.prpwd_verified_at)
        self.assertEqual(app.verification_url, 'https://registry.example.test/manual')
        self.assertEqual(list(app.events.order_by('occurred_at', 'pk').values_list('action', flat=True)),
            ['prpwd_verified', 'approved'])

    def test_manual_negative_result_is_recorded_without_creating_a_member(self):
        intake = self.make()
        self.decide(intake, self.data(intake, action='decline_registration'))
        app = MembershipApplication.objects.get()
        self.assertFalse(app.prpwd_verified)
        self.assertEqual(app.prpwd_verified_by, self.actor)
        self.assertIsNotNone(app.prpwd_verified_at)
        self.assertFalse(Member.objects.exists())
        self.assertTrue(app.events.filter(action='prpwd_not_verified').exists())

    def test_verification_permission_and_configured_registry_are_required(self):
        intake = self.make()
        actor = staff('synthetic_no_registry_permission', 'membership.decide_membershipapplication')
        with self.assertRaises(PermissionDenied):
            self.decide(intake, actor=actor)
        MembershipSettings.objects.update(prpwd_url='')
        with self.assertRaisesMessage(ValidationError, 'official PRPWD'):
            self.decide(intake)
        self.assertFalse(Member.objects.exists())

    def test_onsite_lookup_carries_to_review_but_leaves_verification_pending(self):
        from membership.tests import grant
        grant(self.actor, 'membership.encode_registrationintake')
        self.client.force_login(self.actor)
        url = reverse('membership:registration_encode', args=['walk_in'])
        response = self.client.get(url)
        data = self.data(self.make())
        for name in ('version', 'action'):
            data.pop(name)
        data['context_id'] = response.context['context_id']
        response = self.client.post(url, data, follow=True)
        self.assertEqual(response.status_code, 200)
        intake = RegistrationIntake.objects.get(channel='walk_in')
        self.assertEqual(response.context['editor_form'].initial['prpwd_lookup_number'], data['pwd_number'])
        self.assertContains(response, 'data-prpwd-review')
        self.assertContains(response, 'Leave pending')
        self.assertFalse(MembershipApplication.objects.exists())
        self.assertFalse(Member.objects.exists())
        self.assertFalse(MembershipEvent.objects.exists())
        self.assertNotIn('prpwd_lookup_number', intake.revisions.get().data)
