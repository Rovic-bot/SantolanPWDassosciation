"""Directory interaction checks on a fresh disposable MySQL instance only."""
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse
from django.utils import timezone

from members.models import Member, MemberEvent
from members.review_services import open_review
from members.test_information_review import synthetic_review_policy, intake_data
from members.tests import create_member
from scripts.durable_test_runner import require_disposable


@override_settings(INFORMATION_REVIEW_POLICY=synthetic_review_policy())
class MemberDirectoryBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_directory_search_selection_and_responsive_layout(self):
        require_disposable()
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'member-directory-browser'
        directory.mkdir()
        actor = get_user_model().objects.create_superuser('synthetic_directory_browser', password=None)
        names = ['Ana Reyes', 'Ben Santos', 'Cora Cruz', 'Dan Ramos', 'Ella Garcia', 'Finn Mendoza',
                 'Gia Torres', 'Hugo Bautista', 'Iris Dela Cruz', 'Jiro Aquino', 'Kara Castillo', 'Luis Navarro',
                 'Mara Flores', 'Nico Dizon', 'Ona Mercado', 'Paolo Castro', 'Rina Lopez', 'Sam Valdez',
                 'Tala Lim', 'Uri Santiago', 'Vera Ramos', 'Will Reyes', 'Xena Cruz', 'Yana Santos', 'Zoe Garcia']
        members = []
        for index, name in enumerate(names):
            member = create_member(f'TEST-2026-{index + 1:03d}')
            Member.objects.filter(pk=member.pk).update(full_name=name,
                contact_number=f'0917000{index:04d}', is_active=index not in (5, 11, 23, 24),
                archived_at=timezone.now() if index == 24 else None)
            member.refresh_from_db()
            members.append(member)
        open_review(members[2].pk, user=actor, data=intake_data())
        MemberEvent.objects.create(member=members[0], actor=actor, actor_label='Synthetic staff',
            action='profile_updated', notes='Synthetic note: contact details reviewed at the membership desk.')
        client = Client()
        client.force_login(actor)
        env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_ADMIN_SESSION': client.cookies['sessionid'].value,
               'QA_DIRECTORY_ROUTE': reverse('member_directory'), 'QA_OUTPUT': str(directory),
               'QA_FIRST_ID': str(members[0].pk), 'QA_SECOND_ID': str(members[1].pk)}
        result = subprocess.run(['node', 'scripts/member_directory_browser_qa.cjs'], env=env,
            capture_output=True, text=True, encoding='utf-8', timeout=150,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(Member.objects.count(), 25)
        print(result.stdout, flush=True)
