from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError
from unittest.mock import patch

from assistance.tests import review_data
from ewaf.models import CriterionAssessment
from ewaf.operational_testsupport import OperationalHelpers
from membership.tests import grant
from programs.models import ProgramRequirement
from programs.tests import create_program
from programs.testsupport import application_fixture


class ChecklistNavigationTests(OperationalHelpers, TestCase):
    def setUp(self):
        self.setup_operational()
        grant(self.officer, 'membership.view_membershipapplication')
        self.client.force_login(self.officer)
        self.url = reverse('programs:application_detail', args=[self.program.pk, self.application.pk])

    def return_for_review(self):
        self.application.refresh_from_db()
        response = self.client.post(self.url, {'action': 'return_review', 'return-version': self.application.version,
            'return-decision': 'pending', 'return-notes': 'Fictional renewed evidence review.', 'return-confirm': 'on'})
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()

    def photo_data(self, **changes):
        self.application.refresh_from_db()
        return {'action': 'photo', 'version': self.application.version,
            'photo_id': str(self.application.current_photo_id), 'outcome': 'VERIFIED',
            'category': '', 'reason': 'Fictional officer checked identity evidence.', 'confirm': 'on', **changes}

    def test_submission_and_decision_replace_separate_panels_without_recording_verification(self):
        before = (self.application.assistance_history.count(), self.application.current_photo.reviews.count(),
                  CriterionAssessment.objects.count())
        response = self.client.get(self.url)
        expected = {'membership-review', 'photo-review', 'disability-review', 'documents', 'program-fit-review'}
        self.assertEqual({row['target'] for row in response.context['eligibility_checks']}, expected)
        for target in expected - {'documents'}:
            self.assertNotContains(response, f'id="{target}"')
        self.assertContains(response, 'id="documents"')
        self.assertContains(response, 'id="eligibility"')
        for old in ('requirements-dialog', 'photo-dialog', 'qualification-dialog'):
            self.assertNotContains(response, old)
        self.assertContains(response, 'Submitted application')
        self.assertEqual(response.context['membership_intake'].pk, self.member.application_id)
        self.assertEqual(before, (self.application.assistance_history.count(), self.application.current_photo.reviews.count(),
                                 CriterionAssessment.objects.count()))

    def test_photo_correction_and_verification_refresh_status_and_keep_history(self):
        self.return_for_review()
        old_reviews = list(self.application.current_photo.reviews.values_list('pk', flat=True))
        for outcome, status in [('NEEDS_RESUBMISSION', 'Needs review'), ('VERIFIED', 'Verified')]:
            response = self.client.post(self.url, self.photo_data(outcome=outcome, category='Fictional correction'), follow=True)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['photo_status'], status)
            current = self.application.current_photo.reviews.first()
            self.assertEqual(current.outcome, outcome)
            self.assertEqual(current.reviewer_id, self.officer.pk)
        self.assertEqual(self.application.current_photo.reviews.filter(pk__in=old_reviews).count(), len(old_reviews))
        self.assertEqual(self.application.current_photo.reviews.count(), len(old_reviews) + 2)

    def test_rejection_requires_reason_and_eligible_cannot_bypass_identity(self):
        self.return_for_review()
        count = self.application.current_photo.reviews.count()
        response = self.client.post(self.url, self.photo_data(outcome='REJECTED', category='', reason=''))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['photo_form'].errors)
        self.assertEqual(self.application.current_photo.reviews.count(), count)
        response = self.client.post(self.url, self.photo_data(outcome='REJECTED', category='Identity mismatch'), follow=True)
        self.assertEqual(response.context['photo_status'], 'Needs review')
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'VERIFICATION_FAILED')
        response = self.client.post(self.url, {**review_data(self.application), 'action': 'eligibility'})
        self.assertEqual(response.status_code, 200)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'VERIFICATION_FAILED')

    def test_disability_comparison_and_missing_optional_requirement_inventory(self):
        from members.models import DisabilityType
        other = DisabilityType.objects.create(name='Fictional other qualification')
        program = create_program(eligible_disability_types=[self.member.disability_type_id, other.pk])
        missing = ProgramRequirement.objects.create(program=program, label='Fictional required certificate', kind='document', is_required=True)
        optional = ProgramRequirement.objects.create(program=program, label='Fictional optional file', kind='document', is_required=False)
        app = application_fixture(program, self.member)
        from programs.forms import snapshot
        app.requirements_snapshot = snapshot(program)
        app.save(update_fields=['requirements_snapshot'])
        response = self.client.get(reverse('programs:application_detail', args=[program.pk, app.pk]))
        self.assertEqual({row['status'] for row in response.context['disability_comparison']}, {'Matches', 'Does not match'})
        rows = {row['id']: row for row in response.context['program_requirement_rows']}
        self.assertEqual(rows[missing.pk]['status'], 'Missing')
        self.assertEqual(rows[optional.pk]['status'], 'Not required')
        self.assertNotIn('qualification', {row['key'] for row in response.context['eligibility_checks']})
        response = self.client.post(reverse('programs:application_detail', args=[program.pk, app.pk]),
            {**review_data(app), 'action': 'eligibility', f'check_{missing.pk}': 'pass', f'check_{optional.pk}': 'review'})
        self.assertContains(response, 'no submission exists to validate')

    def test_restricted_users_have_no_evidence_or_review_controls(self):
        viewer = get_user_model().objects.create_user('checklist_viewer', is_staff=True)
        grant(viewer, 'accounts.access_dashboard', 'programs.view_program', 'programs.view_programapplication')
        self.client.force_login(viewer)
        response = self.client.get(self.url)
        self.assertEqual({row['status'] for row in response.context['eligibility_checks']}, {'Restricted'})
        for private in ('?preview=1', 'data-applicant-review-form', 'Onsite membership decision', 'name="qualification-evidence"'):
            self.assertNotContains(response, private)
        for action in ('photo', 'eligibility', 'qualification'):
            self.assertEqual(self.client.post(self.url, {'action': action}).status_code, 403)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.officer)
        self.assertEqual(protected.post(self.url, self.photo_data()).status_code, 403)
        self.assertEqual(Client().get(self.url).status_code, 302)

    def test_correction_link_retains_applicant_context_and_safe_return(self):
        self.return_for_review()
        route = reverse('programs:correction', args=[self.application.pk]) + '?return=applicant'
        self.assertContains(self.client.get(self.url), route)
        response = self.client.get(route)
        self.assertContains(response, self.url + '#documents')
        data = {name: response.context['form'][name].value() for name in response.context['form'].fields
                if name != 'calendar_photo' and response.context['form'][name].value() is not None}
        data.update(reason='Fictional correction to retained text evidence.')
        response = self.client.post(route, data)
        self.assertRedirects(response, self.url + '#documents')

    def test_program_fit_badge_respects_the_required_accepted_findings(self):
        self.lock_policy()
        with patch('ewaf.four_pool.eligibility', side_effect=ValidationError('Required consent is not satisfied.')):
            response = self.client.get(self.url)
        self.assertEqual(response.context['qualification_status'], 'Not met')
        self.assertEqual(response.context['review_result'], 'Review needed')
