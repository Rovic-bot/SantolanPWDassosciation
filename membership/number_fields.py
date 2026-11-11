"""Numeric form strings retain leading zeroes and optional ID separators."""
import re

from django import forms
from django.core.exceptions import ValidationError


class NumberStringField(forms.CharField):
    def __init__(self, *args, hyphenated=False, **kwargs):
        self.pattern = r'[0-9]+(?:-[0-9]+)*' if hyphenated else r'[0-9]+'
        self.number_message = ('Use digits (0-9); hyphens may separate number groups. Do not enter letters.'
                               if hyphenated else 'Use digits only (0-9). Do not enter letters.')
        self.recorded_value = None
        kwargs['widget'] = forms.TextInput(attrs={
            'inputmode': 'numeric', 'pattern': self.pattern, 'title': self.number_message,
            'data-registration-number': 'hyphens' if hyphenated else 'digits',
        })
        kwargs['help_text'] = ' '.join(filter(None, (kwargs.get('help_text'), self.number_message)))
        super().__init__(*args, **kwargs)

    def preserve_recorded_value(self, value):
        # Only server-provided initial data may preserve an older declaration.
        # New/changed submissions must satisfy the numeric contract.
        if value and not re.fullmatch(self.pattern, str(value)):
            self.recorded_value = str(value)
            self.widget.attrs.pop('pattern', None)
            self.widget.attrs.pop('data-registration-number', None)
            self.widget.attrs.pop('inputmode', None)

    def validate(self, value):
        super().validate(value)
        if value and value != self.recorded_value and not re.fullmatch(self.pattern, value):
            raise ValidationError(self.number_message, code='invalid')


def number_field(label, *, length=80, hyphenated=False, help_text=''):
    return NumberStringField(label=label, required=False, max_length=length,
                             hyphenated=hyphenated, help_text=help_text)
