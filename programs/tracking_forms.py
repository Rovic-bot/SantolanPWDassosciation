from django import forms


class ApplicationTrackingForm(forms.Form):
    reference = forms.CharField(label='Application reference number', max_length=40,
        help_text='Use the reference on your program application receipt.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control', 'autocomplete': 'off'})

