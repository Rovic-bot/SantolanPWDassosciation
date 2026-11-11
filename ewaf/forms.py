from django import forms
from membership.forms import StyledForm
from .calculation import validate_configuration
from .models import ApplicationInput, Configuration


class ConfigurationForm(StyledForm, forms.ModelForm):
    class Meta:
        model = Configuration
        fields = ('name', 'si_source', 'pairwise', 'encodings', 'bounds', 'thresholds')
        help_texts = {
            'si_source': 'Choose the association-approved meaning of SI for this configuration.',
            'pairwise': 'JSON 5×5 positive reciprocal matrix in SI, ES, PA, ND, PR order. Diagonal values are 1; CR must be below 0.10.',
            'encodings': 'JSON object with ES and PR dictionaries mapping exact approved category names to numeric encodings. No values are preselected.',
            'bounds': 'JSON object with SI, ES, PA, ND and PR. Each has min, max and direction (benefit or inverse). Missing/equal/out-of-range inputs block scoring for review.',
            'thresholds': 'JSON list of objects with minimum (inclusive percentage) and label. Include zero; each band ends at the next minimum. Configure only approved thresholds.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean(self):
        values = super().clean()
        if all(name in values for name in self.Meta.fields):
            validate_configuration(Configuration(**values))
        return values


class InputForm(StyledForm, forms.ModelForm):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    notes = forms.CharField(max_length=2000, label='Assessment remarks', widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = ApplicationInput
        fields = ('relevance', 'socioeconomic')
        labels = {'relevance': 'Assessed program relevance category', 'socioeconomic': 'Socioeconomic assessment value'}
        help_texts = {'relevance': 'Use an exact category from the approved PR encoding configuration.',
                      'socioeconomic': 'Required only when the selected configuration uses a recorded SI assessment.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class GenerateForm(StyledForm, forms.Form):
    configuration = forms.ModelChoiceField(queryset=Configuration.objects.all())
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    confirm = forms.BooleanField(label='Calculate all valid eligible applicants. This does not approve anyone.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields['confirm'].widget.attrs['class'] = 'form-check-input'
