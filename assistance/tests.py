from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, close_old_connections, connections, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from programs.testsupport import close_non_ewaf_program, application_fixture, private_media, verified_photo
from membership.tests import pdf
from members.tests import create_member
from members.services import change_status
from membership.tests import grant
from programs.models import ProgramApplication, ProgramRequirement, ProgramDocument
from programs.tests import create_program, program_data
from programs.services import change_application, save_program
from .models import EligibilityStatus, AssistanceCase, AssistanceRelease, AssistanceLog
from .services import (VIEW_PERMISSIONS, review_eligibility, decide_assistance, record_release, void_release,
                       configure_status, previous_assistance_count, reserved_slots)


def seed_statuses():
    # TransactionTestCase flushes data migrations between tests.
    for code, label in EligibilityStatus.Code.choices:
        EligibilityStatus.objects.get_or_create(code=code, defaults={'label': label})


def create_application(program=None, member=None):
    return application_fixture(program or create_program(), member or create_member('ASSIST-001'))


def review_data(application, **overrides):
    application.refresh_from_db()
    return {'version': application.version, 'eligibility': 'eligible', 'other_requirements': 'pass',
            'member_version': application.member.version, 'program_version': application.program.version,
            **{f'check_{item["id"]}': 'review' for item in application.requirements_snapshot},
            'notes': 'Verified original requirements and active membership.', **overrides}


def decision_data(application, **overrides):
    application.refresh_from_db()
    return {'version': application.version, 'decision': 'approved', 'confirm': True, 'notes': 'Authorized human decision.', **overrides}


def release_data(application, **overrides):
    application.refresh_from_db()
    return {'version': application.version, 'assistance_type': 'Support', 'benefit': 'Delivered support',
            'amount': '500.00', 'estimated_value': '', 'released_on': str(timezone.localdate()),
            'reference': 'TEST-RECEIPT', 'notes': 'Confirmed actual receipt.', 'confirm': True, **overrides}


class AssistanceTests(TestCase):
    def setUp(self):
        private_media(self)
        seed_statuses()
        self.admin = get_user_model().objects.create_superuser('assistance_admin')
        self.viewer = get_user_model().objects.create_user('assistance_viewer', is_staff=True)
        grant(self.viewer, 'accounts.access_dashboard', *VIEW_PERMISSIONS)
        self.application = create_application()
        self.member = self.application.member
        self.program = self.application.program
        self.client.force_login(self.admin)
        self.detail = reverse('assistance:detail', args=[self.application.pk])

    def review(self, **overrides):
        return review_eligibility(self.application.pk, user=self.admin, data=review_data(self.application, **overrides))

    def approve(self, *, publish=True):
        self.review()
        close_non_ewaf_program(self.program, self.admin)
        case = decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))
        if publish:
            from announcements.testsupport import publish_selection
            publish_selection(self.program, self.admin)
        return case

    def release(self, **overrides):
        return record_release(self.application.pk, user=self.admin, data=release_data(self.application, **overrides))

    def void(self, release, **overrides):
        self.application.refresh_from_db()
        return void_release(self.application.pk, release.pk, user=self.admin,
            data={'version': self.application.version, 'notes': 'Incorrect release; correction required.', 'confirm': True, **overrides})

    def test_assessment_approval_release_and_void_counts(self):
        self.assertEqual(previous_assistance_count(self.member), 0)
        self.approve()
        self.assertEqual(previous_assistance_count(self.member), 0)
        release = self.release()
        self.assertEqual(previous_assistance_count(self.member), 1)
        self.assertEqual(release.approval_snapshot['decision'], 'approved')
        self.assertEqual(release.approval_snapshot['approved_by_label'], self.admin.username)
        self.void(release)
        self.assertEqual(previous_assistance_count(self.member), 0)
        self.assertEqual(reserved_slots(self.program), 0)
        self.assertEqual(AssistanceRelease.objects.count(), 1)
        self.approve()
        replacement = self.release(amount='600')
        self.assertNotEqual(release.pk, replacement.pk)
        self.assertEqual(previous_assistance_count(self.member), 1)
        self.assertEqual(AssistanceRelease.objects.count(), 2)
        self.assertEqual(AssistanceLog.objects.count(), 7)

    def test_events_pending_cancelled_and_rejected_never_count(self):
        self.review(eligibility='ineligible', other_requirements='fail')
        with self.assertRaises(ValidationError):
            decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application, decision='rejected'))
        change_application(self.application.pk, user=self.admin, version=decision_data(self.application)['version'], status='CLOSED', notes='Closed.')
        self.assertEqual(previous_assistance_count(self.member), 0)

    def test_required_original_items_must_exist_and_pass(self):
        requirement = ProgramRequirement.objects.create(program=self.program, label='Proof', kind='document')
        self.application.requirements_snapshot = [{'id': requirement.pk, 'label': 'Original proof', 'kind': 'document', 'is_required': True}]
        self.application.save()
        with self.assertRaisesMessage(ValidationError, 'no submission'):
            self.review(**{f'check_{requirement.pk}': 'pass'})
        ProgramDocument.objects.create(application=self.application, requirement=requirement, label='Original proof', file=pdf(), content_type='application/pdf', size=20)
        with self.assertRaisesMessage(ValidationError, 'every required'):
            self.review(**{f'check_{requirement.pk}': 'review'})
        requirement.is_active = False
        requirement.label = 'Changed for future submissions'
        requirement.save()
        case = self.review(**{f'check_{requirement.pk}': 'pass'})
        self.assertIn('Original proof', [item['label'] for item in case.checklist])

    def test_written_answers_and_acknowledgements_checked(self):
        self.application.requirements_snapshot = [{'id': 10, 'label': 'Answer', 'kind': 'text', 'is_required': True},
                                                  {'id': 11, 'label': 'Consent', 'kind': 'acknowledgement', 'is_required': True}]
        self.application.answers = {'10': 'A written answer', '11': False}
        self.application.save()
        with self.assertRaisesMessage(ValidationError, 'no submission'):
            self.review(check_10='pass', check_11='pass')
        self.application.answers['11'] = True
        self.application.save()
        self.review(check_10='pass', check_11='pass')

    def test_optional_unfulfilled_item_does_not_prevent_eligibility(self):
        self.application.requirements_snapshot = [{'id': 10, 'label': 'Optional', 'kind': 'text', 'is_required': False}]
        self.application.save()
        self.assertEqual(self.review().eligibility_id, 'eligible')

    def test_inactive_member_can_be_assessed_but_not_eligible(self):
        change_status(self.member.pk, user=self.admin, version=0, status='inactive', notes='Membership inactive.')
        with self.assertRaises(ValidationError):
            self.review()
        self.assertFalse(AssistanceCase.objects.exists())

    def test_no_release_without_approval_or_after_rejection(self):
        with self.assertRaisesMessage(ValidationError, 'approve assistance'):
            self.release()
        self.review()
        close_non_ewaf_program(self.program)
        decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application, decision='rejected'))
        with self.assertRaisesMessage(ValidationError, 'approve assistance'):
            self.release()

    def test_ineligible_review_pending_do_not_approve(self):
        for status in ['pending', 'review', 'ineligible']:
            self.review(eligibility=status, other_requirements='fail' if status == 'ineligible' else 'review')
            with self.assertRaises(ValidationError):
                decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))

    def test_reassessment_clears_approval_and_return_needs_new_assessment(self):
        self.approve()
        decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application, decision='pending'))
        self.assertEqual(self.review().decision, 'pending')
        close_non_ewaf_program(self.program, self.admin)
        decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))
        case = decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application, decision='pending'))
        self.assertEqual(case.eligibility_id, 'review')
        with self.assertRaises(ValidationError):
            decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))

    def test_member_or_program_changes_require_reassessment(self):
        self.review()
        self.member.version += 1
        self.member.save()
        with self.assertRaisesMessage(ValidationError, 'Photo Verification'):
            decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))
        verified_photo(self.application)
        self.approve()
        self.program.version += 1
        self.program.save()
        with self.assertRaisesMessage(ValidationError, 'changed after assessment'):
            self.release()

    def test_review_form_rejects_member_or_program_changed_since_opening(self):
        data = review_data(self.application)
        self.member.version += 1
        self.member.save()
        with self.assertRaisesMessage(ValidationError, 'Photo Verification'):
            review_eligibility(self.application.pk, user=self.admin, data=data)
        verified_photo(self.application)
        data = review_data(self.application)
        self.program.version += 1
        self.program.save()
        with self.assertRaisesMessage(ValidationError, 'while this form was open'):
            review_eligibility(self.application.pk, user=self.admin, data=data)

    def test_program_and_membership_availability_rechecked_at_release(self):
        self.approve()
        for status in ['draft', 'cancelled', 'archived']:
            self.program.status = status
            self.program.save()
            with self.assertRaisesMessage(ValidationError, 'published program'):
                self.release()
        self.program.status = 'published'
        self.program.save()
        self.member.is_active = False
        self.member.save()
        with self.assertRaisesMessage(ValidationError, 'Active membership'):
            self.release()

    def test_slots_limit_approvals_and_cannot_be_lowered_below_reservations(self):
        self.program.slots = 2
        self.program.save()
        self.approve(publish=False)
        other = create_application(self.program, create_member('ASSIST-002'))
        review_eligibility(other.pk, user=self.admin, data=review_data(other))
        close_non_ewaf_program(self.program, self.admin)
        decide_assistance(other.pk, user=self.admin, data=decision_data(other))
        third = create_application(self.program, create_member('ASSIST-003'))
        review_eligibility(third.pk, user=self.admin, data=review_data(third))
        close_non_ewaf_program(self.program, self.admin)
        with self.assertRaisesMessage(ValidationError, 'All beneficiary slots'):
            decide_assistance(third.pk, user=self.admin, data=decision_data(third))
        # Final outcomes protect approved capacity before an edit can be saved.
        with self.assertRaisesMessage(ValidationError, 'approved details must be preserved'):
            save_program(pk=self.program.pk, user=self.admin, data=program_data(slots=1))

    def test_released_case_prevents_review_decision_and_cancellation(self):
        self.approve()
        self.release()
        for action in [lambda: self.review(), lambda: decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application, decision='pending')),
                       lambda: change_application(self.application.pk, user=self.admin, version=decision_data(self.application)['version'], status='CLOSED', notes='Cancel.')]:
            with self.assertRaisesMessage(ValidationError, 'has been released'):
                action()

    def test_approved_application_must_be_returned_before_cancellation(self):
        self.approve()
        with self.assertRaisesMessage(ValidationError, 'Return the assistance approval'):
            change_application(self.application.pk, user=self.admin, version=decision_data(self.application)['version'], status='CLOSED', notes='Cancel.')

    def test_cancelled_application_cannot_be_assessed_or_approved(self):
        self.review()
        change_application(self.application.pk, user=self.admin, version=decision_data(self.application)['version'], status='CLOSED', notes='Cancel.')
        with self.assertRaises(ValidationError):
            self.review()
        with self.assertRaises(ValidationError):
            decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))

    def test_restoring_cancelled_application_requires_fresh_assessment(self):
        self.review()
        change_application(self.application.pk, user=self.admin, version=decision_data(self.application)['version'], status='CLOSED', notes='Cancel.')
        with self.assertRaises(ValidationError):
            change_application(self.application.pk, user=self.admin, version=decision_data(self.application)['version'], status='PHOTO_VERIFIED', notes='Invalid restoration.')
        with self.assertRaises(ValidationError):
            decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))

    def test_stale_versions_notes_and_confirmation_required(self):
        stale = review_data(self.application)
        self.review()
        with self.assertRaisesMessage(ValidationError, 'record changed'):
            review_eligibility(self.application.pk, user=self.admin, data=stale)
        for changes in [{'notes': ' '}, {'confirm': False}, {'decision': 'made_up'}]:
            with self.assertRaises(ValidationError):
                decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application, **changes))

    def test_release_validates_dates_amounts_and_confirm(self):
        self.approve()
        for changes in [{'released_on': str(timezone.localdate()+timedelta(days=1))}, {'released_on': str(timezone.localdate()-timedelta(days=1))},
                        {'amount': '-1'}, {'estimated_value': '-1'}, {'amount': 'NaN'}, {'confirm': False}, {'notes': ' '}, {'benefit': ''}]:
            with self.assertRaises(ValidationError):
                self.release(**changes)
        release = self.release(amount='', estimated_value='100')
        self.assertIsNone(release.amount)

    def test_duplicate_release_and_double_void_blocked(self):
        self.approve()
        release = self.release()
        with self.assertRaisesMessage(ValidationError, 'has been released'):
            self.release()
        self.void(release)
        with self.assertRaisesMessage(ValidationError, 'already been voided'):
            self.void(release)

    def test_database_rejects_duplicate_active_release_and_negative_values(self):
        self.approve()
        release = self.release()
        with self.assertRaises(IntegrityError), transaction.atomic():
            AssistanceRelease.objects.filter(pk=release.pk).update(amount=-1)
        release.pk = None
        import uuid
        release.pk = uuid.uuid4()
        with self.assertRaises(IntegrityError), transaction.atomic():
            release.save(force_insert=True)
        with self.assertRaises(ProtectedError):
            self.application.delete()

    def test_audit_failure_rolls_back_every_action(self):
        with patch('assistance.services.record_log', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.review()
        self.assertFalse(AssistanceCase.objects.exists())
        self.review()
        close_non_ewaf_program(self.program, self.admin)
        with patch('assistance.services.record_log', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))
        self.assertEqual(AssistanceCase.objects.get().decision, 'pending')
        decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))
        from announcements.testsupport import publish_selection
        publish_selection(self.program, self.admin)
        with patch('assistance.services.record_log', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.release()
        self.assertEqual(previous_assistance_count(self.member), 0)
        release = self.release()
        with patch('assistance.services.record_log', side_effect=RuntimeError('Audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.void(release)
        self.assertEqual(previous_assistance_count(self.member), 1)

    def test_configurable_labels_deactivation_stale_writes_and_snapshots(self):
        before = list(EligibilityStatus.objects.values())
        with self.assertRaises(ValidationError):
            configure_status('eligible', user=self.admin, data={'version': 0, 'label': 'Replacement', 'is_active': False, 'notes': 'Attempt mutation.'})
        self.assertEqual(list(EligibilityStatus.objects.values()), before)

    def test_private_routes_and_separate_action_permissions(self):
        routes = [reverse('assistance:queue'), self.detail] + [reverse('assistance:'+name, args=[self.application.pk]) for name in ['review', 'decision', 'release']]
        self.client.logout()
        for route in routes:
            self.assertEqual(self.client.get(route).status_code, 302)
        self.client.force_login(self.viewer)
        self.assertRedirects(self.client.get(self.detail), reverse('programs:application_detail',
            args=[self.program.pk, self.application.pk]))
        for route in routes[2:]:
            self.assertEqual(self.client.get(route).status_code, 403)
        self.assertEqual(self.client.get(reverse('assistance:statuses')).status_code, 403)
        for user in [self.viewer, AnonymousUser()]:
            with self.assertRaises(PermissionDenied):
                review_eligibility(self.application.pk, user=user, data=review_data(self.application))
        self.viewer.is_active = False
        self.viewer.save()
        with self.assertRaises(PermissionDenied):
            review_eligibility(self.application.pk, user=self.viewer, data=review_data(self.application))

    def test_separate_review_decision_release_void_capabilities(self):
        grant(self.viewer, 'assistance.review_eligibility')
        reviewer = get_user_model().objects.get(pk=self.viewer.pk)
        review_eligibility(self.application.pk, user=reviewer, data=review_data(self.application))
        with self.assertRaises(PermissionDenied):
            decide_assistance(self.application.pk, user=reviewer, data=decision_data(self.application))
        self.approve()
        with self.assertRaises(PermissionDenied):
            record_release(self.application.pk, user=reviewer, data=release_data(self.application))
        release = self.release()
        with self.assertRaises(PermissionDenied):
            void_release(self.application.pk, release.pk, user=reviewer, data={})

    def test_get_and_csrf_cannot_mutate(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.admin)
        for action in ['review', 'decision', 'release']:
            url = reverse('assistance:'+action, args=[self.application.pk])
            self.assertEqual(strict.post(url, review_data(self.application)).status_code, 403)
            self.assertEqual(self.client.get(url, follow=True).status_code, 200)
        self.assertFalse(AssistanceCase.objects.exists())
        self.assertEqual(self.client.post(self.detail, {}).status_code, 405)
        self.assertEqual(self.client.get('/admin/assistance/assistancecase/').status_code, 404)

    def test_html_forms_work_with_messages_and_invalid_posts(self):
        response = self.client.post(reverse('assistance:review', args=[self.application.pk]), review_data(self.application), follow=True)
        self.assertContains(response, 'Eligible')
        self.assertContains(response, 'Eligibility saved.')
        close_non_ewaf_program(self.program, self.admin)
        response = self.client.post(reverse('assistance:decision', args=[self.application.pk]), decision_data(self.application), follow=True)
        self.assertContains(response, 'Selected')
        from announcements.testsupport import publish_selection
        publish_selection(self.program, self.admin)
        self.application.refresh_from_db()
        self.program.refresh_from_db()
        response = self.client.post(reverse('assistance:release', args=[self.application.pk]), {
            'version': self.application.version, 'program_version': self.program.version}, follow=True)
        self.assertContains(response, 'Actual receipt recorded')
        self.assertIn('no-store', response['Cache-Control'])
        release = AssistanceRelease.objects.get()
        self.application.refresh_from_db()
        response = self.client.post(reverse('assistance:void', args=[self.application.pk, release.pk]), {'version': self.application.version, 'notes': 'Correction', 'confirm': True}, follow=True)
        self.assertContains(response, 'Voided')
        response = self.client.post(reverse('assistance:review', args=[self.application.pk]), review_data(self.application, notes=''))
        self.assertContains(response, 'This field is required.')

    def test_member_history_permission_and_private_public_pages(self):
        self.approve()
        self.release(benefit='PRIVATE BENEFIT DETAIL')
        member_url = reverse('members:detail', args=[self.member.pk])
        self.assertContains(self.client.get(member_url), 'PRIVATE BENEFIT DETAIL')
        grant(self.viewer, 'members.view_member')
        self.client.force_login(self.viewer)
        self.assertNotContains(self.client.get(member_url), 'PRIVATE BENEFIT DETAIL')
        self.assertNotContains(self.client.get(self.detail, follow=True), 'PRIVATE BENEFIT DETAIL')
        self.client.logout()
        for url in ['/', '/programs/', reverse('programs:detail', args=[self.program.pk])]:
            self.assertNotContains(self.client.get(url), 'PRIVATE BENEFIT DETAIL')

    def test_history_permission_does_not_expose_private_release_notes(self):
        self.approve()
        release = self.release(notes='PRIVATE RELEASE NOTE')
        self.void(release, notes='PRIVATE VOID NOTE')
        grant(self.viewer, 'assistance.view_assistancelog')
        self.client.force_login(self.viewer)
        response = self.client.get(self.detail, follow=True)
        self.assertNotContains(response, 'PRIVATE RELEASE NOTE')
        self.assertNotContains(response, 'PRIVATE VOID NOTE')

    def test_void_requires_current_version_and_explicit_confirmation(self):
        self.approve()
        release = self.release()
        for changes in [{'confirm': False}, {'notes': ''}, {'version': 0}]:
            with self.assertRaises(ValidationError):
                self.void(release, **changes)
        self.assertEqual(previous_assistance_count(self.member), 1)

    def test_configuration_audit_failure_does_not_change_label(self):
        before = list(EligibilityStatus.objects.values())
        with self.assertRaises(ValidationError):
            configure_status('eligible', user=self.admin, data={'version': 0, 'label': 'Replacement', 'is_active': False, 'notes': 'Attempt mutation.'})
        self.assertEqual(list(EligibilityStatus.objects.values()), before)

    def test_search_filters_pagination_and_configuration_pages(self):
        self.review()
        queue = reverse('assistance:queue')
        self.assertContains(self.client.get(queue, {'program': self.program.pk, 'q': self.member.control_number}, follow=True), self.member.full_name)
        self.assertNotContains(self.client.get(queue, {'program': self.program.pk, 'eligibility': 'unreviewed'}, follow=True), self.member.full_name)
        self.assertContains(self.client.get(queue, {'program': self.program.pk, 'eligibility': 'eligible', 'decision': 'pending'}), self.member.full_name)
        for index in range(21):
            create_application(create_program(), self.member)
        response = self.client.get(reverse('assistance:queue'), follow=True)
        self.assertEqual(response.context['page_obj'].paginator.num_pages, 2)
        self.assertContains(response, '/applications/')
        self.assertEqual(self.client.get(reverse('assistance:statuses')).status_code, 200)
        self.assertEqual(self.client.get(reverse('assistance:status_edit', args=['eligible'])).status_code, 200)

    def test_xss_escaped_and_cross_application_void_rejected(self):
        self.approve()
        release = self.release(notes='<script>alert(1)</script>')
        response = self.client.get(self.detail, follow=True)
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        other = create_application(create_program(), self.member)
        self.assertEqual(self.client.get(reverse('assistance:void', args=[other.pk, release.pk])).status_code, 404)


class AssistanceConcurrencyTests(TransactionTestCase):
    def setUp(self):
        private_media(self)
        seed_statuses()
        self.admin = get_user_model().objects.create_superuser('concurrent_assistance')
        self.program = create_program(slots=1)
        self.application = create_application(self.program, create_member('CONCURRENT-A'))
        review_eligibility(self.application.pk, user=self.admin, data=review_data(self.application))

    def race(self, callbacks):
        barrier = Barrier(len(callbacks))
        def worker(callback):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    callback()
                    return True
                except ValidationError:
                    return False
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=len(callbacks)) as pool:
            futures = [pool.submit(worker, callback) for callback in callbacks]
            return [future.result(timeout=30) for future in futures]

    def test_last_slot_can_only_be_approved_once(self):
        other = create_application(self.program, create_member('CONCURRENT-B'))
        review_eligibility(other.pk, user=self.admin, data=review_data(other))
        close_non_ewaf_program(self.program, self.admin)
        first_data, second_data = decision_data(self.application), decision_data(other)
        results = self.race([lambda: decide_assistance(self.application.pk, user=self.admin, data=first_data),
                             lambda: decide_assistance(other.pk, user=self.admin, data=second_data)])
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(reserved_slots(self.program), 1)

    def test_simultaneous_release_creates_one_record_and_log(self):
        close_non_ewaf_program(self.program, self.admin)
        decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))
        from announcements.testsupport import publish_selection
        publish_selection(self.program, self.admin)
        data = release_data(self.application)
        results = self.race([lambda: record_release(self.application.pk, user=self.admin, data=data)] * 2)
        self.assertEqual(sorted(results), [False, True])
        self.assertEqual(AssistanceRelease.objects.count(), 1)
        self.assertEqual(AssistanceLog.objects.filter(action='assistance_released').count(), 1)

    def test_member_deactivation_racing_release_is_serialized(self):
        close_non_ewaf_program(self.program, self.admin)
        decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))
        from announcements.testsupport import publish_selection
        publish_selection(self.program, self.admin)
        data = release_data(self.application)
        self.race([lambda: record_release(self.application.pk, user=self.admin, data=data),
                   lambda: change_status(self.application.member_id, user=self.admin, version=0, status='inactive', notes='Deactivate.')])
        if AssistanceRelease.objects.exists():
            self.assertEqual(AssistanceRelease.objects.get().approval_snapshot['member_version'], 0)
        self.application.member.refresh_from_db()
        self.assertFalse(self.application.member.is_active)
