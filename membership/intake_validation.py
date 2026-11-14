"""Validation for new Association and PDAO intake only.

Review/edit forms retain historical values and application dates. All four
new-intake paths use these rules, including service-side form revalidation.
"""
from calendar import monthrange
from functools import lru_cache
import json
from pathlib import Path
import re
import unicodedata

from django import forms
from django.utils import timezone


CATALOGUE_PATH = Path(__file__).resolve().parent.parent / 'static/data/psgc-2026-q2'
NO_PROVINCE = 'Not applicable (independent city)'
NCR_PROVINCE = 'Metro Manila (NCR - no province)'
CHILD_MAX_AGE = 14
CHILD_EDUCATION = ('None', 'None / Not yet in school', 'Kindergarten', 'Elementary')
CHILD_EMPLOYMENT = ('student', 'unemployed', 'Student', 'Unemployed')


def normalized(value):
    value = unicodedata.normalize('NFKD', str(value or '')).casefold()
    return ' '.join(''.join(c for c in value if not unicodedata.combining(c)).split())


def city_aliases(city):
    name = normalized(city['name'])
    short = re.sub(r'^city of | city$', '', name)
    return {normalized(city['value']), name, short, f'{short} city'}


def region_aliases(name):
    aliases = {normalized(name), normalized(name.split(' (')[0])}
    aliases.update(normalized(item) for item in re.findall(r'\(([^)]+)\)', name))
    if 'NCR' in name:
        aliases.add('metro manila')
    return aliases


@lru_cache(maxsize=1)
def catalogue():
    return json.loads((CATALOGUE_PATH / 'index.json').read_text(encoding='utf-8'))


@lru_cache(maxsize=1642)
def barangays(code):
    # Only codes resolved from our catalogue reach this path.
    return json.loads((CATALOGUE_PATH / f'{code}.json').read_text(encoding='utf-8'))


def province_for(city):
    return city['province'] or (NCR_PROVINCE if city['region_code'] == '1300000000' else NO_PROVINCE)


def age_at(born, today):
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def latest_birthdate(today):
    year = today.year - 5
    return today.replace(year=year, day=min(today.day, monthrange(year, today.month)[1]))


class PhilippineMobileWidget(forms.TextInput):
    template_name = 'membership/widgets/mobile.html'

    def format_value(self, value):
        value = super().format_value(value)
        if value and re.fullmatch(r'\+639[0-9]{9}', value):
            return value[3:]
        return value


class PhilippineMobileField(forms.CharField):
    def __init__(self, *args, **kwargs):
        kwargs.update(max_length=10, min_length=10, widget=PhilippineMobileWidget(attrs={
            'inputmode': 'numeric', 'autocomplete': 'tel-national', 'pattern': '9[0-9]{9}',
            'data-ph-mobile': '', 'placeholder': '987 876 5610',
            'title': 'Enter 10 digits starting with 9, without the leading 0 or +63.',
        }), help_text='Enter 10 digits starting with 9. The +63 country code is already provided.')
        super().__init__(*args, **kwargs)

    def validate(self, value):
        super().validate(value)
        if value and not re.fullmatch(r'9[0-9]{9}', value):
            raise forms.ValidationError('Enter 10 digits starting with 9, without the leading 0 or +63.')

    def clean(self, value):
        value = super().clean(value)
        return f'+63{value}' if value else ''


def validate_address(form, values):
    city_value = normalized(values.get('city'))
    if not city_value:
        return
    candidates = [city for city in catalogue()['cities'] if city_value in city_aliases(city)]
    exact = [city for city in candidates if normalized(city['value']) == city_value]
    if exact:
        candidates = exact
    if len(candidates) > 1:
        candidates = [city for city in candidates if normalized(values.get('region')) in region_aliases(city['region'])]
        if 'province' in form.fields and len(candidates) > 1:
            candidates = [city for city in candidates if normalized(values.get('province')) == normalized(province_for(city))]
    if len(candidates) != 1:
        form.add_error('city', 'Select a city / municipality from the list; include its province when names repeat.')
        return
    city = candidates[0]
    if normalized(values.get('region')) not in region_aliases(city['region']):
        form.add_error('region', f"Choose {city['region']} for {city['name']}.")
    else:
        values['region'] = city['region']
    if 'province' in form.fields:
        allowed = {normalized(province_for(city))}
        if city['region_code'] == '1300000000':
            allowed.update({'ncr', 'metro manila', 'not applicable', 'n/a'})
        if normalized(values.get('province')) not in allowed:
            form.add_error('province', f"Choose {province_for(city)} for {city['name']}.")
        else:
            values['province'] = province_for(city)
    matches = [row for row in barangays(city['code']) if normalized(row[1]) == normalized(values.get('barangay'))]
    if len(matches) != 1:
        form.add_error('barangay', f"Select a barangay belonging to {city['name']}.")
    else:
        values['barangay'] = matches[0][1]
    values['city'] = city['value']


class NewIntakeValidationMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        is_pdao = 'application_type' in self.fields
        required = ['house_street', 'barangay', 'city', 'region', 'email', 'civil_status', 'education', 'employment_status']
        required += (['province', 'sex', 'disability_types', 'disability_cause',
                      'emergency_name', 'emergency_relationship', 'father_first_name', 'father_last_name',
                      'mother_first_name', 'mother_last_name'] if is_pdao else
                     ['zip_code', 'nationality', 'gender', 'family_members', 'four_ps_member', 'disability_type'])
        for name in required:
            self.fields[name].required = True
            if isinstance(self.fields[name], forms.ChoiceField) and not isinstance(self.fields[name], forms.MultipleChoiceField):
                self.fields[name].choices = [('', 'Select an option')] + [(key, label) for key, label in self.fields[name].choices if key]
        for name in ('contact_number', 'spouse_contact', 'guardian_contact', 'emergency_phone'):
            if name in self.fields:
                self.fields[name] = PhilippineMobileField(label=self.fields[name].label,
                    required=name in ('contact_number', 'emergency_phone'))
        born = self.fields['birthdate']
        born.widget.attrs.update(max=latest_birthdate(today).isoformat(),
                                 **{'data-intake-today': today.isoformat()})
        born.help_text = 'Applicants must be at least 5 years old on the application date.'
        for name in ('city', 'province', 'region', 'barangay'):
            if name in self.fields:
                self.fields[name].widget.attrs.update({'data-address-level': name, 'autocomplete': 'off'})
        self.fields['city'].help_text = ('Type and select your city / municipality, then its barangay. '
            'Region and province must match. Address list: Philippine Statistics Authority, PSGC, June 2026.')
        self.fields['region'].help_text = 'Filled from the selected city / municipality. Choose a matching region.'
        self.fields['barangay'].help_text = 'Select your city / municipality first to see its barangays.'
        address_order = ('house_street', 'city', 'province', 'region', 'barangay', 'zip_code',
                         'landline', 'contact_number', 'email')
        self.groups = tuple((title, tuple(name for name in address_order if name in names)
                            if 'house_street' in names else names) for title, names in self.groups)
        if is_pdao:
            for name in ('father_middle_name', 'mother_middle_name'):
                self.fields[name].label += ' (if any)'
            self.fields['date_applied'].disabled = True
            self.initial['date_applied'] = today
            self.fields['date_applied'].help_text = 'Set automatically to today in Philippine time when you submit.'
            self.fields['landline'].help_text = 'Optional if you do not have a landline.'
            self.fields['disability_cause_details'].help_text = 'Select the listed details only when applicable.'
        else:
            self.fields['zip_code'].widget.attrs.update(pattern='[0-9]{4}', maxlength=4)
            self.fields['family_members'].min_value = 1
            self.fields['family_members'].widget.attrs['min'] = 1
            self.fields['spouse_name'].help_text = 'Required when civil status is Married.'
            self.fields['spouse_contact'].help_text += ' Required when civil status is Married.'
            self.fields['guardian_name'].help_text = 'Required for applicants under 18, or when providing a guardian contact.'
            self.fields['guardian_contact'].help_text += ' Required for applicants under 18, or when providing a guardian name.'
        try:
            born_value = self.data.get('birthdate') if self.is_bound else self.initial.get('birthdate')
            born_value = self.fields['birthdate'].clean(born_value)
        except forms.ValidationError:
            born_value = None
        child = born_value is not None and age_at(born_value, today) <= CHILD_MAX_AGE
        for name, allowed in (('education', CHILD_EDUCATION), ('employment_status', CHILD_EMPLOYMENT)):
            field = self.fields[name]
            all_choices = list(field.choices)
            field.widget.attrs.update({
                'data-age-choices': json.dumps(all_choices),
                'data-child-values': json.dumps(allowed),
                'data-child-max-age': CHILD_MAX_AGE,
            })
            field.help_text = ('For applicants under 15, choose education up to elementary.'
                               if name == 'education' else
                               'For applicants under 15, choose Student or Unemployed, as applicable.')
            if child:
                field.choices = [(key, label) for key, label in all_choices if not key or key in allowed]
                field.error_messages['invalid_choice'] = (
                    'Applicants under 15 can select education only up to elementary.' if name == 'education' else
                    'Applicants under 15 must select Student or Unemployed.')
        self.style_fields()

    def clean(self):
        values = super().clean()
        today = timezone.localdate()
        born = values.get('birthdate')
        if born and age_at(born, today) < 5:
            self.add_error('birthdate', 'Applicants must be at least 5 years old on the application date.')
        validate_address(self, values)
        if 'zip_code' in values and not re.fullmatch(r'[0-9]{4}', values['zip_code'] or ''):
            self.add_error('zip_code', 'Enter a four-digit Philippine ZIP code.')
        if 'family_members' in values and values['family_members'] is not None and values['family_members'] < 1:
            self.add_error('family_members', 'Include the applicant; enter at least 1 family member.')
        required = []
        if 'spouse_name' in self.fields and values.get('civil_status') == 'Married':
            required += ['spouse_name', 'spouse_contact']
        if 'guardian_name' in self.fields and (
                (born and age_at(born, today) < 18) or values.get('guardian_name') or values.get('guardian_contact')):
            required += ['guardian_name', 'guardian_contact']
        if 'application_type' in self.fields:
            # Even a form held open over midnight records the server's current day.
            values['date_applied'] = today
            if values.get('application_type') == 'Renewal':
                required.append('pwd_number')
            if values.get('employment_status') == 'Employed':
                required += ['employment_category', 'employment_nature', 'occupation']
            elif values.get('employment_status') == 'Self employed':
                required.append('occupation')
            if born and age_at(born, today) <= CHILD_MAX_AGE:
                for name in ('employment_category', 'employment_nature', 'occupation', 'occupation_other'):
                    if values.get(name):
                        self.add_error(name, 'Employment details do not apply to applicants under 15.')
        for name in required:
            if not values.get(name) and name not in self.errors:
                self.add_error(name, 'Complete this field for the details you selected.')
        return values
