from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from documents.services import file_digest, verify_document
from ewaf.operational_testsupport import OperationalHelpers
from members.models import DisabilityType
from membership.tests import grant

templates = deepcopy(settings.TEMPLATES)
templates[0]['DIRS'].insert(0, Path(__file__).parent / 'templates')


@override_settings(ROOT_URLCONF='main_testing.urls', TEMPLATES=templates,
                   INSTALLED_APPS=[*settings.INSTALLED_APPS, 'main_testing'])
class TestingReviewTests(OperationalHelpers, TestCase):
    def setUp(self):
        self.setup_operational()
        self.client.force_login(self.officer)
        self.app_url = reverse('programs:application_detail', args=[self.program.pk, self.application.pk])
        self.url = reverse('documents:review', args=[self.document.pk]) + '?application=' + str(self.application.pk)

    def values(self, **changes):
        current = self.document.verifications.first()
        return {'member_version': self.member.version, 'review_id': current.pk if current else 0,
                'document_digest': file_digest(self.document), 'verified': 'yes', 'expires_on': '',
                'reason': 'Fictional manual re-review of current evidence.', **changes}

    def test_verified_document_has_working_review_link_and_return(self):
        response = self.client.get(self.app_url)
        self.assertContains(response, self.url)
        self.assertContains(response, f'id="review-document-{self.document.pk}"')
        self.assertNotContains(response, 'data-document-review-form')
        detail = self.client.get(self.url)
        self.assertContains(detail, 'Save document review')
        self.assertContains(detail, self.app_url + '#documents')
        self.assertContains(detail, 'Review history')

    def test_re_review_appends_history_and_rejects_retry_with_stale_token(self):
        original = self.document.verifications.first()
        count = self.document.verifications.count()
        data = self.values(verified='no')
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(self.document.verifications.count(), count + 1)
        self.assertFalse(self.document.verifications.first().verified)
        original.refresh_from_db()
        self.assertTrue(original.verified)
        response = self.client.post(self.url, data)
        self.assertContains(response, 'This document or its review changed.')
        self.assertEqual(self.document.verifications.count(), count + 1)

    def test_invalid_expiry_digest_member_version_and_reason_do_not_write(self):
        before = self.document.verifications.count()
        for change in ({'expires_on': str(timezone.localdate()-timedelta(days=1))},
                       {'document_digest': '0'*64}, {'member_version': self.member.version+1}, {'reason': ''}):
            self.assertEqual(self.client.post(self.url, self.values(**change)).status_code, 200)
            self.assertEqual(self.document.verifications.count(), before)

    def test_document_review_permissions_csrf_and_application_binding(self):
        viewer = get_user_model().objects.create_user('fictional_review_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'members.view_member', 'documents.view_membershipapplicationdocument')
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.values()).status_code, 403)
        self.assertEqual(Client().get(self.url).status_code, 302)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.officer)
        self.assertEqual(csrf.post(self.url, self.values()).status_code, 403)
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(self.url.replace(str(self.application.pk), 'invalid')).status_code, 404)

    def test_relevance_matches_any_registered_type_and_is_separate_from_requirements(self):
        from programs.services import disability_matches
        self.program.eligible_disability_types.set(self.member.disability_ids)
        self.assertTrue(disability_matches(self.program, self.member))
        response = self.client.get(self.app_url)
        self.assertContains(response, 'Program relevance — disability match')
        self.assertContains(response, 'data-program-relevance>Matches')
        self.assertContains(response, 'Additional program requirements')
        self.assertNotContains(response, '>Program Fit / Consent</h2>')
        other = DisabilityType.objects.create(name='Fictional nonmatching classification')
        self.program.eligible_disability_types.set([other])
        self.assertContains(self.client.get(self.app_url), 'data-program-relevance>Does not match')
        self.program.eligible_disability_types.clear()
        self.assertContains(self.client.get(self.app_url), 'data-program-relevance>No disability-type restriction')

    def test_stale_requirement_review_shows_next_step_instead_of_unusable_form(self):
        from assistance.services import review_eligibility
        from assistance.tests import review_data
        data = review_data(self.application)
        data.update(eligibility='review', other_requirements='review')
        review_eligibility(self.application.pk, user=self.officer, data=data)
        response = self.client.get(self.app_url)
        self.assertContains(response, 'Save the program requirement checklist first.')
        self.assertContains(response, 'Requirement review reason')
        self.assertNotContains(response, 'Save additional requirement review</button>')
        self.assertNotContains(response, 'PR_REQUIREMENTS_STALE')

    def test_current_requirement_review_exposes_additional_review_form(self):
        response = self.client.get(self.app_url)
        self.assertContains(response, 'Save additional requirement review</button>')
        self.assertNotContains(response, 'Save the program requirement checklist first.')

    def test_old_calculation_is_retained_and_becomes_stale_after_document_review(self):
        from django.core.exceptions import ValidationError
        from ewaf import operational_services as service
        self.lock_policy()
        run = self.calculate()
        saved = deepcopy(run.payload())
        self.assertEqual(self.client.post(self.url, self.values(verified='no')).status_code, 302)
        with self.assertRaises(ValidationError):
            with service.fence(self.program.pk, self.officer) as (actor, program, applications):
                service._current(program, applications, actor, run.pk)
        run.refresh_from_db()
        self.assertEqual(saved, run.payload())
