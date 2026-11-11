"""Opt-in, permission-controlled policy editing using the existing engine schema."""
import json
from django import forms
from .operational_forms import ConfigurationForm

from .household_criteria import NAMES


class MappingWidget(forms.Widget):
    template_name = 'ewaf/policy_mapping.html'

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        try:
            mapping = json.loads(value) if isinstance(value, str) else value
            rows = list((mapping or {}).items())
        except (ValueError, AttributeError):
            rows = []
        context['widget']['rows'] = [{'index': index, 'key': key, 'value': value}
            for index, (key, value) in enumerate(rows + [('', '')] * max(2, 12 - len(rows)))]
        return context

    def value_from_datadict(self, data, files, name):
        if name in data:
            return data.get(name)
        rows = {}
        for index in range(100):
            key = data.get(f'{name}_key_{index}', '').strip()
            value = data.get(f'{name}_value_{index}', '').strip()
            if key or value:
                if not key or key in rows:
                    return '{invalid mapping'
                rows[key] = value
        return json.dumps(rows) if rows else ''


class GuidedConfigurationForm(ConfigurationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {
            'authority_reference': 'Approval reference', 'authorized_scope': 'What the approval covers',
            'approval_date': 'Approval date', 'effective_from': 'Valid from', 'effective_until': 'Valid until',
            'selection_rule': 'Beneficiary decision process', 'tie_rule': 'Equal-score decisions',
            'tie_procedure': 'Approved procedure for equal scores', 'classification_mode': 'Need categories',
            'classifications': 'Approved category ranges', 'edge_cases': 'Incomplete or unsupported information',
            'pa_scope': 'Assistance programs to count', 'pa_period': 'Assistance period',
            'pa_start': 'First receipt date', 'pa_end': 'Last receipt date',
        }
        for key, label in labels.items():
            self.fields[key].label = label
        self.fields['classifications'].help_text = 'Use the approved category definitions only. Leave blank when categories are not authorized.'
        for code in self.criteria:
            for key, label in {
                'measure': 'What is assessed', 'source_type': 'Verified source', 'value_type': 'Recorded value format',
                'unit': 'Unit', 'direction': 'How the value reflects need', 'lower': 'Lowest approved value',
                'upper': 'Highest approved value', 'encoding': 'Approved category scores',
                'observation_period': 'Period covered by the evidence',
            }.items():
                field = self.fields[code + '_' + key]
                field.label = label
                field.help_text = ''
                if key == 'encoding':
                    field.widget = MappingWidget()
                    field.help_text = 'Copy the approved category names and scores exactly. Leave blank for numeric assessments.'
        for role, label in {'functional_need': 'Functional need', 'consent': 'Required consent',
                            'accessible_alternative': 'Accessible verification'}.items():
            self.fields[f'PR_{role}_item'].label = label + ' — review requirement'
            self.fields[f'PR_{role}_accepted_outcome'].label = label + ' — accepted finding'
        # Choices are from the retained approved evidence definition, never defaults.
        from .models import EvidencePolicyRevision
        policy = EvidencePolicyRevision.objects.filter(program=self.program).first()
        items = (policy.snapshot['criteria']['PR'].get('rubric_definition') or {}).get('items', []) if policy else []
        requirements = {row.pk: row.label for row in self.program.configured_requirements.all()}
        for role in ('functional_need', 'consent', 'accessible_alternative'):
            self.fields[f'PR_{role}_item'].widget = forms.Select(choices=[
                ('', 'Choose an approved requirement'),
                *[(row['id'], requirements.get(row['requirement_id'], 'Program requirement')) for row in items]],
                attrs={'class': 'form-select'})
            outcomes = {key: value for row in items for key, value in row['outcomes'].items()}
            self.fields[f'PR_{role}_accepted_outcome'].widget = forms.Select(
                choices=[('', 'Choose an approved finding'), *outcomes.items()], attrs={'class': 'form-select'})

    def sections(self):
        return [
            ('Approval', [self[name] for name in ('authority_reference', 'authorized_scope', 'approval_date', 'effective_from', 'effective_until')]),
            ('Decision rules', [self[name] for name in ('selection_rule', 'tie_rule', 'tie_procedure', 'classification_mode', 'classifications', 'edge_cases')]),
            *[(label, [self[name] for name in self.fields if name.startswith(code + '_')]) for code, label in ((code, NAMES[code]) for code in self.criteria)],
            ('Assistance history', [self[name] for name in ('pa_scope', 'pa_period', 'pa_start', 'pa_end')]),
            ('Required program checks', [self[name] for name in self.fields if name.startswith('PR_')]),
        ]
