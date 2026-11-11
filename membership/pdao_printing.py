"""Read-only projection onto the owner's Pasig PDAO Version 4.0 form.

No form preparation is a signature, government approval, or ID issuance.
Keep missing historical values blank rather than inventing declarations.
"""
from datetime import date

from .pdf_registration_forms import PDAOForm

PDAO_SOURCE_FORM = 'Pasig_PDAO_PWD_ID_Application_Editable_Google_Docs.docx'


def print_context(submitted):
    data = dict(submitted)
    options = {}
    for name, field in PDAOForm.base_fields.items():
        if not hasattr(field, 'choices'):
            continue
        value = data.get(name, '')
        selected = value if isinstance(value, list) else [value]
        options[name] = [
            {'label': label, 'checked': key in selected}
            for key, label in field.choices if key
        ]
        # Historical declarations must not disappear if the choices change.
        known = {key for key, _ in field.choices}
        options[name].extend({'label': item, 'checked': True}
                             for item in selected if item and item not in known)
    # A saved online intake is evidence of this channel, even after review.
    # The earlier planned-channel answer is not evidence of actual submission.
    options['submission_channel'] = [
        {'label': label, 'checked': data.get('intake_channel') == key}
        for key, label in [('walk_in', 'Walk-In'), ('barangay', 'Barangay'), ('online', 'Online')]]
    for name in ('birthdate', 'date_applied'):
        try:
            data[name] = date.fromisoformat(data.get(name, '')).strftime('%m/%d/%Y')
        except (TypeError, ValueError):
            pass
    return {'pdao': data, 'options': options}
