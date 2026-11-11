"""Synthetic admin presentation fixtures; run only with the disposable G12 runner."""
import json
import re
from pathlib import Path

from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import reverse, resolve
from django.utils import timezone

from analytics import tests as analytics_fixtures
from announcements.models import Announcement
from core.models import PublicContent
from core.templatetags.workspace_navigation import workspace_navigation
from events.models import Event
from membership import registration_services
from membership.test_registration_intake import synthetic_policy, submitted
from members.update_models import MemberUpdateAccess, MemberUpdateRequest, update_write
from scripts.durable_test_runner import require_disposable


@override_settings(REFERRAL_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False,
    PDAO_REGISTRATION_ENABLED=True, ASSOCIATION_REGISTRATION_POLICY=synthetic_policy())
class AdminThemeFixtures(TestCase):
    @classmethod
    def setUpTestData(cls):
        require_disposable()
        analytics_fixtures.OverviewTests.setUpTestData.__func__(cls)
        cls.notice = Announcement.objects.create(title='Community support schedule', content='Visit the Association office for the current support schedule.')
        PublicContent.objects.get_or_create(key='about', defaults={'title':'About the Association','body':'Community information managed by Association staff.'})
        cls.group = Group.objects.create(name='Synthetic review team')
        binding = registration_services.binding_for('synthetic-theme-fixture')
        context = registration_services.issue_context(binding)
        cls.intake = registration_services.submit_registration(context.pk, binding, submitted())
        # A pending request exercises the current comparison screen without sending mail.
        with update_write():
            access = MemberUpdateAccess.objects.create(member=cls.members[0],
                member_version=cls.members[0].version, session_digest='synthetic',
                code_digest='synthetic', expires_at=timezone.now())
            cls.member_update = MemberUpdateRequest.objects.create(access=access, member=cls.members[0],
                member_version=cls.members[0].version, previous_values={'first_name': 'Previous'},
                proposed_values={'first_name': 'Updated'}, changed_fields=['first_name'])

    def test_admin_theme_routes_and_capture(self):
        self.client.force_login(self.admin)
        first = self.client.get(reverse('core:dashboard'))
        request = first.wsgi_request
        request.resolver_match = resolve(reverse('core:dashboard'))
        urls = [link['url'] for group in workspace_navigation({'request':request}) for link in group['links']]
        urls += [reverse(name) for name in ('admin:index','admin:auth_user_add','admin:auth_group_add',
            'admin:documents_documenttype_add','admin:password_change','accounts:password_change',
            'programs:create','events:manage_list','events:create','events:observance_create',
            'announcements:create','membership:registration_inbox','membership:pdao_inbox',
            'assistance:referral_email_settings')]
        urls += [reverse(name,args=[self.members[0].pk]) for name in ('members:detail','members:edit')]
        program = self.programs[0]
        urls += [reverse(name,args=[program.pk]) for name in ('programs:manage_detail','programs:edit',
            'programs:applications','programs:requirement_add','ewaf:operational_workspace',
            'ewaf:operational_breakdown','assistance:program_releases')]
        urls += [reverse(name,args=[self.notice.pk]) for name in ('announcements:manage_detail','announcements:edit')]
        event = Event.objects.first()
        urls += [reverse(name,args=[event.pk]) for name in ('events:manage_detail','events:edit')]
        urls += [reverse('programs:application_detail',args=[program.pk,self.applications[0].pk]),
            reverse('assistance:detail',args=[self.applications[0].pk]),
            reverse('core:content_edit',args=['about']),
            reverse('membership:registration_detail',args=[self.intake.reference]),
            reverse('admin:auth_user_change',args=[self.admin.pk]),
            reverse('admin:auth_group_change',args=[self.group.pk]),
            reverse('admin:auth_group_add')+'?_popup=1',
            reverse('members:update_review',args=[self.member_update.pk])]
        output = Path('.local/admin-theme-synthetic')
        output.mkdir(exist_ok=True)
        manifest = []
        for index,url in enumerate(dict.fromkeys(urls)):
            with self.subTest(url=url):
                response = self.client.get(url,follow=True)
                self.assertEqual(response.status_code,200)
                self.assertContains(response,'css/admin-theme.css',count=1)
                self.assertContains(response,'css/admin-palette.css',count=1)
                self.assertContains(response,'js/dashboard-theme.js',count=1)
                if '_popup' not in url:
                    self.assertContains(response,'data-dashboard-theme-toggle',count=1)
                    route = resolve(url.split('?')[0]).view_name
                    # Builders already return to their corresponding staff list.
                    if route in ('programs:create', 'programs:edit'):
                        self.assertContains(response, f'href="{reverse("program_portfolio")}">Program portfolio')
                    elif route in ('events:create', 'events:edit'):
                        self.assertContains(response, f'href="{reverse("event_workspace")}">Events calendar')
                    elif 'onsite-registration-workspace' not in response.content.decode():
                        self.assertContains(response,'View Public Site')
                filename = f'{index:02d}.html'
                output.joinpath(filename).write_bytes(response.content)
                manifest.append({'file':filename,'url':url,'name':resolve(url.split('?')[0]).view_name,'popup':'_popup' in url})
        output.joinpath('manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
        output.joinpath('jsi18n.js').write_bytes(self.client.get(reverse('admin:jsi18n')).content)
        activity = self.client.get(reverse('admin:admin_logentry_changelist')).content.decode()
        dialog_manifest = []
        for index, url in enumerate(re.findall(r'href="([^"]+)" data-activity-inspect', activity)):
            url += '?dialog=1'
            response = self.client.get(url)
            self.assertContains(response, 'data-activity-detail')
            filename = f'activity-detail-{index}.html'
            output.joinpath(filename).write_bytes(response.content)
            dialog_manifest.append({'file': filename, 'url': url})
        output.joinpath('dialog-manifest.json').write_text(json.dumps(dialog_manifest, indent=2), encoding='utf-8')
        print(f'Captured {len(manifest)} synthetic admin screens for browser verification.',flush=True)

    def test_public_pages_do_not_load_admin_theme(self):
        for route in ('core:home','core:about','core:programs','core:events','core:announcements','accounts:login'):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code,200)
                self.assertNotContains(response,'css/admin-theme.css')
                self.assertNotContains(response,'css/admin-palette.css')
                self.assertNotContains(response,'js/dashboard-theme.js')
                self.assertNotContains(response,'data-dashboard-theme-toggle')
