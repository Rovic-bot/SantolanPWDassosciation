"""Popup integration keeps the existing private attachment permission boundary."""
from html.parser import HTMLParser

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from membership.tests import grant as grant_permissions, pdf
from . import test_application_workflow as fixtures
from .forms import snapshot
from .models import ProgramDocument, ProgramRequirement
from .tests import create_program
from .testsupport import application_fixture


class PreviewMarkup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links, self.dialogs = [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a':
            self.links.append(attrs)
        elif tag == 'dialog':
            self.dialogs.append(attrs)


@override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True, PDAO_ENFORCEMENT_ENABLED=False)
class DocumentPreviewTests(TestCase):
    def setUp(self):
        fixtures.ConfirmedApplicationTests.setUp(self)
        self.application = application_fixture(self.program, self.member)
        requirement = ProgramRequirement.objects.create(program=self.program, label='Submitted evidence', kind='document')
        self.application.requirements_snapshot = snapshot(self.program)
        self.application.save(update_fields=['requirements_snapshot'])
        self.document = ProgramDocument.objects.create(application=self.application, requirement=requirement,
            label=requirement.label, file=pdf(), content_type='application/pdf', size=100)
        self.url = reverse('programs:application_detail', args=[self.program.pk, self.application.pk])
        self.document_url = reverse('programs:document', args=[self.program.pk, self.application.pk, self.document.pk])
        self.photo_url = reverse('programs:photo', args=[self.application.pk, self.application.current_photo_id])

    def test_review_uses_one_accessible_popup_for_documents_and_photo_and_keeps_downloads(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        markup = PreviewMarkup(html)
        previews = [link for link in markup.links if 'data-document-preview' in link]
        self.assertEqual(len(previews), 3)  # photo thumbnail, photo preview, submitted PDF
        self.assertCountEqual([link['href'] for link in previews],
            [self.photo_url, self.photo_url, self.document_url + '?preview=1'])
        for link in previews:
            self.assertEqual(link['aria-haspopup'], 'dialog')
            self.assertTrue(link['data-preview-title'])
            self.assertNotIn('target', link)
        dialogs = [dialog for dialog in markup.dialogs if 'data-document-preview-dialog' in dialog]
        self.assertEqual(len(dialogs), 1)
        self.assertEqual(dialogs[0]['aria-labelledby'], 'document-preview-title')
        self.assertGreater(html.index('data-document-preview-dialog'), html.index('</main>'))
        self.assertContains(response, 'css/document-preview.css')
        self.assertContains(response, 'js/document-preview.js')
        self.assertIn(self.document_url, [link.get('href') for link in markup.links if 'data-document-preview' not in link])
        self.assertIn(self.photo_url, [link.get('href') for link in markup.links if 'download' in link])

    def test_popup_fetch_keeps_private_permissions_and_download_security_headers(self):
        for url in (self.document_url + '?preview=1', self.photo_url):
            self.assertEqual(self.client.get(url).status_code, 302)
        viewer = get_user_model().objects.create_user('preview-without-document-access', is_staff=True)
        grant_permissions(viewer, 'accounts.access_dashboard', 'programs.view_program', 'programs.view_programapplication')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.document_url + '?preview=1').status_code, 403)
        markup = PreviewMarkup(self.client.get(self.url).content.decode())
        self.assertFalse([link for link in markup.links if link.get('href') == self.document_url + '?preview=1'])
        self.client.force_login(self.admin)
        for preview in (False, True):
            response = self.client.get(self.document_url + ('?preview=1' if preview else ''))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/pdf')
            self.assertTrue(response['Content-Disposition'].startswith('inline;' if preview else 'attachment;'))
            self.assertIn('no-store', response['Cache-Control'])
            self.assertIn('private', response['Cache-Control'])
            self.assertEqual(response['Referrer-Policy'], 'no-referrer')
            self.assertEqual(response['Content-Security-Policy'], "sandbox; default-src 'none'")
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            self.assertEqual(response['X-Frame-Options'], 'DENY')
            self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF-'))
        self.assertEqual(self.application.history.filter(action='document_downloaded').count(), 2)

    def test_preview_url_cannot_cross_program_scope_and_missing_file_stays_unavailable(self):
        self.client.force_login(self.admin)
        other_program = create_program()
        forged = reverse('programs:document', args=[other_program.pk, self.application.pk, self.document.pk])
        self.assertEqual(self.client.get(forged + '?preview=1').status_code, 404)
        self.document.file.storage.delete(self.document.file.name)
        self.assertEqual(self.client.get(self.document_url + '?preview=1').status_code, 404)
