"""Revised stages 1–7 browser acceptance, using synthetic data in disposable MySQL."""
import json
import os
from pathlib import Path
import secrets
import subprocess
from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.utils import timezone
from announcements.tests import image_upload
from assistance.models import AssistanceRelease, EligibilityStatus
from members.tests import create_member
from programs.models import ProgramApplication
from programs.tests import create_program


class RevisedBrowserTests(StaticLiveServerTestCase):
    def test_public_submission_admin_photo_correction_eligibility_selection_and_receipt(self):
        for code, label in EligibilityStatus.Code.choices:
            EligibilityStatus.objects.get_or_create(code=code, defaults={'label':label})
        root = Path(__file__).resolve().parents[1]
        password = secrets.token_urlsafe(32)
        get_user_model().objects.create_superuser('revised_browser', password=password)
        member = create_member('BROWSER-REVISED70')
        program = create_program(eligible_disability_types=[])
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            photo = Path(media)/'calendar.png'
            photo.write_bytes(image_upload().read())
            env = {**os.environ, 'QA_URL': self.live_server_url, 'QA_USERNAME':'revised_browser', 'QA_PASSWORD':password,
                'QA_PROGRAM': str(program.pk), 'QA_BIRTHDATE': str(member.birthdate), 'QA_PHOTO':str(photo),
                'QA_DATE': str(timezone.localdate())}
            def phase(name):
                result = subprocess.run(['node', str(root/'scripts/revised70_browser_qa.cjs'), name], cwd=root,
                    env=env, capture_output=True, text=True, encoding='utf-8', timeout=240)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                print(result.stdout)
            phase('public')
            application = ProgramApplication.objects.get()
            self.assertEqual(application.status, 'PENDING_PHOTO_VERIFICATION')
            self.assertEqual(application.member_id, member.pk)
            env['QA_APPLICATION'] = str(application.pk)
            env['QA_REFERENCE'] = application.public_reference
            program.registration_closes_at = timezone.now()-timezone.timedelta(minutes=1)
            program.save(update_fields=['registration_closes_at'])
            phase('admin')
            application.refresh_from_db()
            self.assertEqual(application.status, 'COMPLETED')
            self.assertEqual(application.photos.count(), 2)
            self.assertEqual(AssistanceRelease.objects.successful().count(), 1)
            self.assertEqual(application.public_reference, env['QA_REFERENCE'])
