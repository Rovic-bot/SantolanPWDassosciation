from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from members.tests import create_member
from membership.tests import grant
from assistance.tests import seed_statuses, review_data, decision_data, release_data
from assistance.services import review_eligibility, decide_assistance, record_release, void_release
from announcements.results import prepare_results, publish_results, results_current
from announcements.models import Announcement, ProgramResultRevision
from .models import Program, ProgramRequirement
from .forms import ProgramForm
from .services import save_program_with_requirements
from .tests import create_program, program_data
from .testsupport import private_media, application_fixture, close_non_ewaf_program


class AdminWorkflowTests(TestCase):
    def setUp(self):
        private_media(self)
        seed_statuses()
        self.admin = get_user_model().objects.create_superuser('workflow_admin')
        self.client.force_login(self.admin)
        self.program = create_program()
        self.member = create_member('WORKFLOW-001')
        self.application = application_fixture(self.program, self.member)

    def test_inline_requirements_atomic_save_and_pdf(self):
        data = {key: value for key, value in program_data().items() if value is not None}
        data.update({'requirements-TOTAL_FORMS': '1', 'requirements-INITIAL_FORMS': '0',
                     'requirements-0-label': 'Program evidence', 'requirements-0-kind': 'document',
                     'requirements-0-instructions': 'Bring or submit the required proof.', 'requirements-0-is_required': 'on'})
        response = self.client.post(reverse('programs:create'), data)
        self.assertEqual(response.status_code, 302)
        program = Program.objects.exclude(pk=self.program.pk).get()
        self.assertEqual(program.configured_requirements.get().label, 'Program evidence')
        pdf = self.client.get(reverse('programs:proposal', args=[program.pk]))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf['Content-Type'], 'application/pdf')
        self.assertTrue(pdf.content.startswith(b'%PDF-'))
        self.assertIn('inline', pdf['Content-Disposition'])
        self.assertIn('attachment', self.client.get(reverse('programs:proposal', args=[program.pk]) + '?download=1')['Content-Disposition'])
        before = Program.objects.count()
        with patch('programs.services.save_requirement', side_effect=ValidationError('Requirement audit failed')):
            with self.assertRaises(ValidationError):
                save_program_with_requirements(user=self.admin, data=program_data(),
                    requirements=[{'label': 'Proof', 'kind': 'document'}])
        self.assertEqual(Program.objects.count(), before)

    def test_removed_fields_ignore_forged_values_and_preserve_history(self):
        program = create_program(amount='250.00', benefit='Historical benefit', assistance_type='Historical category')
        form = ProgramForm(instance=program)
        self.assertNotIn('amount', form.fields)
        self.assertNotIn('benefit', form.fields)
        self.assertEqual(dict(form.fields['assistance_type'].choices)[program.assistance_type], 'Historical category (retained)')
        self.assertEqual(list(dict(ProgramForm().fields['assistance_type'].choices)),
                         ['Food & Nutrition', 'Healthcare & Medical Aid', 'Assistive Devices'])
        data = program_data(version=program.version, assistance_type=program.assistance_type,
                            registration_opens_at=program.registration_opens_at,
                            registration_closes_at=program.registration_closes_at, amount='0', benefit='Forged')
        save_program_with_requirements(user=self.admin, pk=program.pk, data=data, requirements=[])
        program.refresh_from_db()
        self.assertEqual(str(program.amount), '250.00')
        self.assertEqual(program.benefit, 'Historical benefit')

    def test_program_first_reviews_and_integrated_photo(self):
        response = self.client.get(reverse('core:application_programs'))
        self.assertContains(response, 'class="program-grid"')
        self.assertContains(response, 'Created')
        response = self.client.get(reverse('assistance:queue'), follow=True)
        self.assertContains(response, reverse('programs:applications', args=[self.program.pk]))
        response = self.client.get(reverse('assistance:queue'), {'program': self.program.pk}, follow=True)
        self.assertContains(response, self.member.full_name)
        url = reverse('programs:application_detail', args=[self.program.pk, self.application.pk])
        self.assertContains(self.client.get(url), 'Verify Identity')
        response = self.client.post(url, {'action': 'photo', 'version': self.application.version,
            'photo_id': self.application.current_photo_id, 'outcome': 'VERIFIED',
            'reason': 'Verified the supplied program photo.', 'confirm': 'on'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.application.current_photo.reviews.first().reason, 'Verified the supplied program photo.')
        limited = get_user_model().objects.create_user('workflow_restricted', is_staff=True)
        grant(limited, 'accounts.access_dashboard', 'programs.view_program', 'programs.view_programapplication')
        self.client.force_login(limited)
        self.assertNotContains(self.client.get(url), 'class="applicant-photo"')
        self.assertEqual(self.client.post(url, {'action': 'photo'}).status_code, 403)

    def test_recipient_publication_requires_receipt_and_void_invalidates_publication(self):
        review_eligibility(self.application.pk, user=self.admin, data=review_data(self.application))
        close_non_ewaf_program(self.program)
        decide_assistance(self.application.pk, user=self.admin, data=decision_data(self.application))
        with self.assertRaisesMessage(ValidationError, 'actual assistance'):
            prepare_results(self.program.pk, user=self.admin, version=0, reason='Recipient notice', recipients=True)
        receipt = record_release(self.application.pk, user=self.admin, data=release_data(self.application))
        item = prepare_results(self.program.pk, user=self.admin, version=0, reason='Confirmed recipients', recipients=True)
        self.assertEqual(item.status, 'draft')
        self.assertFalse(Announcement.objects.published().exists())
        payload = item.result_revision.public_payload
        self.assertEqual([row['status'] for row in payload['rows']], ['Received'])
        self.assertNotIn(self.member.full_name, str(payload))
        self.assertNotIn(self.application.public_reference, str(payload))
        publish_results(item.pk, user=self.admin, version=item.version)
        response = self.client.get(reverse('announcements:detail', args=[item.pk]))
        self.assertContains(response, 'Confirmed assistance recipients')
        self.application.refresh_from_db()
        void_release(self.application.pk, receipt.pk, user=self.admin, data={
            'version': self.application.version, 'notes': 'Correct the receipt record.', 'confirm': True})
        item.refresh_from_db()
        self.assertFalse(results_current(item))
        self.assertEqual(self.client.get(reverse('announcements:detail', args=[item.pk])).status_code, 404)
        self.assertEqual(ProgramResultRevision.objects.count(), 1)

    def test_reports_filters_privacy_exports_and_permissions(self):
        other = create_program(name='Another program')
        for kind in ('members', 'applications', 'programs', 'assistance'):
            url = reverse('reports:' + kind)
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.client.get(url, {'format': 'pdf'})['Content-Type'], 'application/pdf')
            csv = self.client.get(url, {'format': 'csv'})
            self.assertIn('no-store', csv['Cache-Control'])
            self.assertNotIn(self.member.address, csv.content.decode('utf-8-sig'))
        csv = self.client.get(reverse('reports:programs'), {'program': other.pk, 'format': 'csv'}).content.decode('utf-8-sig')
        self.assertIn(other.name, csv)
        self.assertNotIn(self.program.name, csv)
        self.assertEqual(self.client.get(reverse('reports:members'), {'start': '2026-10-20', 'end': '2026-01-01', 'format': 'csv'}).status_code, 400)
        limited = get_user_model().objects.create_user('report_restricted', is_staff=True)
        grant(limited, 'accounts.access_dashboard', 'programs.view_program')
        self.client.force_login(limited)
        self.assertEqual(self.client.get(reverse('reports:members'), {'format': 'csv'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('reports:assistance')).status_code, 403)
        self.assertEqual(self.client.get(reverse('reports:programs')).status_code, 200)

    def test_reports_csv_formula_injection_and_invalid_filter(self):
        from reports.services import csv_bytes
        self.assertIn("'=HYPERLINK", csv_bytes(['Name'], [['=HYPERLINK("example")']]).decode('utf-8-sig'))
        self.assertEqual(self.client.get(reverse('reports:programs'), {'program': 'invalid', 'format': 'pdf'}).status_code, 400)

    def test_excel_matches_filtered_csv_and_treats_formulas_as_text(self):
        from io import BytesIO
        from openpyxl import load_workbook
        from reports.services import xlsx_bytes
        workbook = load_workbook(BytesIO(xlsx_bytes(['Name'], [['=HYPERLINK("https://example.test")']])))
        self.assertEqual(workbook.active['A2'].data_type, 's')
        workbook.close()
        response = self.client.get(reverse('reports:applications'), {'program': self.program.pk, 'format': 'xlsx'})
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content), read_only=True)
        rows = list(workbook.active.values)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], self.application.public_reference)
        self.assertEqual(rows[1][2], self.program.name)
        self.assertIn('Actually assisted', rows[0])
        workbook.close()

    def test_retired_event_creation_and_navigation(self):
        self.assertEqual(self.client.get(reverse('events:create')).status_code, 410)
        self.assertEqual(self.client.post(reverse('events:create'), {}).status_code, 410)
        from core.tests.test_workspace_navigation import sidebar
        nav = sidebar(self.client.get(reverse('programs:create')))
        for removed in ('Create program', 'Create event', 'Photo Verification Queue', 'Criterion evidence',
                        'Scoring-policy diagnostics', 'Configuration drafts', 'Historical EWAF information', 'Prepare program results'):
            self.assertNotIn(removed, nav)
        self.assertIn('aria-current="page">Program Management', nav)
