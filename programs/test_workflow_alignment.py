from datetime import timedelta
from io import BytesIO, StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.datastructures import MultiValueDict
from PIL import Image
from announcements.masking import masked_name
from announcements.models import Announcement
from announcements.program_publication import process_closed_program
from assistance.models import AssistanceCase
from assistance.services import review_eligibility, decide_assistance
from assistance.tests import review_data, decision_data, seed_statuses
from documents.models import DocumentType, MembershipDocumentRequirement
from events.models import EventRegistration
from events.tests import create_event
from members.models import DisabilityType, Member
from members.tests import create_member
from membership.models import MembershipApplication, MembershipSettings
from membership.forms import ApplicationForm
from membership.tests import profile, onsite_profile
from programs.forms import ProgramForm
from programs.models import ProgramApplication, ProgramLog
from programs.services import save_program, verify_member, submit_application
from programs.tests import create_program, program_data, verification
from ewaf.models import ApplicationInput, Snapshot
from ewaf.services import generate_ranking, current_ranking
from ewaf.testsupport import prepare_ranking, test_configuration


class WorkflowAlignmentTests(TestCase):
    def setUp(self):
        seed_statuses()
        self.admin = get_user_model().objects.create_superuser('alignment-admin')
        self.member = create_member('ALIGN-001')
        self.member.full_name = 'John Doe'
        self.member.save()
        self.program = create_program()

    def submit(self, member=None, program=None):
        member, program = member or self.member, program or self.program
        grant = verify_member(program.pk, **verification(member, program))
        return submit_application(program.pk, grant=grant, data={'version': program.version}, files=MultiValueDict())

    def eligible(self, app):
        return review_eligibility(app.pk, user=self.admin, data=review_data(app))

    def test_public_membership_is_guidelines_only_even_when_legacy_flag_open(self):
        MembershipSettings.objects.update_or_create(pk=1, defaults={'registration_open': True, 'prpwd_url': 'https://example.test/'})
        active = MembershipDocumentRequirement.objects.create(document_type=DocumentType.objects.create(name='Configured active requirement'))
        MembershipDocumentRequirement.objects.create(document_type=DocumentType.objects.create(name='Inactive requirement'), is_active=False)
        page = self.client.get(reverse('core:membership'))
        self.assertContains(page, 'How to become a member')
        self.assertContains(page, 'Birth Certificate OR Marriage Certificate')
        self.assertNotContains(page, str(active))
        self.assertTrue(MembershipDocumentRequirement.objects.filter(pk=active.pk, is_active=True).exists())
        self.assertNotContains(page, 'Inactive requirement')
        before = MembershipApplication.objects.count()
        self.assertEqual(self.client.post(reverse('core:membership'), profile()).status_code, 405)
        self.assertEqual(MembershipApplication.objects.count(), before)

    def test_admin_encoding_requires_permission_and_does_not_create_account(self):
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://example.test/'})
        route = reverse('membership:encode')
        self.assertEqual(self.client.get(route).status_code, 302)
        restricted = get_user_model().objects.create_user('restricted', is_staff=True)
        self.client.force_login(restricted)
        self.assertEqual(self.client.get(route).status_code, 403)
        self.client.force_login(self.admin)
        count = get_user_model().objects.count()
        data = {**onsite_profile(), 'disability_types': [self.member.disability_type_id], 'control_number': 'NEW-ONSITE',
                'submission_token': ApplicationForm().initial['submission_token']}
        response = self.client.post(route, data)
        self.assertEqual(response.status_code, 302)
        app = MembershipApplication.objects.get(control_number='NEW-ONSITE')
        self.assertEqual(app.status, 'pending')
        self.assertEqual(app.events.get().actor, self.admin)
        self.assertFalse(Member.objects.filter(application=app).exists())
        self.assertEqual(get_user_model().objects.count(), count)
