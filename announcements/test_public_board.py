from urllib.parse import parse_qs, urlsplit

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from programs.tests import create_program
from .models import Announcement


@override_settings(PDAO_ENFORCEMENT_ENABLED=False)
class PublicAnnouncementBoardTests(TestCase):
    def notice(self, **changes):
        return Announcement.objects.create(**{'title': 'Community bulletin', 'content': 'Association news.',
            'source_office': 'Barangay Santolan', 'status': 'published', 'published_at': timezone.now(), **changes})

    def listing(self, **params):
        response = self.client.get(reverse('core:announcements'), params)
        self.assertEqual(response.status_code, 200)
        return response

    def test_notice_batches_order_by_publication_date_with_working_detail_links(self):
        now = timezone.now()
        notices = [self.notice(title=f'Bulletin {index}', published_at=now - timezone.timedelta(days=index))
            for index in range(27)]
        response = self.listing()
        self.assertEqual([row['pk'] for row in response.context['page_obj']], [row.pk for row in notices[:24]])
        self.assertContains(response, 'class="notice-row"', count=24)
        self.assertContains(response, 'data-swipe-rows="1"')
        self.assertContains(response, 'Browse by topic')
        self.assertContains(response, 'Read more')
        self.assertNotContains(response, 'Go to Results')
        self.assertNotContains(response, 'notice-results-callout')
        self.assertContains(response, reverse('core:announcements') + '?category=results')
        self.assertContains(response, reverse('announcements:detail', args=[notices[0].pk]))
        self.assertContains(response, 'aria-label="Search announcements"')
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(len(self.listing(page=2).context['page_obj']), 3)

    def test_search_topic_and_pagination_preserve_filters_and_reset_pages_for_topics(self):
        for index in range(26):
            self.notice(title=f'News & access {index}')
        self.notice(title='Unrelated notice')
        response = self.listing(q='News & access', category='announcements')
        params = parse_qs(urlsplit(response.context['next_page_url']).query)
        self.assertEqual(params, {'category': ['announcements'], 'q': ['News & access'], 'page': ['2']})
        second = self.client.get(response.context['next_page_url'])
        self.assertEqual(len(second.context['page_obj']), 1)
        for topic in second.context['topic_links']:
            params = parse_qs(urlsplit(topic['url']).query)
            self.assertNotIn('page', params)
            self.assertEqual(params['q'], ['News & access'])

    def test_search_excludes_private_and_future_notices_and_handles_empty_results(self):
        visible = self.notice(content='A published accessibility workshop.')
        self.notice(title='Hidden accessibility note', status='draft')
        self.notice(title='Future accessibility note', published_at=timezone.now() + timezone.timedelta(days=1))
        response = self.listing(q='accessibility')
        self.assertEqual([row['pk'] for row in response.context['page_obj']], [visible.pk])
        response = self.listing(q='<script>not-a-notice</script>')
        self.assertContains(response, 'No announcements match your search.')
        self.assertNotContains(response, '<script>not-a-notice</script>')
        self.assertContains(response, 'Clear filters')

    def test_program_search_uses_current_public_content_instead_of_unused_notice_copies(self):
        program = create_program(name='Mobility support', description='Current program overview.')
        notice = self.notice(linked_program=program, title='UNUSED-PRIVATE-COPY', content='UNUSED-OLD-DESCRIPTION')
        response = self.listing(q='Mobility', category='programs')
        self.assertEqual([row['pk'] for row in response.context['page_obj']], [notice.pk])
        self.assertContains(response, reverse('programs:detail', args=[program.pk]))
        self.assertNotContains(response, 'data-public-popup data-popup-label')
        popup = self.client.get(reverse('announcements:detail', args=[notice.pk]), {'popup': '1'})
        self.assertContains(popup, reverse('programs:detail', args=[program.pk]))
        self.assertNotContains(response, 'UNUSED-PRIVATE-COPY')
        for query in ('UNUSED-PRIVATE-COPY', 'UNUSED-OLD-DESCRIPTION'):
            self.assertEqual(self.listing(q=query).context['page_obj'].paginator.count, 0)

    def test_three_topics_combine_general_and_program_notices_without_obsolete_filters(self):
        general = self.notice()
        program = create_program(name='Mobility support')
        linked = self.notice(linked_program=program)
        for category in ('announcements', 'general', 'programs'):
            with self.subTest(category=category):
                response = self.listing(category=category, disability='obsolete', program_category='obsolete')
                self.assertEqual(response.context['category'], 'announcements')
                self.assertEqual(response.context['page_obj'].paginator.count, 2)
                self.assertEqual(len(response.context['page_obj']), 1)
                second = self.listing(category=category, page=2)
                self.assertEqual({response.context['page_obj'][0]['pk'], second.context['page_obj'][0]['pk']}, {general.pk, linked.pk})
                self.assertEqual([topic['label'] for topic in response.context['topic_links']],
                                 ['All', 'Announcements', 'Program Results'])
                self.assertNotContains(response, 'name="disability"')
                self.assertNotContains(response, 'name="program_category"')
        self.assertEqual(self.listing(category='results').context['page_obj'].paginator.count, 0)

    def test_combined_announcements_still_withhold_unpublished_program_information(self):
        program = create_program(name='Private program')
        program.status = 'draft'
        program.save(update_fields=['status'])
        self.notice(linked_program=program)
        self.assertEqual(self.listing(category='announcements').context['page_obj'].paginator.count, 0)

    def test_invalid_topic_and_page_fall_back_without_echoing_unknown_values(self):
        notice = self.notice()
        response = self.listing(category='unknown-topic', page='invalid')
        self.assertEqual(response.context['category'], '')
        self.assertEqual(response.context['page_obj'].number, 1)
        self.assertEqual(response.context['page_obj'][0]['pk'], notice.pk)
        self.assertNotContains(response, 'unknown-topic')
