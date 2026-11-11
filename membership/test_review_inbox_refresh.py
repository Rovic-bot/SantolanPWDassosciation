"""PDAO status navigation stays private, read-only and true to forwarding state."""
from django.test import TestCase, override_settings
from django.urls import reverse

from . import pdao_services as services
from .pdao_models import PDAORegistration, PDAORegistrationEvent
from .test_pdao_registration import PDAOHelpers, actor


@override_settings(PDAO_REGISTRATION_ENABLED=True)
class PDAOInboxStatusTests(PDAOHelpers, TestCase):
    def test_status_tabs_count_search_matches_and_preserve_processing_state(self):
        item, _ = self.submit()
        user = actor(services.VIEW, services.FORWARD)
        self.client.force_login(user)
        url = reverse('membership:pdao_inbox')
        for status in ('received', 'ready', 'forwarded'):
            if status != 'received':
                services.transition(item.pk, user, {'version': 0 if status == 'ready' else 1,
                    'action': status, 'confirmed': 'on'})
            before = list(PDAORegistration.objects.values()), list(PDAORegistrationEvent.objects.values())
            response = self.client.get(url, {'q': 'Fictional', 'state': status})
            self.assertEqual(list(response.context['page_obj']), [item])
            counts = {tab['value']: tab['count'] for tab in response.context['status_tabs']}
            self.assertEqual(counts, {'': 1, 'received': int(status == 'received'),
                'ready': int(status == 'ready'), 'forwarded': int(status == 'forwarded')})
            empty = self.client.get(url, {'q': 'No such applicant', 'state': status})
            self.assertEqual(empty.context['page_obj'].paginator.count, 0)
            self.assertTrue(all(tab['count'] == 0 for tab in empty.context['status_tabs']))
            self.assertEqual(before, (list(PDAORegistration.objects.values()), list(PDAORegistrationEvent.objects.values())))
            self.assertIn('no-store', response['Cache-Control'])
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
