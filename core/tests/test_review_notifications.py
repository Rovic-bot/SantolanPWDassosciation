"""Review counters contain aggregates only and do not advance application states."""
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from analytics.tests import only_reads
from members.tests import create_member
from membership.models import MembershipApplication
from membership.pdao_models import PDAORegistration
from membership.registration_models import RegistrationIntake, RegistrationSubmissionContext, registration_write
from membership.test_pdf_registration import pdf_policy
from membership.tests import grant, profile
from programs.models import ProgramApplication
from programs.tests import create_program


@override_settings(ASSOCIATION_REGISTRATION_POLICY=pdf_policy(), PDAO_ENFORCEMENT_ENABLED=False)
class ReviewNotificationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('synthetic_badge_admin')
        cls.member = create_member('SYNTH-BADGE-MEMBER')
        cls.programs = [create_program(name='Synthetic review program'), create_program(name='Synthetic second program')]
        cls.applications = []
        for i, state in enumerate(ProgramApplication.Status.values):
            member = create_member(f'SYNTH-BADGE-{i}')
            cls.applications.append(ProgramApplication.objects.create(program=cls.programs[0], member=member,
                public_reference=f'SYNTH-BADGE-APP-{i}', status=state))
        ProgramApplication.objects.create(program=cls.programs[1], member=cls.member,
            public_reference='SYNTH-BADGE-OTHER', status='ELIGIBILITY_REVIEW')
        with registration_write():
            cls.intakes = []
            for i, (channel, decision) in enumerate([('online', None), ('online', 'pending'),
                    ('online', 'approved'), ('online', 'rejected'), ('walk_in', None)]):
                context = RegistrationSubmissionContext.objects.create(binding_digest='a' * 64,
                    policy_digest='b' * 64, channel=channel, actor=cls.admin if channel != 'online' else None,
                    expires_at=timezone.now() + timedelta(hours=1))
                application = MembershipApplication.objects.create(**(profile() | {'control_number': f'SYNTH-REVIEW-{i}'}),
                    submission_key=uuid4(), status=decision) if decision else None
                cls.intakes.append(RegistrationIntake.objects.create(context=context, request_key=context.request_key,
                    reference=f'AMR-SYNTH-{i}', payload_digest='c' * 64, channel=channel, policy_snapshot={},
                    membership_application=application, state='membership_review' if application else 'received'))
            cls.pdao = []
            for channel, status in [('online', 'received'), (None, 'received'), ('walk_in', 'received'),
                                    ('online', 'needs_info'), ('online', 'ready'), ('online', 'forwarded')]:
                cls.pdao.append(PDAORegistration.objects.create(submission_key=uuid4(),
                    data={'intake_channel': channel} if channel else {}, status=status,
                    payload_digest='d' * 64, privacy_version='synthetic', binding_digest='e' * 64,
                    receipt_expires_at=timezone.now() + timedelta(hours=1)))

    def setUp(self):
        self.url = reverse('core:review_notification_counts')
        self.client.force_login(self.admin)

    def test_totals_states_channels_and_card_counts_are_read_only(self):
        with connection.execute_wrapper(only_reads):
            response = self.client.get(self.url, {'programs': ','.join(str(p.pk) for p in self.programs)})
        self.assertEqual(response.json(), {'membership': 4, 'association': 2, 'pdao': 2, 'programs': 4,
            'program_cards': {str(self.programs[0].pk): 3, str(self.programs[1].pk): 1}})
        self.assertIn('no-store', response.headers['Cache-Control'])
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_counts_clear_after_reviews_and_include_new_submissions(self):
        ProgramApplication.objects.filter(status__in=('PENDING_PHOTO_VERIFICATION', 'PHOTO_VERIFIED',
            'ELIGIBILITY_REVIEW')).update(status='ELIGIBLE')
        with registration_write():
            for item in self.pdao[:2]:
                item.status = 'ready'
                item.save(update_fields=['status'])
            for item in self.intakes[:2]:
                if item.membership_application_id:
                    MembershipApplication.objects.filter(pk=item.membership_application_id).update(status='approved')
                else:
                    item.membership_application = MembershipApplication.objects.create(
                        **(profile() | {'control_number': 'SYNTH-NEW-DECISION'}), submission_key=uuid4(), status='approved')
                    item.state = 'membership_review'
                    item.save()
        self.assertEqual(self.client.get(self.url).json(),
            dict(membership=0, association=0, pdao=0, programs=0, program_cards={}))
        ProgramApplication.objects.filter(pk=self.applications[0].pk).update(status='ELIGIBILITY_REVIEW')
        self.assertEqual(self.client.get(self.url).json()['programs'], 1)

    def test_permissions_and_revocation_do_not_disclose_other_queues(self):
        user = get_user_model().objects.create_user('badge_limited', is_staff=True)
        grant(user, 'accounts.access_dashboard', 'programs.view_program')
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).json(),
            dict(membership=0, association=0, pdao=0, programs=0, program_cards={}))
        grant(user, 'membership.view_pdaoregistration')
        self.assertEqual(self.client.get(self.url).json()['membership'], 2)
        grant(user, 'membership.view_membershipapplication')
        self.assertEqual(self.client.get(self.url).json()['association'], 0)
        grant(user, 'membership.view_registrationintake', 'programs.view_programapplication')
        self.assertEqual(self.client.get(self.url).json()['association'], 2)
        self.assertEqual(self.client.get(self.url).json()['programs'], 4)
        user.user_permissions.clear()
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_bounded_card_request_and_disabled_association_policy(self):
        for ids in ('-1', 'abc', '1.5', '1,' * 21, '9' * 11, '١'):
            self.assertEqual(self.client.get(self.url, {'programs': ids}).status_code, 400)
        with override_settings(ASSOCIATION_REGISTRATION_POLICY={}):
            self.assertEqual(self.client.get(self.url).json()['association'], 0)

    def test_badges_on_navigation_membership_and_filtered_program_cards(self):
        output = Path(__file__).resolve().parents[2] / '.local/dashboard-badges-20261111'
        output.mkdir(parents=True, exist_ok=True)
        for name, route, query in [('membership', 'membership:review_home', {}),
                ('programs', 'program_portfolio', {'q': self.programs[0].name})]:
            response = self.client.get(reverse(route), query)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'data-review-count="membership"')
            self.assertContains(response, 'data-review-count="programs"')
            if name == 'membership':
                for kind in ('association', 'pdao'):
                    self.assertContains(response, f'data-review-count="{kind}"')
            else:
                self.assertEqual([(p.pk, p.review_count) for p in response.context['page_obj']], [(self.programs[0].pk, 3)])
                self.assertContains(response, f'data-program-count-id="{self.programs[0].pk}"')
                self.assertNotContains(response, f'data-program-count-id="{self.programs[1].pk}"')
            output.joinpath(name + '.html').write_text(response.content.decode(), encoding='utf-8')
