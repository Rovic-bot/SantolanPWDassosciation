from copy import deepcopy
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from .pdf_registration_forms import PDAOForm
from .pdao_printing import print_context
from .test_pdf_registration import pdao_data


class PDAOSourcePrintTests(SimpleTestCase):
    def test_all_source_applicant_fields_have_a_print_mapping(self):
        source = (Path(settings.BASE_DIR) / 'templates/membership/pdao/source_form.html').read_text(encoding='utf-8')
        for field in PDAOForm.base_fields:
            if field != 'acknowledgement':
                with self.subTest(field=field):
                    self.assertIn(f'pdao.{field}' if not hasattr(PDAOForm.base_fields[field], 'choices')
                                  else f'options.{field}', source)

    def test_choices_dates_missing_fields_and_channel_do_not_mutate_history(self):
        form = PDAOForm(pdao_data())
        self.assertTrue(form.is_valid(), form.errors)
        data = form.submitted_data() | {'intake_channel': 'online'}
        original = deepcopy(data)
        context = print_context(data)
        self.assertEqual(context['pdao']['birthdate'], '01/02/1990')
        self.assertEqual([row['label'] for row in context['options']['disability_types'] if row['checked']],
                         ['Physical Disability', 'Visual Disability'])
        self.assertEqual([row['label'] for row in context['options']['submission_channel'] if row['checked']], ['Online'])
        self.assertEqual(data, original)
        legacy = print_context({'submission_channel': 'Barangay'})
        self.assertFalse(any(row['checked'] for row in legacy['options']['submission_channel']))
        self.assertFalse(any(row['checked'] for row in legacy['options']['sex']))

    def test_print_escapes_values_and_leaves_signature_unfilled(self):
        form = PDAOForm(pdao_data() | {'organization': '<script>unsafe()</script>'})
        self.assertTrue(form.is_valid(), form.errors)
        html = render_to_string('membership/registration/pdao_print.html', {'submitted': form.submitted_data()})
        self.assertIn('&lt;script&gt;unsafe()&lt;/script&gt;', html)
        self.assertNotIn('<script>unsafe()</script>', html)
        self.assertIn('SIGNATURE: ______________________________', html)
        self.assertIn('19. SUBMISSION CHANNEL:', html)
        self.assertIn('Certificate of Guardianship', html)
        self.assertIn('Government-Issued ID PLUS Barangay', html)
        self.assertNotIn('Not provided', html)
        self.assertEqual(html.count('class="pdao-sheet"'), 2)
