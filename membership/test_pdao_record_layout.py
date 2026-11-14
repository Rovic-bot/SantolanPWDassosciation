from django.test import TestCase, override_settings
from django.urls import reverse

from . import pdao_services as services
from .test_pdao_registration import PDAOHelpers, actor
from .test_pdao_review import review_data


@override_settings(PDAO_REGISTRATION_ENABLED=True)
class PDAORecordLayoutTests(PDAOHelpers, TestCase):
    def test_read_only_record_has_complete_details_without_management_actions(self):
        item, _ = self.submit()
        self.client.force_login(actor(services.VIEW))
        response = self.client.get(reverse('membership:pdao_detail', args=[item.pk]))
        for text in ('Application overview', 'Application details', 'Processing history',
                     'Contact details', item.data['full_name']):
            self.assertContains(response, text)
        for text in ('Original applicant submission', 'Submission and review history', 'Other onsite applications', 'id="pdao-review-form"', 'id="pdao-forward-form"', 'Print or save PDF'):
            self.assertNotContains(response, text)
        for _, rows in item.data['profile_sections']:
            for label, _ in rows:
                self.assertContains(response, label)

    def test_invalid_edit_opens_editor_and_forwarded_record_stays_locked(self):
        item, _ = self.submit()
        staff = actor(services.VIEW, services.CORRECT, services.PRINT, services.FORWARD)
        self.client.force_login(staff)
        url = reverse('membership:pdao_detail', args=[item.pk])
        response = self.client.post(url, review_data(item, first_name=''))
        self.assertContains(response, 'id="pdao-review-form"', status_code=400)
        self.assertNotContains(response, 'id="pdao-editor"', status_code=400)
        self.assertContains(response, 'This field is required.', status_code=400)
        services.transition(item.pk, staff, {'version': 0, 'action': 'ready', 'ready_confirmed': 'on'})
        services.transition(item.pk, staff, {'version': 1, 'action': 'forwarded', 'confirmed': 'on'})
        response = self.client.get(url)
        self.assertContains(response, 'These details are now locked.')
        self.assertContains(response, 'Print or save PDF')
        self.assertNotContains(response, 'id="pdao-review-form"')
        self.assertNotContains(response, 'id="pdao-forward-form"')

    def test_retired_list_redirects_without_changing_or_disclosing_records(self):
        item, _ = self.submit()
        before = (item.data, item.reference, item.version)
        url = reverse('membership:list')
        self.assertEqual(self.client.get(url).status_code, 302)
        staff = actor(services.VIEW)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        from .tests import grant
        grant(staff, 'membership.view_membershipapplication')
        response = self.client.get(url, {'reference': 'do-not-forward', 'q': 'private search'})
        self.assertRedirects(response, reverse('membership:review_home'))
        self.assertEqual(self.client.post(url).status_code, 405)
        self.assertNotContains(self.client.get(reverse('membership:review_home')), url)
        item.refresh_from_db()
        self.assertEqual((item.data, item.reference, item.version), before)
