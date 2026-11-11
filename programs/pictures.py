"""Validated, private program artwork with an independent edit version."""
from contextvars import ContextVar
from functools import wraps

from django import forms
from django.core.exceptions import ValidationError

from announcements.images import prepare_image
from announcements.services import remove_file


class ProgramPictureForm(forms.Form):
    picture = forms.FileField(required=False, label='Program picture',
        widget=forms.FileInput(attrs={'accept': '.png,.jpg,.jpeg'}))
    remove_picture = forms.BooleanField(required=False, label='Remove picture and use title initials')
    picture_version = forms.IntegerField(required=False, min_value=0, widget=forms.HiddenInput)

    def clean_picture(self):
        upload = self.cleaned_data.get('picture')
        return prepare_image(upload) if upload else None

    def clean(self):
        values = super().clean()
        if values.get('picture') and values.get('remove_picture'):
            self.add_error('picture', 'Choose a new picture or remove the current one, not both.')
        return values


_uploads = ContextVar('program_picture_uploads', default=None)


def picture_uploads(function):
    """Clean new files if any part of the enclosing program save rolls back."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        journal = []
        token = _uploads.set(journal)
        try:
            return function(*args, **kwargs)
        except Exception:
            for storage, name in journal:
                remove_file(storage, name)
            raise
        finally:
            _uploads.reset(token)
    return wrapped


def save_picture(program, *, form, user, notes, address):
    from .models import ProgramPicture
    from .services import record_log
    values = form.cleaned_data
    if not (values.get('picture') or values.get('remove_picture')):
        return
    item = ProgramPicture.objects.select_for_update().filter(program=program).first()
    if (values.get('picture_version') or 0) != (item.version if item else 0):
        raise ValidationError('The program picture changed. Reload the page before continuing.')
    item = item or ProgramPicture(program=program)
    before = item.image.name
    if values.get('picture'):
        item.image.save('picture.png', values['picture'], save=False)
        _uploads.get().append((item.image.storage, item.image.name))
    else:
        item.image = ''
    item.version += 1
    item.updated_by = user
    item.save()
    record_log(program, 'picture_updated', notes or 'Program picture uploaded with the draft.',
        user=user, address=address, changes={'picture': {'before': before, 'after': item.image.name}})
    # Older files stay private and retained for the audit history.
