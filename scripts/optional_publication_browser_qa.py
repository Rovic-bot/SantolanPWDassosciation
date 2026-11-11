"""Publish with optional text blank and unpublish an event in disposable MySQL."""
import os
from pathlib import Path
import subprocess

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse

from events.services import publish_event, save_event
from events.tests import event_data
from programs.services import save_program
from programs.tests import program_data
from programs.testsupport import private_media
from scripts.durable_test_runner import require_disposable


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class OptionalPublicationBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_optional_program_publication_and_event_unpublish(self):
        require_disposable()
        private_media(self)
        actor = get_user_model().objects.create_superuser('synthetic_optional_publisher')
        program = save_program(user=actor, setup_only=True,
            data=program_data(name='Synthetic optional program', description='', benefit='', ewaf_applicable=False))
        event = save_event(user=actor, data=event_data(title='Synthetic withdrawable event'))
        event = publish_event(event.pk, user=actor, version=event.version)
        client = Client()
        client.force_login(actor)
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'optional-publication-browser'
        directory.mkdir()
        result = subprocess.run(['node', 'scripts/optional_publication_browser_qa.cjs'], env={**os.environ,
            'QA_URL': self.live_server_url, 'QA_OUTPUT': str(directory),
            'QA_SESSION': client.cookies['sessionid'].value,
            'QA_PROGRAM': reverse('programs:manage_detail', args=[program.pk]),
            'QA_BUILDER': reverse('programs:edit', args=[program.pk]),
            'QA_EVENT': reverse('events:manage_detail', args=[event.pk]),
            'QA_EVENTS': reverse('events:manage_list'),
            'QA_POPUP': reverse('events:detail', args=[event.pk]) + '?popup=1'},
            capture_output=True, text=True, encoding='utf-8', timeout=180,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        program.refresh_from_db()
        event.refresh_from_db()
        self.assertEqual((program.status, program.description, program.benefit), ('published', '', ''))
        self.assertEqual(program.history.filter(action='published').count(), 1)
        self.assertEqual(event.status, 'draft')
        self.assertEqual(event.history.get(action='draft').notes, 'Synthetic browser withdrawal for schedule review.')
        print(result.stdout, flush=True)
