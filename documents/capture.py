"""Additive onsite uploads, using retained private documents and review services."""
from functools import wraps
from django import forms
from django.core.exceptions import ValidationError
from .models import MembershipApplicationDocument, MembershipDocumentRequirement
from .validators import validate_document, validate_upload_total


def upload_fields(form):
    from membership.forms import validate_portrait
    form.capture_requirements = list(MembershipDocumentRequirement.objects.filter(capture_key__isnull=False).select_related('document_type'))
    form.retained_documents = list(form.instance.application.documents.all()) if form.instance.pk else []
    retained = {document.requirement_id for document in form.retained_documents}
    for item in form.capture_requirements:
        form.fields[f'document_{item.pk}'] = forms.FileField(label=item.document_type.name, required=False,
            disabled=item.pk in retained, validators=[validate_document] + ([validate_portrait] if item.capture_key == 'photo_1x1' else []),
            widget=forms.FileInput(attrs={'accept': '.jpg,.jpeg,.png' if item.capture_key == 'photo_1x1' else '.pdf,.jpg,.jpeg,.png'}),
            help_text='An existing document is retained; use its protected preview and verification history.' if item.pk in retained
            else 'Add a private supporting document. Existing Association requirements remain unchanged.')


def validate_uploads(form):
    validate_upload_total(form.files)
    expected = {f'document_{item.pk}' for item in form.capture_requirements}
    retained = {f'document_{doc.requirement_id}' for doc in form.retained_documents}
    if any(name not in expected or name in retained or len(form.files.getlist(name)) != 1 for name in form.files):
        raise ValidationError('Upload one file per empty supporting-document field. Existing files cannot be overwritten.')


def save_uploads(form, application):
    from ewaf.membership_invalidation import remember_membership_upload
    for item in form.capture_requirements:
        upload = form.cleaned_data.get(f'document_{item.pk}')
        if upload:
            document = MembershipApplicationDocument(application=application, requirement=item,
                label=item.document_type.name, content_type=upload.content_type, size=upload.size)
            document.file.save(upload.name, upload, save=False)
            remember_membership_upload((document.file.storage, document.file.name))
            document.save()


def cleanup_uploads(function):
    """Wrap the complete source-writer transaction, including its final audit."""
    @wraps(function)
    def wrapped(*args, **kwargs):
        from ewaf.membership_invalidation import _uploads
        from announcements.services import remove_file
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
