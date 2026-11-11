from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from membership.forms import PROFILE_FIELDS, StyledForm
from .models import Member
from .profile_forms import ProfileFormMixin

MEMBER_STATUSES = [('active', 'Active'), ('inactive', 'Inactive'), ('archived', 'Archived')]


class MemberForm(ProfileFormMixin, StyledForm, forms.ModelForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    notes = forms.CharField(label='Reason for this update', max_length=2000,
                           widget=forms.Textarea(attrs={'rows': 3}))

    class Meta:
        model = Member
        fields = PROFILE_FIELDS + ('disability_types',)
        widgets = {'birthdate': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
                   'address': forms.Textarea(attrs={'rows': 3}),
                   'disability_information': forms.Textarea(attrs={'rows': 3})}
        labels = {'control_number': 'PWD control number', 'monthly_income': 'Monthly income (PHP)',
                  'dependents': 'Number of dependents'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial['version'] = self.instance.version
        from documents.capture import upload_fields
        upload_fields(self)
        self.style_fields()
        from django.db.models import Q
        from .models import DisabilityType
        self.fields['disability_type'].queryset = DisabilityType.objects.filter(Q(is_active=True) | Q(pk=self.instance.disability_type_id))
        self.fields['disability_type'].help_text = 'Map legacy descriptions to an approved classification; no automatic mapping is performed.'
        self.fields['birthdate'].widget.attrs['max'] = timezone.localdate().isoformat()

    def clean_birthdate(self):
        value = self.cleaned_data['birthdate']
        if value > timezone.localdate():
            raise ValidationError('Birthdate cannot be in the future.')
        return value

    def clean_control_number(self):
        return self.cleaned_data['control_number'].strip().upper()

    def clean(self):
        result = super().clean()
        from documents.capture import validate_uploads
        validate_uploads(self)
        return result

    @property
    def document_fields(self):
        return [self[f'document_{item.pk}'] for item in self.capture_requirements]


class MemberStatusForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    status = forms.ChoiceField(choices=MEMBER_STATUSES, label='Member status')
    notes = forms.CharField(label='Reason for the status change', max_length=2000,
                           widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
