"""Category previews follow canonical records and the existing approval boundary."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from membership.tests import grant
from programs.models import Program
from programs.tests import create_program
from .models import Announcement
from .services import change_publication, save_announcement


class AnnouncementCategoryTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('notice_admin')
        self.editor = get_user_model().objects.create_user('notice_editor', is_staff=True)
        grant(self.editor, 'accounts.access_dashboard', 'announcements.view_announcement',
              'announcements.add_announcement', 'announcements.change_announcement')
        self.program = create_program(name='Canonical program', assistance_type='Medical support')
        self.data = dict(category='general', source_office='Barangay Santolan',
                         title='General services notice', content='Official community update.', version=0)
        self.list_url = reverse('core:announcements')

    def draft(self, **overrides):
        return save_announcement(user=self.admin, data={**self.data, **overrides})

    def program_notice(self, program=None):
        return self.draft(category='programs', linked_program=(program or self.program).pk,
                          title='Do not duplicate this title', content='Do not duplicate this description')

    def publish(self, item):
        return change_publication(item.pk, user=self.admin, version=item.version, action='published')

    def test_general_source_date_category_and_home_projection(self):
        item = self.publish(self.draft())
        for url in (self.list_url, reverse('announcements:detail', args=[item.pk]), reverse('core:home')):
            response = self.client.get(url)
            self.assertContains(response, 'Barangay Santolan')
            self.assertContains(response, 'General')
            self.assertContains(response, '<time datetime=')
        self.assertNotContains(self.client.get(self.list_url, {'category': 'programs'}), item.title)
        self.assertNotContains(self.client.get(self.list_url, {'category': 'results'}), item.title)

    def test_source_required_for_new_draft_and_publication_without_inventing_legacy_metadata(self):
        for value in ('', '   '):
            with self.assertRaises(ValidationError):
                self.draft(source_office=value)
        legacy = Announcement.objects.create(title='Historical update', content='Historical content',
            status='published', published_at=timezone.now())
        self.assertContains(self.client.get(reverse('announcements:detail', args=[legacy.pk])), 'Source not recorded')
        legacy = change_publication(legacy.pk, user=self.admin, version=legacy.version, action='draft')
        with self.assertRaises(ValidationError):
            self.publish(legacy)

    def test_published_edit_is_private_until_reviewed_again_with_audit_and_stale_protection(self):
        item = self.publish(self.draft())
        version = item.version
        edited = save_announcement(user=self.admin, pk=item.pk,
            data={**self.data, 'version': version, 'content': 'Revised notice awaiting review.'})
        self.assertEqual(edited.status, 'draft')
        self.assertEqual(self.client.get(reverse('announcements:detail', args=[item.pk])).status_code, 404)
        self.assertIn('Saved for review', edited.events.first().description)
        with self.assertRaises(ValidationError):
            change_publication(item.pk, user=self.admin, version=version, action='published')
        self.publish(edited)
        self.assertContains(self.client.get(reverse('announcements:detail', args=[item.pk])), 'Revised notice')

    def test_program_preview_reads_live_canonical_content_and_links_to_membership_checks(self):
        item = self.publish(self.program_notice())
        self.assertNotEqual(item.title, self.program.name)
        self.assertNotEqual(item.content, self.program.description)
        self.program.name = 'Updated canonical program'
        self.program.description = '<script>unsafe()</script> Updated program overview.'
        self.program.save(update_fields=['name', 'description'])
        for url in (self.list_url, reverse('announcements:detail', args=[item.pk]), reverse('core:home')):
            response = self.client.get(url)
            self.assertContains(response, 'Updated canonical program')
            self.assertContains(response, 'Updated program overview')
            self.assertNotContains(response, 'Do not duplicate')
            self.assertNotContains(response, '<script>unsafe()</script>')
        detail = self.client.get(reverse('announcements:detail', args=[item.pk]))
        self.assertContains(detail, reverse('programs:detail', args=[self.program.pk]))
        self.assertContains(detail, 'membership verification')
        self.assertNotIn('linked_program', detail.context['announcement'])

    def test_nonpublic_cancelled_or_future_published_program_is_withheld_everywhere(self):
        item = self.publish(self.program_notice())
        changes = [dict(status='draft'), dict(status='archived'), dict(status='cancelled'),
                   dict(published_at=timezone.now() + timezone.timedelta(days=1))]
        for values in changes:
            with self.subTest(values=values):
                original = {key: getattr(self.program, key) for key in values}
                Program.objects.filter(pk=self.program.pk).update(**values)
                self.assertEqual(self.client.get(reverse('announcements:detail', args=[item.pk])).status_code, 404)
                for url in (self.list_url, reverse('core:home')):
                    self.assertNotContains(self.client.get(url), self.program.name)
                Program.objects.filter(pk=self.program.pk).update(**original)

    def test_program_must_still_be_public_at_publication_time(self):
        item = self.program_notice()
        Program.objects.filter(pk=self.program.pk).update(status='draft')
        with self.assertRaises(ValidationError):
            self.publish(item)
        item.refresh_from_db()
        self.assertEqual(item.status, 'draft')
        with self.assertRaises(ValidationError):
            self.program_notice()

    def test_upcoming_program_and_combined_filters_include_unrestricted_programs(self):
        restricted = self.publish(self.program_notice())
        unrestricted = create_program(name='Open classification program', eligible_disability_types=[],
            assistance_type='Educational support', registration_opens_at=timezone.now() + timezone.timedelta(hours=2))
        other = self.publish(self.program_notice(unrestricted))
        classification = str(self.program.eligible_disability_types.get().pk)
        response = self.client.get(self.list_url, {'category': 'programs', 'disability': classification})
        self.assertEqual(response.context['page_obj'].paginator.count, 2)
        self.assertContains(response, self.program.name)
        self.assertContains(response, unrestricted.name)
        response = self.client.get(self.list_url, {'category': 'programs', 'disability': classification,
                                                   'program_category': 'Medical support'})
        self.assertEqual([row['pk'] for row in response.context['page_obj']], [restricted.pk])
        self.assertNotContains(response, unrestricted.name)
        self.assertEqual(self.client.get(reverse('announcements:detail', args=[other.pk])).status_code, 200)

    def test_private_programs_do_not_leak_through_filter_options_and_invalid_filters_are_safe(self):
        self.publish(self.program_notice())
        private = create_program(name='Unannounced program', assistance_type='Private category')
        self.program_notice(private)
        response = self.client.get(self.list_url, {'category': 'programs', 'disability': 'not-an-id',
                                                   'program_category': 'Private category', 'page': 'bad'})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Private category')
        self.assertNotContains(response, private.name)
        self.assertEqual(response.context['disability'], '')

    def test_linking_and_editing_program_notices_requires_program_permission(self):
        with self.assertRaises(ValidationError):
            save_announcement(user=self.editor, data={**self.data, 'category': 'programs',
                                                      'linked_program': self.program.pk})
        item = self.program_notice()
        with self.assertRaises(PermissionDenied):
            save_announcement(user=self.editor, pk=item.pk, data={**self.data, 'version': item.version})
        self.client.force_login(self.editor)
        self.assertEqual(self.client.get(reverse('announcements:edit', args=[item.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('announcements:manage_detail', args=[item.pk])).status_code, 403)
        grant(self.editor, 'programs.view_program')
        self.editor = get_user_model().objects.get(pk=self.editor.pk)
        saved = save_announcement(user=self.editor, data={**self.data, 'category': 'programs',
                                                        'linked_program': self.program.pk})
        with self.assertRaises(PermissionDenied):
            change_publication(saved.pk, user=self.editor, version=saved.version, action='published')

    def test_result_category_cannot_be_forged_or_combined_with_a_program_preview(self):
        with self.assertRaises(ValidationError):
            self.draft(category='results')
        item = self.draft(program=self.program.pk, result_revision='999')
        self.assertEqual(item.category, 'general')
        self.assertIsNone(item.result_revision_id)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Announcement.objects.create(title='Invalid', content='Invalid', program=self.program,
                                        linked_program=self.program)

    def test_audit_failure_rolls_back_link_source_and_publication(self):
        item = self.publish(self.draft())
        with patch('announcements.services.record_event', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                save_announcement(user=self.admin, pk=item.pk, data={**self.data,
                    'version': item.version, 'category': 'programs', 'linked_program': self.program.pk})
        item.refresh_from_db()
        self.assertEqual(item.status, 'published')
        self.assertEqual(item.category, 'general')
        self.assertEqual(item.source_office, self.data['source_office'])

    def test_admin_categories_search_and_explicit_review_confirmation(self):
        item = self.program_notice()
        self.client.force_login(self.admin)
        response = self.client.get(reverse('announcements:manage_notices'),
                                   {'category': 'programs', 'q': self.program.name})
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertContains(response, 'Prepare and publish program results')
        response = self.client.post(reverse('announcements:manage_detail', args=[item.pk]),
                                   {'version': item.version, 'action': 'published'})
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.status, 'draft')
        self.assertContains(response, 'I reviewed these results and authorize publication with names masked on the public website.')
