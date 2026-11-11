from django import forms
from programs.models import Program, ProgramApplication


class ReportFilterForm(forms.Form):
    start = forms.DateField(required=False, label='From date', widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(required=False, label='To date', widget=forms.DateInput(attrs={'type': 'date'}))
    program = forms.ModelChoiceField(queryset=Program.objects.all(), required=False, empty_label='All programs')
    status = forms.ChoiceField(required=False)
    assistance_type = forms.ChoiceField(required=False)

    def __init__(self, *args, kind, **kwargs):
        super().__init__(*args, **kwargs)
        choices = {
            'members': [('active', 'Active'), ('inactive', 'Inactive'), ('archived', 'Archived')],
            'applications': ProgramApplication.Status.choices,
            'programs': Program.Status.choices,
            'assistance': [('received', 'Received'), ('voided', 'Voided')],
        }
        self.fields['status'].choices = [('', 'All statuses' if kind != 'assistance' else 'Received (non-voided)')] + list(choices[kind])
        if kind == 'members':
            self.fields.pop('program')
            self.fields.pop('assistance_type')
        else:
            self.fields['assistance_type'].choices = [('', 'All assistance types')] + [
                (value, value) for value in Program.objects.order_by('assistance_type')
                .values_list('assistance_type', flat=True).distinct()]
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'

    def clean(self):
        values = super().clean()
        if values.get('start') and values.get('end') and values['start'] > values['end']:
            raise forms.ValidationError('From date must be on or before To date.')
        return values
