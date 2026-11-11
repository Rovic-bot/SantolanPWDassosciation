from django import forms
from django.utils import timezone
from membership.forms import StyledForm
from .models import AssistanceRelease, EligibilityStatus
from .claimant import ClaimantForm


class ActionForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    notes = forms.CharField(max_length=2000, label='Remarks / reason', widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        for field in self.fields.values():
            if isinstance(field, forms.BooleanField):
                field.widget.attrs['class'] = 'form-check-input'


class EligibilityForm(ActionForm):
    member_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    program_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    eligibility = forms.ModelChoiceField(queryset=EligibilityStatus.objects.filter(is_active=True), empty_label='Choose an assessment')

    def __init__(self, *args, application, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['member_version'] = application.member.version
        self.initial['program_version'] = application.program.version
        options = [('review', 'Not yet assessed / needs further review'), ('pass', 'Meets requirement'), ('fail', 'Does not meet requirement')]
        for item in application.requirements_snapshot:
            self.fields[f'check_{item["id"]}'] = forms.ChoiceField(choices=options, initial='review',
                label=item['label'], help_text=('Required at submission. ' if item['is_required'] else 'Optional at submission. ') + item.get('instructions', ''))
        self.fields['other_requirements'] = forms.ChoiceField(choices=options,
            label='Program instructions and other requirements',
            help_text='Review the original program instructions and document your findings in remarks.')
        self.order_fields(['version', 'member_version', 'program_version', 'eligibility',
                           *[f'check_{item["id"]}' for item in application.requirements_snapshot], 'other_requirements', 'notes'])
        self.style_fields()


class DecisionForm(ActionForm):
    decision = forms.ChoiceField(choices=[('approved', 'Select participant / beneficiary'), ('rejected', 'Not Selected'), ('pending', 'Return for review')])
    confirm = forms.BooleanField(label='I confirm this administrative decision.')


class ReceiptForm(ClaimantForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    program_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)


class ReleaseForm(StyledForm, forms.ModelForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    confirm = forms.BooleanField(label='I confirm this assistance was actually released / received.')

    class Meta:
        model = AssistanceRelease
        fields = ('assistance_type', 'benefit', 'amount', 'estimated_value', 'released_on', 'reference', 'notes')
        widgets = {'released_on': forms.DateInput(attrs={'type': 'date'}), 'notes': forms.Textarea(attrs={'rows': 3})}
        labels = {'benefit': 'Assistance / benefit delivered', 'amount': 'Cash amount (PHP)',
                  'estimated_value': 'Estimated non-cash value (PHP)', 'reference': 'Receipt / release reference', 'notes': 'Release remarks'}
        help_texts = {'amount': 'Optional. Leave blank when not applicable.', 'estimated_value': 'Optional. Leave blank when not applicable.',
                      'reference': 'Optional supporting reference. Do not include sensitive document contents.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields['confirm'].widget.attrs['class'] = 'form-check-input'

    def clean_released_on(self):
        value = self.cleaned_data['released_on']
        if value > timezone.localdate():
            raise forms.ValidationError('A successful release cannot be in the future.')
        return value


class VoidForm(ActionForm):
    confirm = forms.BooleanField(label='I confirm this record is incorrect and must be excluded from received assistance.')


class StatusForm(StyledForm, forms.ModelForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    notes = forms.CharField(max_length=2000, label='Reason for configuration change', widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = EligibilityStatus
        fields = ('label', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields['is_active'].widget.attrs['class'] = 'form-check-input'
