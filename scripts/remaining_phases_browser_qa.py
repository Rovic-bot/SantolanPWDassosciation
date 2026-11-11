"""Synthetic browser integration; no working server, identities or media."""
import os
from pathlib import Path
import secrets
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone
from core.content import save_content, RESOURCE_KEYS
from core.tests.test_resources import resource_data
from members.models import Member
from members.tests import create_member
from members.review_models import InformationReview
from members.test_information_review import synthetic_review_policy
from membership.models import MembershipApplication
from membership.registration_models import RegistrationIntake, RegistrationRevision
from membership.test_registration_intake import synthetic_policy
from scripts.durable_test_runner import require_disposable


class RemainingPhasesBrowserTests(StaticLiveServerTestCase):
    def test_registration_review_and_published_resources(self):
        require_disposable()
        actor = get_user_model().objects.create_superuser('synthetic_remaining_browser')
        password = secrets.token_urlsafe(32)
        actor.set_password(password)
        actor.save()
        member = create_member('SYNTHETIC-BROWSER-MEMBER')
        for key in RESOURCE_KEYS:
            save_content(key, user=actor, data=resource_data(action='publish',
                title='Synthetic reviewed ' + key, body='Synthetic demonstration only. This is not Association policy or a real service notice.'))
        root = Path(__file__).resolve().parents[1]
        env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': actor.username,
            'QA_PASSWORD': password, 'QA_MEMBER_ID': str(member.pk), 'QA_TODAY': timezone.localdate().isoformat()}
        with override_settings(ASSOCIATION_REGISTRATION_POLICY=synthetic_policy(onsite_enabled=True),
                               INFORMATION_REVIEW_POLICY=synthetic_review_policy()):
            result = subprocess.run(['node', str(root / 'scripts/remaining_phases_browser_qa.cjs')],
                cwd=root, env=env, capture_output=True, text=True, encoding='utf-8', timeout=300)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        self.assertEqual(RegistrationIntake.objects.count(), 1)
        self.assertEqual(RegistrationRevision.objects.count(), 2)
        self.assertEqual(MembershipApplication.objects.count(), 1)  # Only the pre-existing synthetic Member fixture.
        self.assertEqual(Member.objects.count(), 1)
        self.assertEqual(InformationReview.objects.count(), 1)
        self.assertEqual(InformationReview.objects.get().actions.count(), 2)
