from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from assistance.services import review_eligibility, decide_assistance, record_release, void_release
from assistance.tests import seed_statuses, review_data, decision_data, release_data
from members.tests import create_member
from membership.tests import grant
from programs.models import PhotoVerification
from programs.tests import create_program
from programs.testsupport import private_media, application_fixture, close_non_ewaf_program
from .models import Announcement, ProgramResultRevision
from .results import prepare_results, mask_identity, RESULT_PERMISSIONS
from .services import change_publication


def mock_pdf_conversion(test):
    # Delivery/workflow tests do not require a desktop Office installation.
    # Real conversion and visual verification are exercised separately.
    import hashlib
    converter = patch('announcements.certificate_delivery.certificate_pdfs',
        side_effect=lambda documents: [b'%PDF-1.4\n% synthetic ' + hashlib.sha256(doc).hexdigest().encode()
                                      + b'\n%%EOF\n' for doc in documents])
    test.pdf_converter = converter.start()
    test.addCleanup(converter.stop)


class ProgramResultTests(TestCase):
    def setUp(self):
        mock_pdf_conversion(self)
        private_media(self)
        seed_statuses()
        self.admin = get_user_model().objects.create_superuser('result_admin')
        self.program = create_program(eligible_disability_types=[], slots=2)
        self.member = create_member('RESULT-001')
        self.member.full_name = 'Juan Dela Cruz'
        self.member.save()
        self.application = application_fixture(self.program, self.member)
        review_eligibility(self.application.pk, user=self.admin, data=review_data(self.application))
        close_non_ewaf_program(self.program)
        self.client.force_login(self.admin)

    def draft(self, version=0):
        return prepare_results(self.program.pk, user=self.admin, version=version, reason='Reviewed official decisions and approved public information.')

    def publish(self, item):
        return change_publication(item.pk, user=self.admin, version=item.version, action='published')

    def test_draft_explicit_publication_safe_projection_and_withdrawal(self):
        item = self.draft()
        public = Client()
        url = reverse('announcements:detail', args=[item.pk])
        self.assertEqual(public.get(url).status_code, 404)
        item = self.publish(item)
        notice = public.get(url)
        self.assertContains(notice, reverse('core:result_detail', args=[item.pk]))
        self.assertNotContains(notice, 'J*** D*** C***')
        response = public.get(reverse('core:result_detail', args=[item.pk]))
        self.assertContains(response, 'J*** D*** C***')
        self.assertContains(response, '****' + self.application.public_reference[-4:])
        for value in (self.member.full_name, self.member.control_number, self.application.public_reference,
                      str(self.application.pk), self.application.status_token, self.member.contact_number):
            self.assertNotContains(response, value)
        self.assertEqual(set(item.result_revision.public_payload['rows'][0]), {'name', 'reference', 'status', 'ambiguous'})
        self.assertContains(public.get(reverse('core:announcements')), item.title)
        self.assertContains(public.get(reverse('core:announcements')), item.title)
        change_publication(item.pk, user=self.admin, version=item.version, action='draft')
        self.assertEqual(public.get(url).status_code, 404)

    def test_pending_photo_or_missing_information_blocks_entire_publication(self):
        other = application_fixture(self.program, create_member('RESULT-002'))
        for status in ('PENDING_PHOTO_VERIFICATION', 'NEEDS_INFORMATION', 'ELIGIBLE', 'WAITLISTED'):
            other.status = status
            other.save()
            with self.assertRaises(ValidationError): self.draft()
        self.assertFalse(Announcement.objects.exists())

    def test_unverified_or_missing_photo_blocks_results(self):
        PhotoVerification.objects.create(photo=self.application.current_photo, outcome='NEEDS_RESUBMISSION',
            reason='Unclear calendar', reviewer_label='Admin', member_version=self.member.version)
        with self.assertRaises(ValidationError): self.draft()

    def test_nonselected_is_counted_as_eligible_but_never_listed(self):
        other_member = create_member('RESULT-002')
        other_member.full_name = 'Private Other Person'
        other_member.save()
        other = application_fixture(self.program, other_member)
        review_eligibility(other.pk, user=self.admin, data=review_data(other))
        decide_assistance(other.pk, user=self.admin, data=decision_data(other, decision='rejected'))
        item = self.publish(self.draft())
        payload = item.result_revision.public_payload
        self.assertEqual(payload['eligible_count'], 2)
        self.assertEqual(len(payload['rows']), 1)
        self.assertNotContains(Client().get(reverse('announcements:detail', args=[item.pk])), 'P*** O*** P***')

    def test_revision_and_publication_optimistic_lock(self):
        item = self.draft()
        with self.assertRaises(ValidationError): self.draft()
        with self.assertRaises(ValidationError):
            change_publication(item.pk, user=self.admin, version=0, action='published')
        self.assertEqual(ProgramResultRevision.objects.count(), 1)

    def test_source_changes_block_publish_and_all_public_reads(self):
        item = self.publish(self.draft())
        self.member.version += 1
        self.member.save()
        public = Client()
        self.assertEqual(public.get(reverse('announcements:detail', args=[item.pk])).status_code, 404)
        self.assertNotContains(public.get(reverse('core:announcements')), item.title)
        self.assertNotContains(public.get(reverse('core:home')), item.title)
        item = change_publication(item.pk, user=self.admin, version=item.version, action='draft')
        with self.assertRaises(ValidationError): self.publish(item)
        self.assertEqual(ProgramResultRevision.objects.count(), 1)

    def test_receipt_keeps_selection_public_but_void_requires_review(self):
        item = prepare_results(self.program.pk, user=self.admin, version=0,
            reason='Reviewed selected members for delivery.', roster=True)
        item = self.publish(item)
        release = record_release(self.application.pk, user=self.admin, data=release_data(self.application))
        url = reverse('announcements:detail', args=[item.pk])
        self.assertEqual(Client().get(url).status_code, 200)
        self.application.refresh_from_db()
        void_release(self.application.pk, release.pk, user=self.admin,
                     data={'version':self.application.version, 'notes':'Wrong actual receipt.', 'confirm':True})
        self.assertEqual(Client().get(url).status_code, 404)

    def test_legacy_applicant_rows_and_images_never_become_public(self):
        legacy = Announcement.objects.create(program=self.program, title='Old applicants', content='Old text',
            status='published', published_at=timezone.now(), image='announcements/private-legacy.png',
            applicant_rows=[{'name':self.member.full_name,'reference':self.application.public_reference}])
        with self.assertRaises(ValidationError):
            change_publication(legacy.pk, user=self.admin, version=0, action='published')
        item = self.publish(self.draft())
        self.assertEqual(item.pk, legacy.pk)
        self.assertEqual(item.applicant_rows, legacy.applicant_rows)
        self.assertEqual(item.result_revision.previous_announcement['title'], 'Old applicants')
        self.assertEqual(item.result_revision.previous_announcement['content'], 'Old text')
        self.assertEqual(Client().get(reverse('announcements:image', args=[item.pk])).status_code, 404)
        self.assertNotContains(Client().get(reverse('announcements:detail', args=[item.pk])), self.member.full_name)

    def test_no_ewaf_bypass_or_open_period_publication(self):
        self.program.ewaf_applicable = True
        self.program.save()
        response = self.client.get(reverse('announcements:prepare_results', args=[self.program.pk]))
        self.assertContains(response, 'PUBLISH_RECORDED_RESULTS')
        self.assertIsNotNone(response.context['preview'])
        # Legacy verified-final-results preparation still needs a valid run.
        with self.assertRaises(ValidationError): self.draft()
        self.program.ewaf_applicable = False
        self.program.registration_closes_at = timezone.now()+timezone.timedelta(days=1)
        self.program.save()
        with self.assertRaises(ValidationError): self.draft()

    def test_program_explanation_is_escaped_in_public_projection(self):
        self.program.description = '<script>alert(1)</script>'
        self.program.save()
        item = self.publish(self.draft())
        response = Client().get(reverse('announcements:detail', args=[item.pk]))
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_expired_verified_document_withholds_published_result(self):
        from documents.models import DocumentType, MembershipDocumentRequirement, MembershipApplicationDocument
        from documents.services import verify_document
        from programs.models import ProgramRequirement, ProgramDocument
        from membership.tests import pdf
        document_type = DocumentType.objects.create(name='Synthetic result proof')
        requirement = MembershipDocumentRequirement.objects.create(document_type=document_type, is_required=True)
        source = MembershipApplicationDocument.objects.create(application=self.member.application, requirement=requirement,
            label=document_type.name, file=pdf(), size=30, content_type='application/pdf')
        review = verify_document(source.pk, user=self.admin, member_version=self.member.version,
            verified=True, expires_on=timezone.localdate(), reason='Synthetic verified proof.')
        rule = ProgramRequirement.objects.create(program=self.program, label='Proof', kind='document', is_required=True)
        ProgramDocument.objects.create(application=self.application, requirement=rule, label='Proof',
            file=source.file.name, size=source.size, content_type=source.content_type,
            source_document=source, source_verification=review)
        self.application.refresh_from_db()
        self.application.requirements_snapshot = [{'id':rule.pk, 'label':'Proof', 'kind':'document','is_required':True}]
        self.application.save()
        # Reassess under the fixture's expanded mandatory requirements.
        case = self.application.assistance_case
        case.checklist.append({'key':str(rule.pk),'required':True,'result':'pass'})
        case.save()
        item = self.publish(self.draft())
        with patch('documents.services.timezone.localdate', return_value=timezone.localdate()+timezone.timedelta(days=1)):
            self.assertEqual(Client().get(reverse('announcements:detail', args=[item.pk])).status_code, 404)

    def test_permission_separation_and_forged_public_rows_ignored(self):
        editor = get_user_model().objects.create_user('result_editor', is_staff=True)
        grant(editor, 'accounts.access_dashboard', *RESULT_PERMISSIONS, 'announcements.add_announcement', 'announcements.change_announcement')
        item = prepare_results(self.program.pk, user=editor, version=0, reason='Reviewed official record.')
        with self.assertRaises(PermissionDenied):
            change_publication(item.pk, user=editor, version=item.version, action='published')
        self.client.post(reverse('announcements:manage_detail', args=[item.pk]),
            {'version':item.version, 'action':'published','confirm':'on', 'applicant_rows':'private injected name'})
        item.refresh_from_db()
        self.assertEqual(item.status, 'published')
        self.assertNotIn('private injected', str(item.result_revision.public_payload))

    def test_csrf_and_confirmation_required(self):
        item = self.draft()
        url = reverse('announcements:manage_detail', args=[item.pk])
        csrf = Client(enforce_csrf_checks=True); csrf.force_login(self.admin)
        self.assertEqual(csrf.post(url, {'version':item.version,'action':'published','confirm':'on'}).status_code, 403)
        self.client.post(url, {'version':item.version,'action':'published'})
        item.refresh_from_db(); self.assertEqual(item.status, 'draft')

    def test_audit_failure_rolls_back_preparation_and_publication(self):
        with patch('announcements.results.record_event', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError): self.draft()
        self.assertFalse(Announcement.objects.exists())
        item = self.draft()
        with patch('announcements.results.record_event', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError): self.publish(item)
        item.refresh_from_db(); self.assertEqual(item.status, 'draft')

    def test_new_draft_withdraws_old_publication_preserving_revision_and_events(self):
        item = self.publish(self.draft())
        original = item.result_revision
        revised = self.draft(item.version)
        self.assertEqual(revised.status, 'draft')
        self.assertEqual(revised.result_revisions.count(), 2)
        original.refresh_from_db(); self.assertEqual(original.number, 1)
        with self.assertRaises(ValidationError): original.save()
        with self.assertRaises(ValidationError): original.delete()
        self.assertEqual(revised.events.count(), 3)

    def test_masks_handle_short_unicode_compound_names_and_collisions(self):
        for name in ('A Li', "María Dela Cruz Jr.", "Anne-Marie O’Neil", '李 王'):
            row = mask_identity(name, 'LEGACY-000123')
            self.assertNotEqual(row['name'], name)
            self.assertEqual(row['reference'], '****0123')
        # Two legitimately different legacy references can have the same suffix.
        from programs.models import ProgramApplication
        from programs.testsupport import verified_photo
        member = create_member('RESULT-002'); member.full_name = 'Jose Dela Cruz'; member.save()
        other = ProgramApplication.objects.create(program=self.program, member=member,
            public_reference='OLD-' + self.application.public_reference[-4:])
        verified_photo(other)
        review_eligibility(other.pk, user=self.admin, data=review_data(other))
        decide_assistance(other.pk, user=self.admin, data=decision_data(other))
        item = self.publish(self.draft())
        self.assertTrue(all(row['ambiguous'] for row in item.result_revision.public_payload['rows']))
        self.assertContains(Client().get(reverse('core:result_detail', args=[item.pk])), 'Similar entry')

    def test_unified_members_navigation_respects_permissions(self):
        response = self.client.get(reverse('members:list'))
        html = response.content.decode()
        sidebar = html.split('<aside class="workspace-sidebar"', 1)[1].split('</aside>')[0]
        self.assertNotIn('Onsite member registration', sidebar)
        members_navigation = sidebar.split('data-group-key="members"', 1)[1].split('</details>', 1)[0]
        self.assertNotIn('>Applications</a>', members_navigation)
        self.assertIn(reverse('reports:applications'), sidebar)
        self.assertContains(response, 'Onsite registration')
        limited = get_user_model().objects.create_user('onsite_only', is_staff=True)
        grant(limited, 'accounts.access_dashboard', 'membership.view_membershipapplication', 'membership.encode_membershipapplication')
        self.client.force_login(limited)
        response = self.client.get(reverse('membership:list'), follow=True)
        self.assertContains(response, 'Onsite registration')
        self.assertNotContains(response, '>Member records</a>')
        self.assertEqual(self.client.get(reverse('members:list')).status_code, 403)


class ResultPublicationConcurrencyTests(TransactionTestCase):
    def test_simultaneous_preparation_and_publication_keep_one_authorized_revision(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        private_media(self)
        seed_statuses()
        admin = get_user_model().objects.create_superuser('concurrent_result_admin')
        program = create_program(eligible_disability_types=[])
        application = application_fixture(program, create_member('CONCURRENT-RESULT'))
        review_eligibility(application.pk, user=admin, data=review_data(application))
        close_non_ewaf_program(program)
        decide_assistance(application.pk, user=admin, data=decision_data(application))
        for action in ('prepare', 'publish'):
            barrier = Barrier(2)
            item = Announcement.objects.filter(program=program).first()
            def attempt():
                close_old_connections()
                try:
                    user = get_user_model().objects.get(pk=admin.pk)
                    barrier.wait(timeout=10)
                    try:
                        if action == 'prepare':
                            prepare_results(program.pk, user=user, version=0, reason='Concurrent reviewed preparation.')
                        else:
                            change_publication(item.pk, user=user, version=item.version, action='published')
                    except ValidationError:
                        return 'stale'
                    return 'saved'
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes = list(pool.map(lambda _: attempt(), range(2)))
            self.assertCountEqual(outcomes, ['saved', 'stale'])
        item = Announcement.objects.get(program=program)
        self.assertEqual(item.result_revisions.count(), 1)
        self.assertEqual(item.events.filter(action='results_published').count(), 1)
