"""Synthetic Phase 2A UI checks, through the isolated no-migration test runner."""
import os
from pathlib import Path
import secrets
import subprocess
from uuid import UUID, uuid4

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from membership.models import MembershipApplication, MembershipEvent
from membership.tests import grant, profile


class ReferenceRetrievalBrowserTests(StaticLiveServerTestCase):
    def test_staff_reference_lookup_keyboard_and_responsive_layout(self):
        root = Path(__file__).resolve().parents[1]
        password = secrets.token_urlsafe(32)
        officer = get_user_model().objects.create_user('synthetic_reference_officer',
            password=password, is_staff=True)
        grant(officer, 'accounts.access_dashboard', 'membership.view_membershipapplication')
        pending = MembershipApplication.objects.create(**{**profile(),
            'full_name': 'Synthetic Pending Applicant', 'control_number': 'SYNTHETIC-UI-001'},
            reference=UUID('11111111-2222-4333-8444-555555555555'), submission_key=uuid4())
        completed = MembershipApplication.objects.create(**{**profile(),
            'full_name': 'Synthetic Rejected Applicant', 'control_number': 'SYNTHETIC-UI-002'},
            reference=UUID('aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee'), submission_key=uuid4(),
            status=MembershipApplication.Status.REJECTED, decision_notes='Synthetic retained review fixture.')
        before = list(MembershipApplication.objects.order_by('pk').values())
        env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': officer.username,
            'QA_PASSWORD': password, 'QA_REFERENCE': str(completed.reference),
            'QA_PENDING_REFERENCE': str(pending.reference),
            'QA_LIST': reverse('membership:list'),
            'QA_DETAIL': reverse('membership:detail', args=[completed.reference])}
        result = subprocess.run(['node', str(root / 'scripts/reference_retrieval_browser_qa.cjs')],
            cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=180)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.assertEqual(before, list(MembershipApplication.objects.order_by('pk').values()))
        self.assertEqual(MembershipEvent.objects.count(), 0)

