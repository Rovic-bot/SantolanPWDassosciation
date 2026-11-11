from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.html import escape

from members.models import DisabilityType
from members.tests import create_member
from programs.models import ProgramApplication
from programs.tests import create_program
from . import access


@override_settings(ROOT_URLCONF='program_intake.test_urls', PROGRAM_INTAKE_ENABLED=True,
    PROGRAM_APPLICATION_WORKFLOW_ENABLED=False, PDAO_ENFORCEMENT_ENABLED=False)
class DisabilityScreeningTests(TestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser('screening-admin', password='synthetic-only')
        self.member = create_member('SYNTHETIC-INTAKE-SCREENING')
        self.member.disability_cause = 'congenital'
        self.member.disability_visibility = 'apparent'
        self.member.save()
        self.member.application.decided_by = admin
        self.member.application.save(update_fields=['decided_by'])
        self.program = create_program(policy_authorized_by=admin)
        self.verify_url = reverse('programs:verify', args=[self.program.pk])
        self.apply_url = reverse('programs:apply', args=[self.program.pk])
        self.data = {'control_number': self.member.control_number,
            'full_name': access.registered_name(self.member), 'disability_types': self.member.disability_ids,
            'disability_cause': self.member.disability_cause, 'disability_visibility': self.member.disability_visibility,
            'version': self.program.version}

    def restrict_to_unmatched_type(self):
        other = DisabilityType.objects.create(name='Synthetic unmatched classification')
        self.program.eligible_disability_types.set([other])

    def test_verified_mismatch_explains_block_and_clears_previous_grant(self):
        self.assertRedirects(self.client.post(self.verify_url, self.data), self.apply_url)
        self.restrict_to_unmatched_type()
        response = self.client.post(self.verify_url, self.data)
        self.assertContains(response, 'You cannot proceed with this application because')
        self.assertContains(response, 'target disability types')
        self.assertNotContains(response, escape(access.FAILED))
        self.assertNotIn('program_verification', self.client.session)
        self.assertRedirects(self.client.post(self.apply_url, {}), self.verify_url)
        self.assertFalse(ProgramApplication.objects.exists())

    def test_disability_mismatch_is_private_until_identity_matches(self):
        self.restrict_to_unmatched_type()
        response = self.client.post(self.verify_url, {**self.data, 'full_name': 'Incorrect name'})
        self.assertContains(response, escape(access.FAILED))
        self.assertNotContains(response, 'target disability types')
        self.assertNotIn('program_verification', self.client.session)
        self.assertFalse(ProgramApplication.objects.exists())

    def test_program_without_restriction_accepts_verified_member(self):
        self.program.eligible_disability_types.clear()
        self.assertRedirects(self.client.post(self.verify_url, self.data), self.apply_url)
