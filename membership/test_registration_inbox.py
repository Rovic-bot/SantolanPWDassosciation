"""Synthetic inbox queries; no changes to membership decision authority."""
from html import unescape
from urllib.parse import parse_qs, urlsplit
import re

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from scripts.durable_test_runner import require_disposable
from . import registration_services as services
from .models import MembershipApplication, MembershipEvent
from .registration_models import RegistrationIntake, RegistrationRevision, RegistrationAction
from .test_pdf_registration import association_data
from .test_registration_decisions import DecisionHelpers
from .test_registration_intake import staff
from .tests import grant


class RegistrationInboxTests(DecisionHelpers, TestCase):
    def setUp(self):
        require_disposable()
        self.setup_decisions()
        self.pending = self.make_named('Waiting')
        self.approved = self.make_named('Approved')
        self.rejected = self.make_named('Declined')
        self.decide(self.approved, self.data(self.approved, first_name='Approved'))
        self.decide(self.rejected, self.data(self.rejected,
            first_name='Declined', action='decline_registration', pwd_number=''))
        self.url = reverse('membership:registration_inbox')
        self.client.force_login(self.actor)

    def make_named(self, name):
        binding = services.binding_for('synthetic-inbox-' + name)
        context = services.issue_context(binding)
        return services.submit_registration(context.pk, binding,
            association_data() | {'first_name': name, 'pwd_number': '00-0000-000-0000001'})

    def test_tabs_use_actual_decisions_and_show_counts_without_changing_records(self):
        models = (RegistrationIntake, RegistrationRevision, RegistrationAction,
                  MembershipApplication, MembershipEvent)
        before = [list(model.objects.order_by('pk').values()) for model in models]
        response = self.client.get(self.url)
        self.assertEqual(list(response.context['page_obj']), [self.pending])
        self.assertEqual(response.context['tab_counts'], {'all': 3, 'awaiting': 1, 'completed': 2})
        self.assertContains(response, 'Awaiting onsite')
        response = self.client.get(self.url, {'tab': 'completed'})
        rows = list(response.context['page_obj'])
        self.assertEqual({row.pk for row in rows}, {self.approved.pk, self.rejected.pk})
        self.assertEqual({row.inbox_status for row in rows}, {'Approved', 'Rejected'})
        self.assertTrue(all(row.inbox_completed for row in rows))
        self.assertEqual(self.client.get(self.url, {'tab': 'all'}).context['page_obj'].paginator.count, 3)
        self.assertEqual(before, [list(model.objects.order_by('pk').values()) for model in models])

    def test_name_search_uses_current_revision_and_does_not_duplicate_rows(self):
        services.correct_registration(self.pending.reference, user=self.actor, version=0,
            reason='Synthetic name correction', data=association_data() | {'first_name': 'Corrected'})
        self.assertEqual(self.client.get(self.url, {'q': 'Waiting'}).context['page_obj'].paginator.count, 0)
        response = self.client.get(self.url, {'q': 'cOrReCtEd'})
        self.assertEqual(list(response.context['page_obj']), [self.pending])
        self.assertContains(response, 'Corrected Example')
        self.assertEqual(response.context['tab_counts']['all'], 1)
        response = self.client.get(self.url, {'q': 'example', 'tab': 'completed'})
        self.assertEqual(response.context['page_obj'].paginator.count, 2)
        self.assertEqual(response.context['tab_counts']['all'], 3)

    def test_complete_reference_finds_final_decision_despite_stale_filters(self):
        for key in ('reference', 'q'):
            response = self.client.get(self.url, {key: self.approved.reference.upper(),
                'state': 'received', 'channel': 'walk_in', 'tab': 'awaiting'})
            self.assertEqual(list(response.context['page_obj']), [self.approved])
            self.assertEqual(response.context['active_tab'], 'all')
            self.assertContains(response, 'Exact reference search takes precedence')
            self.assertEqual(response.context['page_obj'][0].inbox_status, 'Approved')
        response = self.client.get(self.url, {'q': 'AMR-'})
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        self.assertContains(response, 'No accessible registration matches')
        self.assertNotContains(response, self.pending.reference)

    def test_filters_and_invalid_values_do_not_broaden_search(self):
        response = self.client.get(self.url, {'q': 'waiting', 'channel': 'online'})
        self.assertEqual(list(response.context['page_obj']), [self.pending])
        self.assertEqual(response.context['tab_counts']['completed'], 0)
        for params in ({'state': 'unlisted'},
                       {'tab': 'unlisted'}, {'q': 'nonexistent'}):
            with self.subTest(params=params):
                self.assertEqual(self.client.get(self.url, params).context['page_obj'].paginator.count, 0)

    def test_retired_channel_filter_cannot_silently_hide_applications(self):
        for channel in ('online', 'walk_in', 'printed', 'unlisted'):
            with self.subTest(channel=channel):
                response = self.client.get(self.url, {'tab': 'all', 'channel': channel})
                self.assertEqual(response.context['page_obj'].paginator.count, 3)
                self.assertNotContains(response, 'name="channel"')
                self.assertNotContains(response, 'channel=')

    def test_pagination_preserves_search_tab_and_filters(self):
        for index in range(21):
            self.make_named('Pagination ' + str(index))
        response = self.client.get(self.url, {'q': 'Pagination', 'tab': 'awaiting', 'channel': 'online'})
        self.assertEqual(response.context['page_obj'].paginator.count, 21)
        link = re.search(r'href="([^"]+)">Next</a>', response.content.decode()).group(1)
        query = parse_qs(urlsplit(unescape(link)).query)
        self.assertEqual(query, {'q': ['Pagination'], 'tab': ['awaiting'], 'page': ['2']})
        next_page = self.client.get(self.url + unescape(link))
        self.assertEqual(len(next_page.context['page_obj']), 1)
        self.assertNotEqual(response.context['page_obj'][0].pk, next_page.context['page_obj'][0].pk)

    def test_search_is_escaped_and_read_only_and_encoding_links_are_permission_scoped(self):
        self.assertNotContains(self.client.get(self.url), 'Record walk-in intake')
        encoder = staff('synthetic_inbox_encoder', 'membership.encode_registrationintake')
        self.client.force_login(encoder)
        self.assertContains(self.client.get(self.url), 'Record walk-in intake')
        self.assertNotContains(self.client.get(self.url), 'Record printed form')
        response = self.client.get(self.url, {'q': '<script>alert(1)</script>'})
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.assertIn('no-store', response['Cache-Control'])
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        restricted = get_user_model().objects.create_user('synthetic_inbox_restricted', is_staff=True)
        grant(restricted, 'accounts.access_dashboard', 'membership.view_membershipapplication')
        self.client.force_login(restricted)
        self.assertEqual(self.client.get(self.url, {'q': 'Example'}).status_code, 403)
