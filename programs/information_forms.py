"""Edit current member information while reviewing a reported application change."""
from django import forms

from members.registration_form import member_edit_form
from .information_confirmation import review_token


def information_update_form(data=None, *, application):
    expected = review_token(application)
    form = member_edit_form(data, instance=application.member)
    form.fields['expected'] = forms.CharField(widget=forms.HiddenInput)
    form.initial['expected'] = expected
    form.fields['notes'].required = False
    form.fields['notes'].label = 'Remarks'
    # This screen edits information. Existing protected document workflows stay
    # available on the application page; no extra upload is required here.
    for name in list(form.fields):
        if name.startswith('document_'):
            del form.fields[name]
    form.capture_requirements = []
    form.style_fields()
    return form
