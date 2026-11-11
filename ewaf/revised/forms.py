from decimal import Decimal
from django import forms
from .math import CRITERIA, NAMES, DEFAULTS, LIMITS, CalculationError, proposal


class PreviewForm(forms.Form):
    mode = forms.ChoiceField(label='New method / preview mode', choices=[
        ('DOCUMENT_EXAMPLE', 'Revised dataset v1 — document example'),
        ('DRAFT_SENSITIVITY', 'Revised dataset v1 — draft sensitivity')], widget=forms.Select(attrs={'class': 'form-select'}))
    classify = forms.BooleanField(label='Show demonstration classifications', required=False, initial=True)
    capacity = forms.IntegerField(label='Example capacity (optional)', min_value=0, required=False,
                                  widget=forms.NumberInput(attrs={'class': 'form-control'}))
    expected = forms.CharField(required=False, widget=forms.HiddenInput)
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    reason = forms.CharField(label='Note for retained history', required=False, max_length=2000,
                            widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for code, name, value, (lower, upper) in zip(CRITERIA, NAMES, DEFAULTS, LIMITS):
            self.fields[code] = forms.DecimalField(label=f'{name} ({code})', min_value=Decimal(lower),
                max_value=Decimal(upper), decimal_places=2, max_digits=5, initial=value,
                widget=forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control', 'data-proposal-number': code}))

    def clean(self):
        data = super().clean()
        if all(code in data for code in CRITERIA[:4]):
            values = {code: str(data[code]) for code in CRITERIA[:4]}
            try:
                proposal(values)
            except CalculationError as error:
                raise forms.ValidationError(str(error)) from error
            if data.get('mode') == 'DOCUMENT_EXAMPLE' and any(data[code] != Decimal(value) for code, value in zip(CRITERIA, DEFAULTS)):
                raise forms.ValidationError('Choose draft sensitivity to preview changed weights. The document example preserves its exact defaults.')
            data['proposed'] = values if data.get('mode') == 'DRAFT_SENSITIVITY' else None
        return data

    def calculation_arguments(self):
        return {key: self.cleaned_data[key] for key in ('mode', 'proposed', 'classify', 'capacity')}
