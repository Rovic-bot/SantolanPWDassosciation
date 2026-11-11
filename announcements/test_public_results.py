"""Public Results uses current authorized revisions, never private history."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from assistance.services import review_eligibility, decide_assistance
from assistance.tests import seed_statuses, review_data, decision_data
from members.tests import create_member
from programs.models import ProgramApplication
from programs.tests import create_program
from programs.testsupport import private_media, application_fixture, close_non_ewaf_program, verified_photo
from .models import Announcement, ProgramResultRevision
from .results import prepare_results
from .services import change_publication


class PublicResultsTests(TestCase):
    def setUp(self):
        private_media(self)
        seed_statuses()
        self.admin = get_user_model().objects.create_superuser('public_result_admin')
        self.program = create_program(eligible_disability_types=[], slots=2)
        self.member = create_member('SYNTHETIC-RESULT-001')
        self.member.full_name = 'Juan Dela Cruz'
        self.member.save()
        self.application = application_fixture(self.program, self.member)
        review_eligibility(self.application.pk, user=self.admin, data=review_data(self.application))
        close_non_ewaf_program(self.program)
        decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))
        self.list_url = reverse('core:announcements') + '?category=results'

    def draft(self, version=0):
        return prepare_results(self.program.pk, user=self.admin, version=version,
                               reason='Synthetic private revision reason; never public.')

    def publish(self, item):
        return change_publication(item.pk, user=self.admin, version=item.version, action='published')

    def detail_url(self, item):
        return reverse('core:result_detail', args=[item.pk])

    def assert_withheld(self, item):
        self.assertNotContains(self.client.get(self.list_url), self.program.name)
        self.assertEqual(self.client.get(self.detail_url(item)).status_code, 404)
        self.assertEqual(self.client.get(reverse('announcements:detail', args=[item.pk])).status_code, 404)

    def test_empty_results_and_closed_applications_do_not_publish_automatically(self):
        response = self.client.get(self.list_url)
        self.assertContains(response, 'No announcements match this view.')
        self.assertNotContains(response, 'Looking for program results?')
        self.assertNotContains(response, 'href="/results/"')
        self.assertEqual(self.client.get('/results/').status_code, 404)
        self.assertEqual(self.client.head('/results/').status_code, 404)
        self.assertContains(response, reverse('core:contact'))
        self.assertFalse(Announcement.objects.exists())
        self.assertEqual(self.client.head(self.list_url).status_code, 200)
        self.assertEqual(self.client.post(self.list_url).status_code, 405)
        self.assertIn('no-store', response['Cache-Control'])

    def test_draft_is_not_public_even_for_a_logged_in_administrator(self):
        item = self.draft()
        self.assert_withheld(item)
        self.client.force_login(self.admin)
        self.assert_withheld(item)

    def test_result_details_keep_projection_while_notice_only_links_to_results(self):
        item = self.publish(self.draft())
        board = reverse('core:announcements')
        for category in ('', 'results'):
            rows = self.client.get(board, {'category': category}).context['page_obj']
            self.assertEqual([row['pk'] for row in rows], [item.pk])
        self.assertEqual(self.client.get(board, {'category': 'announcements'}).context['page_obj'].paginator.count, 0)
        response = self.client.get(self.detail_url(item))
        self.assertContains(response, 'J*** D*** C***')
        self.assertContains(response, '****' + self.application.public_reference[-4:])
        self.assertContains(response, 'Eligible applicants')
        self.assertContains(response, 'Approved selection method')
        self.assertContains(response, reverse('core:contact'))
        result = response.context['result']
        self.assertIsInstance(result, dict)
        self.assertEqual(set(result), {'pk', 'published_at', 'public_payload'})
        self.assertEqual(result['public_payload'], item.result_revision.public_payload)
        notice = self.client.get(reverse('announcements:detail', args=[item.pk]))
        popup = self.client.get(reverse('announcements:detail', args=[item.pk]), {'popup': '1'})
        self.assertTemplateUsed(popup, 'announcements/public_popup.html')
        self.assertContains(popup, f'href="{self.detail_url(item)}"')
        self.assertContains(notice, f'href="{self.detail_url(item)}"')
        self.assertNotIn('result_revision', notice.context['announcement'])
        self.assertNotContains(notice, 'J*** D*** C***')
        self.assertNotContains(notice, '****' + self.application.public_reference[-4:])
        self.assertEqual(notice.context['announcement']['category'], 'results')
        for value in (self.member.full_name, self.member.control_number, self.member.contact_number,
                      str(self.member.birthdate), self.member.address, self.member.disability_information,
                      self.application.public_reference, self.application.status_token,
                      str(self.application.pk), item.result_revision.source_digest, item.result_revision.reason):
            self.assertNotContains(response, value)
            self.assertNotContains(notice, value)
            self.assertNotContains(popup, value)
        for key in ('previous_announcement', 'creator_label', 'source_digest', 'reason', 'applicant_rows', 'score', 'rank'):
            self.assertNotIn(key, result['public_payload'])
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(self.client.head(self.detail_url(item)).status_code, 200)
        self.assertEqual(self.client.post(self.detail_url(item)).status_code, 405)

    def test_listing_excludes_general_announcements_and_legacy_unreviewed_applicant_lists(self):
        Announcement.objects.create(title='Synthetic general notice', content='General content',
                                    status='published', published_at=timezone.now())
        legacy = Announcement.objects.create(program=self.program, title='Legacy private applicant list',
            content=self.member.full_name, applicant_rows=[{'name': self.member.full_name}],
            status='published', published_at=timezone.now())
        self.assert_withheld(legacy)
        self.assertNotContains(self.client.get(self.list_url), 'Synthetic general notice')

    def test_withdraw_archive_and_delete_remove_results_and_compatible_notice(self):
        item = self.publish(self.draft())
        for action in ('draft', 'archived', 'deleted'):
            item = change_publication(item.pk, user=self.admin, version=item.version, action=action)
            self.assert_withheld(item)
            if action != 'deleted':
                item = self.publish(item)
                self.assertEqual(self.client.get(self.detail_url(item)).status_code, 200)
        self.assertEqual(ProgramResultRevision.objects.count(), 1)

    def test_source_invalidation_hides_every_public_destination(self):
        item = self.publish(self.draft())
        self.member.version += 1
        self.member.save()
        self.assert_withheld(item)
        self.assertNotContains(self.client.get(reverse('core:announcements')), item.title)
        self.assertNotContains(self.client.get(reverse('core:home')), item.title)

    def test_ewaf_dependent_or_no_longer_public_program_results_are_withheld(self):
        item = self.publish(self.draft())
        for changes in ({'ewaf_applicable': True}, {'status': 'archived'},
                        {'published_at': timezone.now() + timezone.timedelta(days=1)}):
            with self.subTest(changes=changes):
                original = {key: getattr(self.program, key) for key in changes}
                for key, value in changes.items():
                    setattr(self.program, key, value)
                self.program.save(update_fields=list(changes))
                self.assert_withheld(item)
                for key, value in original.items():
                    setattr(self.program, key, value)
                self.program.save(update_fields=list(original))

    def test_future_publication_date_is_not_visible(self):
        item = self.publish(self.draft())
        item.published_at = timezone.now() + timezone.timedelta(days=1)
        item.save(update_fields=['published_at'])
        self.assert_withheld(item)

    def test_preparing_new_revision_withholds_old_and_exposes_only_reauthorized_current_revision(self):
        item = self.publish(self.draft())
        old = item.result_revision
        item = self.draft(item.version)
        self.assert_withheld(item)
        self.assertEqual(self.client.get(f'/results/revisions/{old.pk}/').status_code, 404)
        item = self.publish(item)
        response = self.client.get(self.detail_url(item))
        self.assertEqual(response.context['result']['public_payload'], item.result_revision.public_payload)
        self.assertNotContains(response, old.reason)
        self.assertEqual(item.result_revisions.count(), 2)

    def test_corrupted_payload_or_revision_from_another_announcement_cannot_leak(self):
        item = self.publish(self.draft())
        revision = item.result_revision
        ProgramResultRevision.objects.filter(pk=revision.pk).update(
            public_payload={**revision.public_payload, 'raw_income': 'SYNTHETIC-PRIVATE-VALUES'})
        self.assert_withheld(item)
        ProgramResultRevision.objects.filter(pk=revision.pk).update(public_payload=revision.public_payload)
        unrelated = Announcement.objects.create(title='Other draft', content='Other')
        ProgramResultRevision.objects.filter(pk=revision.pk).update(announcement=unrelated)
        self.assert_withheld(item)

    def test_result_details_and_notices_have_announcements_active(self):
        item = self.publish(self.draft())
        for route, expected in ((self.list_url, 'Announcements'), (self.detail_url(item), 'Announcements'),
                                (reverse('announcements:detail', args=[item.pk]), 'Announcements')):
            html = self.client.get(route).content.decode()
            nav = html.split('aria-label="Main navigation"', 1)[1].split('</nav>', 1)[0]
            self.assertEqual(nav.count('aria-current="page"'), 1)
            active = nav.split('aria-current="page"', 1)[1].split('</a>', 1)[0]
            self.assertIn('>' + expected, active)

    def test_approved_payload_text_is_escaped_and_masks_do_not_promise_unique_identity(self):
        self.program.description = '<script>synthetic()</script>'
        self.program.save(update_fields=['description'])
        other_member = create_member('SYNTHETIC-RESULT-002')
        other_member.full_name = 'Jose Dela Cruz'
        other_member.save()
        other = ProgramApplication.objects.create(program=self.program, member=other_member,
            public_reference='OLD-' + self.application.public_reference[-4:])
        verified_photo(other)
        review_eligibility(other.pk, user=self.admin, data=review_data(other))
        decide_assistance(other.pk, user=self.admin, data=decision_data(other))
        item = self.publish(self.draft())
        response = self.client.get(self.detail_url(item))
        self.assertContains(response, 'Similar entry')
        self.assertContains(response, 'not proof of identity')
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>synthetic()</script>')
        self.assertNotContains(response, other_member.full_name)
        self.assertNotContains(response, other.public_reference)

    def test_previous_authorized_publications_are_listed_by_publication_date_not_revision_history(self):
        item = self.publish(self.draft())
        item.published_at = timezone.now() - timezone.timedelta(days=100)
        item.save(update_fields=['published_at'])
        response = self.client.get(self.list_url, {'category': 'results', 'page': 'invalid',
                                                  'reference': self.application.public_reference})
        self.assertContains(response, self.program.name)
        self.assertContains(response, f'href="{reverse("announcements:detail", args=[item.pk])}"')
        self.assertNotContains(response, self.application.public_reference)
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertEqual(response.context['page_obj'][0]['destination'], self.detail_url(item))
        self.assertNotIn('public_payload', response.context['page_obj'][0])

    def test_announcement_search_uses_public_result_text_without_indexing_private_metadata(self):
        item = self.publish(self.draft())
        Announcement.objects.filter(pk=item.pk).update(content='PRIVATE-LEGACY-NOTICE-CONTENT')
        url = reverse('core:announcements')
        for query in (item.title, self.program.description):
            response = self.client.get(url, {'q': query, 'category': 'results'})
            self.assertEqual(response.context['page_obj'].paginator.count, 1)
            self.assertContains(response, f'href="{reverse("announcements:detail", args=[item.pk])}"')
            self.assertNotContains(response, 'PRIVATE-LEGACY-NOTICE-CONTENT')
            self.assertNotIn('public_payload', response.context['page_obj'][0])
        for query in ('PRIVATE-LEGACY-NOTICE-CONTENT', self.member.full_name,
                self.application.public_reference, item.result_revision.reason, item.result_revision.source_digest):
            with self.subTest(query=query):
                response = self.client.get(url, {'q': query})
                self.assertEqual(response.context['page_obj'].paginator.count, 0)
        self.member.version += 1
        self.member.save()
        response = self.client.get(url, {'q': item.title})
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
