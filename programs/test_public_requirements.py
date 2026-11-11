"""Read-only published requirement definitions on the public program details page."""
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from members.tests import create_member
from .models import Program, ProgramApplication, ProgramDocument, ProgramRequirement
from .tests import create_program


@override_settings(PDAO_ENFORCEMENT_ENABLED=False, PROGRAM_APPLICATION_WORKFLOW_ENABLED=False)
class PublicProgramRequirementsTests(TestCase):
    def setUp(self):
        self.program = create_program(ewaf_applicable=True, requirements='Published general instructions.')
        self.url = reverse('programs:detail', args=[self.program.pk])

    def requirement(self, **overrides):
        return ProgramRequirement.objects.create(**{
            'program': self.program, 'label': 'Published document', 'kind': 'document',
            'instructions': 'Bring a clear copy.', **overrides})

    def test_active_requirements_show_admin_order_instructions_kind_and_necessity(self):
        optional = self.requirement(label='Optional explanation', kind='text', is_required=False, position=2)
        first = self.requirement(label='Required document', position=0, instructions='First instruction.\nSecond instruction.')
        self.requirement(label='Confirm the declaration', kind='acknowledgement', position=1)
        self.requirement(label='Inactive requirement', is_active=False)
        self.requirement(program=create_program(), label='Another program requirement')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Published general instructions.')
        for text in (first.label, optional.label, 'Required', 'Optional', 'Document upload',
                     'Written answer', 'Acknowledgement checkbox', 'First instruction.<br>Second instruction.'):
            self.assertContains(response, text)
        self.assertNotContains(response, 'Inactive requirement')
        self.assertNotContains(response, 'Another program requirement')
        html = response.content.decode()
        self.assertLess(html.index('Required document'), html.index('Confirm the declaration'))
        self.assertLess(html.index('Confirm the declaration'), html.index('Optional explanation'))
        self.assertLess(html.index('public-program-requirements-heading'), html.index('program-steps-heading'))

    def test_empty_requirements_have_a_clear_message_and_general_instructions_still_display(self):
        self.requirement(is_active=False)
        Program.objects.filter(pk=self.program.pk).update(requirements='')
        empty = self.client.get(self.url)
        self.assertContains(empty, 'No additional program requirements have been published.')
        Program.objects.filter(pk=self.program.pk).update(requirements='Only published general guidance.')
        general = self.client.get(self.url)
        self.assertContains(general, 'Only published general guidance.')
        self.assertNotContains(general, 'No additional program requirements have been published.')

    def test_admin_requirement_text_is_escaped(self):
        self.requirement(label='<script>requirementTitle()</script>',
                         instructions='<img src=x onerror="requirementInstructions()">')
        Program.objects.filter(pk=self.program.pk).update(requirements='<script>generalInstructions()</script>')
        response = self.client.get(self.url)
        self.assertContains(response, '&lt;script&gt;requirementTitle()&lt;/script&gt;')
        self.assertContains(response, '&lt;img src=x onerror=')
        self.assertNotContains(response, '<script>requirementTitle()')
        self.assertNotContains(response, '<img src=x')
        self.assertNotContains(response, '<script>generalInstructions()')

    def test_unpublished_or_future_programs_do_not_expose_requirement_definitions(self):
        self.requirement(label='Not publicly released requirement')
        for changes in ({'status': 'draft'}, {'status': 'archived'},
                        {'status': 'published', 'published_at': timezone.now() + timedelta(hours=1)}):
            with self.subTest(changes=changes):
                Program.objects.filter(pk=self.program.pk).update(**changes)
                response = self.client.get(self.url)
                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, 'Not publicly released requirement', status_code=404)

    def test_viewing_definitions_never_exposes_applicant_answers_documents_or_form_controls(self):
        document = self.requirement()
        application = ProgramApplication.objects.create(program=self.program,
            member=create_member('SYNTHETIC-PRIVATE-REQUIREMENTS'),
            public_reference='SYNTHETIC-PRIVATE-APPLICATION', answers={'secret': 'PRIVATE-ANSWER-VALUE'})
        ProgramDocument.objects.create(application=application, requirement=document,
            label='PRIVATE-UPLOADED-LETTER', file='private/synthetic-evidence.pdf',
            content_type='application/pdf', size=10)
        response = self.client.get(self.url)
        for private in ('PRIVATE-ANSWER-VALUE', 'PRIVATE-UPLOADED-LETTER', 'private/synthetic-evidence.pdf',
                        application.public_reference, str(application.pk), application.status_token):
            self.assertNotContains(response, private)
        panel = response.content.decode().split('<section class="program-detail-requirements"', 1)[1].split('</section>', 1)[0]
        for control in ('<form', '<input', '<textarea', '<select', 'href='):
            self.assertNotIn(control, panel)

    @override_settings(PROGRAM_APPLICATION_WORKFLOW_ENABLED=True)
    def test_requirements_are_viewable_without_bypassing_application_readiness(self):
        self.requirement(label='Requirement visible before applying')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Requirement visible before applying')
        self.assertEqual(response.context['program'].public_application_status, 'unavailable')
        self.assertNotContains(response, 'Apply for this program')
