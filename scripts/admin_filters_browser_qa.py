"""Automatic admin filters against synthetic records in disposable MySQL only."""
import json
import os
from pathlib import Path
import subprocess

from django.test import Client, override_settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.urls import reverse

from events.models import Event
from membership.test_registration_intake import synthetic_policy
from scripts import admin_theme_fixtures
from scripts.durable_test_runner import require_disposable


@override_settings(REFERRAL_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
    PDAO_REGISTRATION_ENABLED=True, ASSOCIATION_REGISTRATION_POLICY=synthetic_policy())
class AdminFiltersBrowserTests(StaticLiveServerTestCase):
    host = '127.0.0.1'

    def test_read_only_filters_across_admin_pages(self):
        require_disposable()
        admin_theme_fixtures.AdminThemeFixtures.setUpTestData.__func__(type(self))
        self.client.force_login(self.admin)
        names = ('core:dashboard', 'programs:manage_list', 'core:application_programs',
            'programs:photo_queue', 'assistance:release_programs', 'assistance:referral_inbox',
            'events:manage_list', 'announcements:manage_list',
            'membership:registration_inbox', 'membership:pdao_inbox', 'ewaf:operational_programs',
            'reports:members', 'reports:applications', 'reports:programs', 'reports:assistance',
            'admin:auth_user_changelist', 'admin:auth_group_changelist',
            'admin:documents_documenttype_changelist', 'admin:audit_securityevent_changelist',
            'admin:admin_logentry_changelist')
        pages = [{'name': name, 'url': reverse(name)} for name in names]
        pages.extend([
            {'name': 'programs:applications', 'url': reverse('programs:applications', args=[self.programs[0].pk])},
            {'name': 'assistance:queue', 'url': reverse('assistance:queue') + f'?program={self.programs[0].pk}'},
            {'name': 'events:attendance_list', 'url': reverse('events:attendance_list', args=[Event.objects.first().pk])},
            {'name': 'events:registrations', 'url': reverse('events:registrations', args=[Event.objects.first().pk])},
        ])
        for page in pages:
            response = self.client.get(page['url'], follow=True)
            self.assertEqual(response.status_code, 200, page['name'])
            self.assertContains(response, 'js/admin-filters.js', count=1)
        for route in ('core:home', 'core:events', 'core:programs', 'core:announcements'):
            self.assertNotContains(self.client.get(reverse(route)), 'js/admin-filters.js')
        directory = Path(os.environ['G12_ARTIFACT_DIR']) / 'admin-filters-browser'
        directory.mkdir()
        manifest = {'pages': pages, 'program': str(self.programs[0].pk),
            'editor': reverse('programs:create'), 'onsite': reverse('membership:encode'),
            'directory': reverse('member_directory')}
        directory.joinpath('manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        client = Client()
        client.force_login(self.admin)
        result = subprocess.run(['node', 'scripts/admin_filters_browser_qa.cjs'],
            env={**os.environ, 'QA_URL': self.live_server_url, 'QA_OUTPUT': str(directory),
                 'QA_ADMIN_SESSION': client.cookies['sessionid'].value}, capture_output=True,
            text=True, encoding='utf-8', timeout=240,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout, flush=True)
