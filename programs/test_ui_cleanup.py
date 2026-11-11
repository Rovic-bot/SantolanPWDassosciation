from importlib import import_module
from types import SimpleNamespace
from django.apps import apps
from django.db import connection
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from membership.forms import ApplicationForm
from membership.pdf_registration_forms import AssociationPDFForm
from membership.tests import onsite_profile
from members.disability_catalog import NAMES, current_types
from members.models import DisabilityType
from members.tests import create_member
from .forms import ProgramForm
from .services import save_program, save_program_with_requirements, change_publication, require_disability
from .tests import program_data
from .test_approved_terms import TermsHelpers
from ewaf.operational_testsupport import OperationalHelpers
from ewaf.models import CriterionAssessment


def seed_catalog():
    import_module('members.migrations.0005_controlled_disability_catalog').add_catalog(
        apps, SimpleNamespace(connection=connection))


class CatalogUITests(TestCase):
    def setUp(self):
        seed_catalog()
        self.admin = get_user_model().objects.create_superuser('catalog_ui')
        self.client.force_login(self.admin)

    def test_catalog_migration_adds_only_and_is_idempotent(self):
        old = DisabilityType.objects.create(name='Historical classification', is_active=False)
        before = list(DisabilityType.objects.values())
        seed_catalog()
        self.assertEqual(list(DisabilityType.objects.values()), before)
        old.refresh_from_db()
        self.assertFalse(old.is_active)
        self.assertEqual(list(current_types().values_list('name', flat=True)), list(NAMES))

    def test_same_ten_checkbox_choices_and_multiple_registration_values(self):
        for form, name in ((ApplicationForm(), 'disability_types'), (ProgramForm(), 'eligible_disability_types')):
            self.assertCountEqual(form.fields[name].queryset.values_list('name', flat=True), NAMES)
            self.assertEqual(type(form.fields[name].widget).__name__, 'CheckboxSelectMultiple')
        self.assertEqual(
            [label for value, label in ProgramForm().fields['eligible_disability_types'].choices],
            [label for value, label in AssociationPDFForm().fields['disability_type'].choices if value])
        data = {**onsite_profile(), 'disability_types': list(current_types().values_list('pk', flat=True))[:2],
                'submission_token': ApplicationForm().initial['submission_token']}
        form = ApplicationForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['disability_types'].count(), 2)
        data['disability_types'] = []
        self.assertFalse(ApplicationForm(data).is_valid())

    def test_extra_requirements_optional_and_disability_mismatch_blocks(self):
        visual = current_types().get(name='Visual Disability')
        cancer = current_types().get(name='Cancer (RA 11215)')
        program = save_program_with_requirements(user=self.admin,
            data=program_data(requirements='', photo_instructions='', selection_method='',
                              eligible_disability_types=[cancer.pk]), requirements=[])
        self.assertFalse(program.configured_requirements.exists())
        member = create_member('UI-TYPE')
        self.assertEqual(member.disability_type_id, visual.pk)
        with self.assertRaisesMessage(ValidationError, 'do not match'):
            require_disability(program, member)
        member.disability_types.add(cancer)
        require_disability(program, member)

    def test_unknown_new_classification_is_not_accepted_and_legacy_is_retained(self):
        old = DisabilityType.objects.create(name='Historical type')
        form = ProgramForm(program_data(eligible_disability_types=[old.pk]))
        self.assertFalse(form.is_valid())
        from .tests import create_program
        program = create_program(eligible_disability_types=[old.pk])
        values = program_data(eligible_disability_types=[], registration_opens_at=program.registration_opens_at,
                              registration_closes_at=program.registration_closes_at)
        updated = save_program(user=self.admin, pk=program.pk, data=values)
        self.assertEqual(list(updated.eligible_disability_types.values_list('pk', flat=True)), [old.pk])
        self.assertContains(self.client.get(reverse('programs:edit', args=[program.pk])), 'Earlier classifications retained')

    def test_removed_navigation_and_events_link_hidden(self):
        response = self.client.get(reverse('core:dashboard'))
        from core.tests.test_workspace_navigation import sidebar
        for label in ('Disability types', 'Registration settings', 'Eligibility statuses', 'Non-EWAF Selection'):
            self.assertNotIn(label, sidebar(response))
        self.assertNotContains(self.client.get(reverse('events:observances')), 'Historical event records')


@override_settings(PDAO_ENFORCEMENT_ENABLED=True)
class PublicationUITests(TermsHelpers, TestCase):
    def test_optional_fields_do_not_block_publication_but_pdao_does(self):
        self.setup_terms(draft=True)
        self.program.photo_instructions = ''
        self.program.selection_method = ''
        self.program.requirements = ''
        self.program.save()
        with self.assertRaises(ValidationError):
            change_publication(self.program.pk, user=self.officer, version=self.program.version,
                               action='published', notes='Fictional notice publication')
        self.reconcile()
        self.program.refresh_from_db()
        change_publication(self.program.pk, user=self.officer, version=self.program.version,
                           action='published', notes='Fictional approved notice publication')
        self.program.refresh_from_db()
        self.assertEqual(self.program.status, 'published')
        self.assertIsNone(self.program.policy_authorized_at)
        self.assertFalse(self.program.registration_available)


class ReviewUITests(OperationalHelpers, TestCase):
    def setUp(self):
        self.setup_operational()
        self.client.force_login(self.officer)
        self.url = reverse('programs:application_detail', args=[self.program.pk, self.application.pk])

    def test_simplified_form_records_explicit_evidence_backed_findings(self):
        response = self.client.get(self.url)
        form = response.context['qualification_form']
        assessment = CriterionAssessment.objects.filter(application=self.application, criterion='PR').first()
        findings = assessment.source_manifest['relevance']['items']
        data = {'action': 'qualification', 'qualification-simplified': 'True',
                'qualification-value': assessment.value, 'qualification-reason': 'Fictional officer reviewed these documents and findings.',
                'qualification-confirmed': 'on',
                'qualification-evidence': sorted({row['id'] for item in findings for row in item['supporting_reviews']})}
        for name in ('expected_context', 'expected_revision', 'policy_id'):
            data['qualification-' + name] = form[name].value()
        for index, item in enumerate(findings):
            data[f'qualification-outcome_{index}'] = item['outcome']
        response = self.client.post(self.url, data)
        self.assertEqual(response.status_code, 302,
                         response.context['qualification_form'].errors if response.status_code == 200 else '')
        latest = CriterionAssessment.objects.filter(application=self.application, criterion='PR').first()
        self.assertEqual(latest.revision, assessment.revision + 1)
        self.assertEqual(len(latest.source_manifest['relevance']['items']), len(findings))

    def test_normal_pages_have_short_controls_and_no_raw_settings_diagnostics(self):
        response = self.client.get(self.url)
        for text in ('Program qualification finding', 'functional_need explanation', 'Original submission',
                     'Verify program inputs', 'Program qualification and functional need'):
            self.assertNotContains(response, text)
        for label in ('Personal Information', 'Address Information', 'Submitted documents', 'Eligible',
                      'Ineligible', 'Needs Information', 'Remarks (optional)'):
            self.assertContains(response, label)
        self.assertNotContains(response, 'Review program fit')
        workspace = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]))
        for text in ('authority_reference', 'SI.measure', 'PR.functional_need', 'Calculation is blocked until'):
            self.assertNotContains(workspace, text)
        self.assertContains(workspace, 'Complete Settings')
        self.assertContains(workspace, 'Generate EWAF')
        settings_page = self.client.get(reverse('ewaf:operational_workspace', args=[self.program.pk]) + '?settings=1')
        self.assertContains(settings_page, 'Approval reference')
        self.assertContains(settings_page, 'Approved category scores')
        self.assertEqual(type(settings_page.context['configuration_form']).__name__, 'GuidedConfigurationForm')
        guided = settings_page.context['configuration_form']
        data = {name: guided[name].value() for name in guided.fields if guided[name].value() is not None}
        data.update(action='DRAFT', reason='Fictional review of the existing approved definition.')
        for code in ('SI', 'ES', 'PA', 'ND'):
            data.pop(code + '_encoding', None)
            for index, (category, score) in enumerate((guided.initial.get(code + '_encoding') or {}).items()):
                data[f'{code}_encoding_key_{index}'] = category
                data[f'{code}_encoding_value_{index}'] = score
        saved = self.client.post(reverse('ewaf:operational_workspace', args=[self.program.pk]) + '?settings=1', data)
        self.assertEqual(saved.status_code, 302,
                         saved.context['configuration_form'].errors if saved.status_code == 200 else '')
