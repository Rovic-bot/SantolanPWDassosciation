from django import forms
from members.disability_catalog import current_types
from members.models import Member


class IntakeForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.HiddenInput, forms.CheckboxSelectMultiple)):
                continue
            widget.attrs['class'] = 'form-check-input' if isinstance(widget, forms.CheckboxInput) else 'form-select' if isinstance(widget, forms.Select) else 'form-control'


class MembershipVerificationForm(IntakeForm):
    control_number = forms.CharField(max_length=100, label='Association Control Number')
    full_name = forms.CharField(max_length=200, label='Full Name',
        help_text='Enter your registered full name, including your recorded middle name and suffix, if any.')
    disability_types = forms.ModelMultipleChoiceField(queryset=current_types(),
        widget=forms.CheckboxSelectMultiple, label='Disability type * (select all that apply)')
    disability_cause = forms.ChoiceField(choices=[('', 'Select cause'),
        ('congenital', 'Congenital / Inborn'), ('acquired', 'Acquired')], label='Cause of Disability *')
    disability_visibility = forms.ChoiceField(choices=[('', 'Select visibility'),
        ('apparent', 'Apparent'), ('non_apparent', 'Non-apparent')], label='Disability Visibility *')
    version = forms.IntegerField(widget=forms.HiddenInput)


class SourceReviewForm(IntakeForm):
    expected = forms.CharField(widget=forms.HiddenInput)
    state = forms.ChoiceField(choices=[('VERIFIED', 'Verified'), ('DISPUTED', 'Disputed'), ('REJECTED', 'Rejected')])
    value = forms.CharField(max_length=100, required=False, label='Observed SI measurement',
        help_text='Record the measurement actually established by the document under this program’s authorized definition. This is not an EWAF score.')
    observation_start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    observation_end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    confirmed = forms.BooleanField(label='I reviewed the protected evidence and verified the displayed onsite sources.')


class SourcePolicyForm(IntakeForm):
    expected = forms.CharField(widget=forms.HiddenInput)
    requirement = forms.ModelChoiceField(queryset=None, label='Required program socioeconomic document')
    measure = forms.CharField(max_length=1000, label='Authorized SI measurement', widget=forms.Textarea(attrs={'rows': 2}))
    unit = forms.CharField(max_length=80)
    lower = forms.DecimalField(max_digits=16, decimal_places=4, label='Authorized lower normalization bound')
    upper = forms.DecimalField(max_digits=16, decimal_places=4, label='Authorized upper normalization bound')
    direction = forms.ChoiceField(choices=[('benefit', 'Higher observed measurement means greater need'),
        ('inverse', 'Lower observed measurement means greater need')])
    observation_period = forms.CharField(max_length=1000, label='Authorized observation-period rule')
    freshness_days = forms.IntegerField(min_value=1, max_value=36500, label='Authorized evidence validity in days')
    authority_reference = forms.CharField(max_length=500)
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    confirmed = forms.BooleanField(label='I authorize these exact source definitions under the stated program authority.')

    def __init__(self, *args, program, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['requirement'].queryset = program.configured_requirements.filter(is_active=True, is_required=True, kind='document')
