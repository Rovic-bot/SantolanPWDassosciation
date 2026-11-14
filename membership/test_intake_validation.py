"""Current owner-approved intake requirements, without application data access."""
from datetime import date
import json
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase

from .intake_validation import catalogue, barangays, latest_birthdate, NCR_PROVINCE
from .pdao_forms import PDAOOnlineForm, PDAOOnsiteForm, PDAOReviewForm
from .registration_forms import OnlineRegistrationForm, OnsiteRegistrationForm, RegistrationForm


def association_data():
    return dict(last_name='Example', first_name='Fictional', birthdate='1990-01-02',
        house_street='12 Example Street', barangay='Santolan', city='Pasig City', region='NCR',
        zip_code='1610', contact_number='9071234567', email='fictional@example.invalid',
        civil_status='Single', nationality='Filipino', gender='Female', family_members='1',
        four_ps_member='No', disability_type='Visual Disability', education='College Undergraduate',
        household_monthly_income='0', household_members='1', employment_status='unemployed',
        pwd_number='00-0000-000-0000001', acknowledgement='on')


def pdao_data():
    return dict(last_name='Example', first_name='Fictional', birthdate='1990-01-02',
        house_street='12 Example Street', barangay='Santolan', city='Pasig City', region='NCR',
        province=NCR_PROVINCE, contact_number='9071234567', email='fictional@example.invalid',
        civil_status='Single', sex='Female', application_type='New applicant', date_applied='2001-01-01',
        disability_types=['Visual Disability'], disability_cause='Acquired', education='College',
        employment_status='Unemployed', accomplished_by='Applicant', emergency_name='Contact Example',
        emergency_relationship='Sibling', emergency_phone='9081234567',
        father_first_name='Father', father_last_name='Example', mother_first_name='Mother', mother_last_name='Example',
        submission_token='synthetic-only', acknowledgement='on')


class IntakeValidationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.policy = json.loads((settings.BASE_DIR / 'config/registration_policy.development.json').read_text(encoding='utf-8'))

    def cases(self):
        for cls in (OnlineRegistrationForm, OnsiteRegistrationForm):
            yield cls, association_data(), {'policy': self.policy}
        for cls in (PDAOOnlineForm, PDAOOnsiteForm):
            yield cls, pdao_data(), {}

    def test_all_four_paths_accept_complete_input_and_canonicalize_mobile_and_address(self):
        for cls, data, kwargs in self.cases():
            with self.subTest(form=cls.__name__):
                form = cls(data, **kwargs)
                self.assertTrue(form.is_valid(), form.errors)
                payload = form.submitted_data()
                self.assertEqual(payload['city'], 'City of Pasig')
                self.assertEqual(payload['region'], 'National Capital Region (NCR)')
                self.assertEqual(payload['contact_number'], '+639071234567')

    def test_all_four_paths_require_personal_address_contact_and_disability(self):
        for cls, data, kwargs in self.cases():
            required = ['house_street', 'barangay', 'city', 'region', 'contact_number', 'email', 'birthdate',
                        'civil_status', 'education', 'employment_status']
            required += (['sex', 'province', 'disability_types', 'disability_cause', 'emergency_name',
                          'emergency_relationship', 'emergency_phone', 'father_first_name', 'father_last_name',
                          'mother_first_name', 'mother_last_name'] if 'application_type' in data else
                         ['zip_code', 'nationality', 'gender', 'family_members', 'four_ps_member', 'disability_type'])
            for name in required:
                with self.subTest(form=cls.__name__, field=name):
                    form = cls({k: v for k, v in data.items() if k != name}, **kwargs)
                    self.assertFalse(form.is_valid())
                    self.assertIn(name, form.errors)

    def test_city_region_province_and_barangay_mismatches_rejected(self):
        for cls, data, kwargs in self.cases():
            for changes, error in [
                ({'city': 'Manila', 'barangay': 'Barangay 1', 'region': 'Region III'}, 'region'),
                ({'barangay': 'Barangay 1'}, 'barangay'),
                ({'city': 'Made up City'}, 'city'),
            ]:
                with self.subTest(form=cls.__name__, changes=changes):
                    form = cls(data | changes, **kwargs)
                    self.assertFalse(form.is_valid())
                    self.assertIn(error, form.errors)
            if 'province' in data:
                form = cls(data | {'province': 'Bulacan'})
                self.assertFalse(form.is_valid())
                self.assertIn('province', form.errors)

    def test_manila_and_repeated_city_names_resolve_to_correct_geography(self):
        data = pdao_data() | {'city': 'Manila', 'barangay': 'Barangay 1'}
        form = PDAOOnlineForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.submitted_data()['city'], 'City of Manila')
        city = next(city for city in catalogue()['cities'] if city['name'] == 'San Jose' and city['province'] == 'Batangas')
        data = pdao_data() | {'city': city['value'], 'province': city['province'],
            'region': city['region'], 'barangay': barangays(city['code'])[0][1]}
        form = PDAOOnlineForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn('Batangas', form.submitted_data()['city'])

    def test_mobile_ten_digits_without_trunk_prefix_for_all_four_paths(self):
        for cls, data, kwargs in self.cases():
            for value in ['09171234567', '+639171234567', '917123456', '91712345678', '8171234567', '917x234567', '９１７１２３４５６７']:
                with self.subTest(form=cls.__name__, value=value):
                    form = cls(data | {'contact_number': value}, **kwargs)
                    self.assertFalse(form.is_valid())
                    self.assertIn('contact_number', form.errors)

    @patch('membership.intake_validation.timezone.localdate', return_value=date(2026, 11, 14))
    def test_fifth_birthday_boundary_and_guardian_for_minors(self, _today):
        for cls, data, kwargs in self.cases():
            data['education'] = 'Elementary'
            if 'application_type' not in data:
                data |= {'guardian_name': 'Guardian Example', 'guardian_contact': '9171234567'}
            for born, valid in [('2021-11-14', True), ('2021-11-15', False), ('2027-01-01', False)]:
                with self.subTest(form=cls.__name__, born=born):
                    form = cls(data | {'birthdate': born}, **kwargs)
                    self.assertEqual(form.is_valid(), valid, form.errors)
                    if not valid:
                        self.assertIn('birthdate', form.errors)
        form = OnlineRegistrationForm(association_data() | {'birthdate': '2021-11-14'}, policy=self.policy)
        self.assertFalse(form.is_valid())
        self.assertIn('guardian_name', form.errors)
        self.assertIn('guardian_contact', form.errors)
        self.assertEqual(latest_birthdate(date(2028, 2, 29)), date(2023, 2, 28))
        self.assertEqual(latest_birthdate(date(2029, 2, 28)), date(2024, 2, 28))

    @patch('membership.intake_validation.timezone.localdate', return_value=date(2026, 11, 14))
    def test_children_under_15_choose_elementary_or_lower_and_student_or_unemployed(self, _today):
        for cls, data, kwargs in self.cases():
            is_pdao = 'application_type' in data
            data |= {'guardian_name': 'Guardian Example', 'guardian_contact': '9171234567'} if not is_pdao else {}
            for born in ('2021-11-14', '2016-11-14', '2011-11-15'):
                for education in ('None' if is_pdao else 'None / Not yet in school', 'Kindergarten', 'Elementary'):
                    for status in (('Student', 'Unemployed') if is_pdao else ('student', 'unemployed')):
                        with self.subTest(form=cls.__name__, born=born, education=education, status=status):
                            form = cls(data | {'birthdate': born, 'education': education, 'employment_status': status}, **kwargs)
                            self.assertTrue(form.is_valid(), form.errors)
                for changes, error in [
                    ({'education': 'Junior High School' if is_pdao else 'High School'}, 'education'),
                    ({'education': 'College' if is_pdao else 'College Undergraduate'}, 'education'),
                    ({'employment_status': 'Employed' if is_pdao else 'employed'}, 'employment_status'),
                    ({'employment_status': 'Self employed' if is_pdao else 'self_employed'}, 'employment_status'),
                ]:
                    with self.subTest(form=cls.__name__, born=born, changes=changes):
                        form = cls(data | {'birthdate': born, 'education': 'Elementary'} | changes, **kwargs)
                        self.assertFalse(form.is_valid())
                        self.assertIn(error, form.errors)
            # Exactly 15 restores the existing choices, including their conditional details.
            data |= {'birthdate': '2011-11-14', 'employment_status': 'Employed' if is_pdao else 'employed'}
            if is_pdao:
                data |= {'employment_category': 'Private', 'employment_nature': 'Permanent / Regular', 'occupation': 'Professional'}
            form = cls(data, **kwargs)
            self.assertTrue(form.is_valid(), form.errors)

    @patch('membership.intake_validation.timezone.localdate', return_value=date(2026, 11, 14))
    def test_child_employment_details_rejected_and_required_family_names_have_optional_middle_names(self, _today):
        for cls in (PDAOOnlineForm, PDAOOnsiteForm):
            child = pdao_data() | {'birthdate': '2021-11-14', 'education': 'Kindergarten', 'employment_status': 'Student'}
            form = cls(child)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.submitted_data()['employment_status'], 'Student')
            for name, value in [('employment_category', 'Private'), ('employment_nature', 'Casual'),
                                ('occupation', 'Professional'), ('occupation_other', 'Seller')]:
                with self.subTest(form=cls.__name__, field=name):
                    form = cls(child | {name: value})
                    self.assertFalse(form.is_valid())
                    self.assertIn(name, form.errors)
            for name in ('father_middle_name', 'mother_middle_name'):
                self.assertFalse(cls().fields[name].required)

    @patch('membership.intake_validation.timezone.localdate', return_value=date(2026, 11, 14))
    def test_filtered_bound_form_retains_full_choices_for_birthdate_correction(self, _today):
        for cls, data, kwargs in self.cases():
            form = cls(data | {'birthdate': '2021-11-14'}, **kwargs)
            profile = getattr(form, 'profile_form', form)
            education = profile.fields['education']
            self.assertNotIn(data['education'], dict(education.choices))
            self.assertIn(data['education'], dict(json.loads(education.widget.attrs['data-age-choices'])))

    @patch('membership.intake_validation.timezone.localdate', return_value=date(2026, 11, 14))
    def test_child_choices_survive_staff_review_without_rewriting_saved_information(self, _today):
        for education in ('None / Not yet in school', 'Kindergarten', 'Elementary'):
            data = association_data() | {'birthdate': '2021-11-14', 'education': education, 'employment_status': 'student',
                'guardian_name': 'Guardian Example', 'guardian_contact': '9171234567'}
            intake = OnlineRegistrationForm(data, policy=self.policy)
            self.assertTrue(intake.is_valid(), intake.errors)
            saved = intake.submitted_data()
            fields = RegistrationForm(policy=self.policy).fields
            review = RegistrationForm({key: value for key, value in saved.items() if key in fields}, initial=saved, policy=self.policy)
            self.assertTrue(review.is_valid(), review.errors)
            self.assertEqual(review.submitted_data()['education'], education)
            self.assertEqual(review.submitted_data()['employment_status'], 'student')
        data = pdao_data() | {'birthdate': '2021-11-14', 'education': 'Kindergarten', 'employment_status': 'Student'}
        intake = PDAOOnlineForm(data)
        self.assertTrue(intake.is_valid(), intake.errors)
        saved = intake.submitted_data()
        review = PDAOReviewForm({key: value for key, value in saved.items() if key in PDAOReviewForm.base_fields} |
            {'version': 0, 'action': 'correct'}, initial=saved)
        self.assertTrue(review.is_valid(), review.errors)
        self.assertEqual(review.submitted_data()['employment_status'], 'Student')

    def test_married_requires_spouse_name_and_mobile_but_single_does_not(self):
        for cls in (OnlineRegistrationForm, OnsiteRegistrationForm):
            form = cls(association_data() | {'civil_status': 'Married'}, policy=self.policy)
            self.assertFalse(form.is_valid())
            self.assertIn('spouse_name', form.errors)
            self.assertIn('spouse_contact', form.errors)
            form = cls(association_data() | {'civil_status': 'Married', 'spouse_name': 'Spouse Example',
                                          'spouse_contact': '9171234567'}, policy=self.policy)
            self.assertTrue(form.is_valid(), form.errors)

    @patch('membership.intake_validation.timezone.localdate', return_value=date(2026, 11, 14))
    def test_pdao_today_cannot_be_overridden_even_when_omitted_or_invalid(self, _today):
        for cls in (PDAOOnlineForm, PDAOOnsiteForm):
            for value in ['2000-01-01', '2999-12-31', '', 'invalid']:
                form = cls(pdao_data() | {'date_applied': value}, initial={'date_applied': date(1999, 1, 1)})
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.submitted_data()['date_applied'], '2026-11-14')
                self.assertTrue(form.fields['date_applied'].disabled)

    def test_conditional_pdao_renewal_and_employment_fields(self):
        for cls in (PDAOOnlineForm, PDAOOnsiteForm):
            form = cls(pdao_data() | {'application_type': 'Renewal', 'employment_status': 'Employed'})
            self.assertFalse(form.is_valid())
            for name in ('pwd_number', 'employment_category', 'employment_nature', 'occupation'):
                self.assertIn(name, form.errors)
            form = cls(pdao_data() | {'application_type': 'Renewal', 'pwd_number': '00-123',
                'employment_status': 'Employed', 'employment_category': 'Private',
                'employment_nature': 'Permanent / Regular', 'occupation': 'Other', 'occupation_other': 'Seller'})
            self.assertTrue(form.is_valid(), form.errors)

    def test_historical_review_forms_do_not_reset_application_date_or_enforce_new_intake(self):
        data = {key: value for key, value in pdao_data().items() if key not in ('submission_token', 'acknowledgement')}
        data |= {'version': '1', 'action': 'correct', 'date_applied': '2001-01-01', 'contact_number': '09171234567',
                 'city': 'Previously declared city', 'region': '', 'disability_types': []}
        review = PDAOReviewForm(data, initial=data)
        self.assertTrue(review.is_valid(), review.errors)
        self.assertEqual(review.submitted_data()['date_applied'], '2001-01-01')
        self.assertEqual(review.submitted_data()['contact_number'], '09171234567')
        historical = RegistrationForm(association_data() | {'region': '', 'contact_number': ''}, policy=self.policy)
        self.assertTrue(historical.is_valid(), historical.errors)

    def test_widget_and_dataset_integrity(self):
        form = PDAOOnlineForm()
        self.assertIn('+63', str(form['contact_number']))
        self.assertIn('maxlength="10"', str(form['contact_number']))
        self.assertEqual(len(catalogue()['cities']), 1642)
        self.assertEqual(len({city['value'] for city in catalogue()['cities']}), 1642)
        self.assertEqual(sum(len(barangays(city['code'])) for city in catalogue()['cities']), 42010)
