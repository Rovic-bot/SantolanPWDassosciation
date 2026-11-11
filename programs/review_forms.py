"""Human-readable program qualification findings over the retained evidence contract."""
from django import forms
from ewaf.evidence import source_context, digest
from ewaf.models import CriterionAssessment


class QualificationForm(forms.Form):
    expected_context = forms.CharField(widget=forms.HiddenInput)
    expected_revision = forms.IntegerField(widget=forms.HiddenInput)
    policy_id = forms.IntegerField(widget=forms.HiddenInput)
    value = forms.ChoiceField(label='Program qualification finding')
    reason = forms.CharField(label='Review reason', max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))
    confirmed = forms.BooleanField(label='I verified functional need and each applicable program requirement against the cited evidence.')

    def __init__(self, *args, application, policy, **kwargs):
        super().__init__(*args, **kwargs)
        self.policy = policy
        rule = policy.snapshot['criteria']['PR']
        self.items = (rule.get('rubric_definition') or {}).get('items', [])
        latest = CriterionAssessment.objects.filter(application=application, criterion='PR').first()
        self.initial.update(expected_context=digest(source_context(application)),
                            expected_revision=latest.revision if latest else 0, policy_id=policy.pk)
        self.fields['value'].choices = [('', 'Choose a finding'), *rule.get('categories', {}).items()]
        choices = []
        for document in application.member.application.documents.all():
            verification = document.verifications.first()
            if verification:
                choices.append((verification.pk, f'{document.label} — {verification.reviewed_at:%Y-%m-%d}'))
        for index, item in enumerate(self.items):
            label = item['id'].replace('_', ' ').capitalize()
            self.fields[f'outcome_{index}'] = forms.ChoiceField(label=label,
                choices=[('', 'Choose an outcome'), *item['outcomes'].items()])
            self.fields[f'explanation_{index}'] = forms.CharField(label=label + ' explanation',
                max_length=500, widget=forms.Textarea(attrs={'rows': 2}))
            self.fields[f'reviews_{index}'] = forms.MultipleChoiceField(label=label + ' supporting evidence',
                choices=choices, widget=forms.CheckboxSelectMultiple)
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs['class'] = ('form-check-input' if isinstance(field.widget, forms.CheckboxInput)
                    else 'profile-checkboxes' if isinstance(field.widget, forms.CheckboxSelectMultiple)
                    else 'form-select' if isinstance(field.widget, forms.Select) else 'form-control')

    def findings(self):
        return [{'item_id': item['id'], 'outcome': self.cleaned_data[f'outcome_{index}'],
                 'explanation': self.cleaned_data[f'explanation_{index}'],
                 'review_ids': [int(value) for value in self.cleaned_data[f'reviews_{index}']]}
                for index, item in enumerate(self.items)]


class SimpleQualificationForm(QualificationForm):
    """One evidence picker and shared remarks, with explicit per-rule decisions."""
    simplified = forms.BooleanField(initial=True, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = self.fields['reviews_0'].choices if self.items else []
        self.fields['evidence'] = forms.MultipleChoiceField(
            label='Documents reviewed', choices=choices, widget=forms.CheckboxSelectMultiple)
        self.fields['value'].label = 'Program fit'
        self.fields['value'].widget = forms.RadioSelect(choices=list(self.fields['value'].choices)[1:])
        self.fields['reason'].label = 'Review remarks'
        self.fields['reason'].max_length = 500
        self.fields['reason'].widget.attrs['maxlength'] = 500
        self.fields['confirmed'].label = 'I checked the selected documents and each applicable requirement.'
        labels = {row['id']: row['label'] for row in kwargs['application'].requirements_snapshot}
        for index, item in enumerate(self.items):
            field = self.fields[f'outcome_{index}']
            field.label = labels.get(item['requirement_id'], 'Program requirement')
            field.widget = forms.RadioSelect(choices=list(field.choices)[1:])
            del self.fields[f'explanation_{index}']
            del self.fields[f'reviews_{index}']

    def findings(self):
        from documents.models import DocumentVerification
        selected = DocumentVerification.objects.filter(pk__in=self.cleaned_data['evidence']).select_related('document__requirement')
        results = []
        for index, item in enumerate(self.items):
            mapped = {(row['document_type_id'], row['membership_requirement_id']) for row in item['evidence_mappings']}
            ids = [row.pk for row in selected if
                   (row.document.requirement.document_type_id, row.document.requirement_id) in mapped]
            results.append({'item_id': item['id'], 'outcome': self.cleaned_data[f'outcome_{index}'],
                            'explanation': self.cleaned_data['reason'], 'review_ids': ids})
        return results


from assistance.forms import EligibilityForm
from membership.forms import StyledForm


class ApplicationDecisionForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    member_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    program_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    expected_context = forms.CharField(max_length=64, widget=forms.HiddenInput)
    eligibility = forms.ChoiceField(choices=[('eligible', 'Eligible'), ('review', 'Needs Information'),
                                            ('ineligible', 'Ineligible')])
    notes = forms.CharField(required=False, max_length=2000, label='Remarks',
                           widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, application, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.update(version=application.version, member_version=application.member.version,
                            program_version=application.program.version,
                            expected_context=digest(source_context(application)))
        self.style_fields()

    def clean(self):
        values = super().clean()
        if values.get('eligibility') in ('review', 'ineligible') and not values.get('notes', '').strip():
            message = ('Describe the information the applicant needs to provide.' if values['eligibility'] == 'review'
                       else 'Explain why the application is ineligible.')
            self.add_error('notes', message)
        return values


class SimpleEligibilityForm(EligibilityForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['eligibility'].widget = forms.HiddenInput()
        self.fields['notes'].label = 'Remarks / reason'
        self.fields['notes'].widget.attrs['rows'] = 2
        self.fields['other_requirements'].label = 'Program instructions'
        self.fields['other_requirements'].initial = 'review'
        for name, field in self.fields.items():
            if name.startswith('check_') or name == 'other_requirements':
                field.help_text = ''
                field.widget = forms.RadioSelect(choices=[
                    ('review', 'Needs information'), ('pass', 'Verified'), ('fail', 'Not met')])

    @property
    def checklist_fields(self):
        return [self[name] for name in self.fields if name.startswith('check_') or name == 'other_requirements']

    @property
    def checklist_errors(self):
        return any(field.errors for field in self.checklist_fields)
