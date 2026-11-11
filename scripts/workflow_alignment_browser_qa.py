"""Approved workflow browser checks; synthetic data in disposable native MySQL."""
import json
import os
from pathlib import Path
import secrets
import subprocess
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse
from announcements.program_publication import process_closed_program
from announcements.models import Announcement
from assistance.services import review_eligibility
from assistance.tests import create_application, review_data, seed_statuses
from documents.models import DocumentType, MembershipDocumentRequirement
from events.tests import create_event
from ewaf.testsupport import prepare_ranking
from membership.models import MembershipSettings, MembershipApplication
from membership.tests import profile
from programs.tests import create_program


class WorkflowBrowserTests(StaticLiveServerTestCase):
    def test_approved_workflows_and_responsive_screens(self):
        root = Path(__file__).resolve().parents[1]
        seed_statuses()
        password = secrets.token_urlsafe(32)
        admin = get_user_model().objects.create_superuser('workflow_browser', password=password)
        MembershipSettings.objects.update_or_create(pk=1, defaults={'prpwd_url': 'https://example.test/verify'})
        MembershipDocumentRequirement.objects.create(document_type=DocumentType.objects.create(name='Synthetic onsite requirement'), is_required=False)
        app = create_application()
        member = app.member
        member.full_name = 'John Doe'
        member.save()
        review_eligibility(app.pk, user=admin, data=review_data(app))
        prepare_ranking(app.program, admin)
        announcement, _ = process_closed_program(app.program_id)
        open_program = create_program(name='Open browser program')
        event = create_event()
        routes = {'ranking': reverse('ewaf:ranking', args=[app.program_id]),
                  'status': reverse('programs:status', args=[app.status_token]),
                  'announcement': reverse('announcements:detail', args=[announcement.pk]),
                  'program': reverse('programs:detail', args=[open_program.pk]),
                  'edit': reverse('programs:edit', args=[open_program.pk]),
                  'event': reverse('events:detail', args=[event.pk]),
                  'encode': reverse('membership:encode')}
        env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME': admin.username, 'QA_PASSWORD': password,
               'QA_ROUTES': json.dumps(routes), 'QA_PROFILE': json.dumps(profile()),
               'QA_DISABILITY': str(member.disability_type_id), 'QA_CONTROL': member.control_number}
        result = subprocess.run(['node', str(root / 'scripts/workflow_alignment_browser_qa.cjs')], cwd=root, env=env,
                                capture_output=True, text=True, encoding='utf-8', timeout=240)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout)
        app.assistance_case.refresh_from_db()
        self.assertEqual(app.assistance_case.decision, 'approved')
        announcement.refresh_from_db()
        self.assertEqual(announcement.applicant_rows[0]['status'], 'Approved')
        self.assertTrue(MembershipApplication.objects.filter(control_number='BROWSER-ONSITE', status='pending').exists())
        self.assertEqual(open_program.applications.get().status, 'under_review')
        self.assertEqual(get_user_model().objects.count(), 1)
