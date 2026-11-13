"""Explicit claimed-ID to pending Association intake; no automatic approval."""
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, QueryDict
from django.utils import timezone

from . import pdao_services as pdao, registration_services as association
from .forms import StyledForm
from .number_fields import NumberStringField
from .pdao_models import PDAOIDClaim, PDAORegistration
from .pdf_registration_forms import ASSOCIATION_PDF_KIND
from .registration_forms import OnsiteRegistrationForm
from .registration_models import RegistrationIntake, registration_write
from .registration_policy import RegistrationUnavailable, policy_for

DISABILITIES = {
    'Deaf / Hard of Hearing': 'Hearing',
    'Intellectual Disability': 'Intellectual',
    'Learning Disability': 'Learning and Behavioral',
    'Mental Disability': 'Mental Disability',
    'Physical Disability': 'Physical / Orthopedic',
    'Psychosocial Disability': 'Psychosocial',
    'Speech / Language Impairment': 'Speech',
    'Visual Disability': 'Visual Disability',
    'Cancer (RA 11215)': 'Cancer (R.A. 11215)',
    'Rare Disease (RA 10747)': 'Rare Disease (R.A. 10747)',
}


class IDClaimForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    pwd_number = NumberStringField(label='Issued PWD ID number', max_length=80, hyphenated=True)
    confirmed = forms.BooleanField(label='I confirm that the applicant or authorized representative has received this PWD ID.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


def record_claim(key, *, user, data):
    form = IDClaimForm(data)
    if not form.is_valid():
        raise ValidationError('Enter the issued PWD ID number and confirm actual collection.')
    with transaction.atomic(), registration_write():
        actor = pdao.require_staff(user, pdao.FORWARD)
        registration = PDAORegistration.objects.select_for_update().filter(pk=key).first()
        if not registration:
            raise Http404
        existing = PDAOIDClaim.objects.filter(registration=registration).first()
        if existing:
            if existing.pwd_number == form.cleaned_data['pwd_number']:
                return existing
            raise ValidationError('A different ID claim is already recorded. Review the retained record.')
        if registration.status != 'forwarded' or registration.version != form.cleaned_data['version']:
            raise ValidationError('Reload the forwarded PDAO application before recording ID collection.')
        claim = PDAOIDClaim.objects.create(registration=registration,
            pwd_number=form.cleaned_data['pwd_number'], actor=actor, actor_label=actor.get_username())
        registration.version += 1
        registration.save(update_fields=['version'])
        pdao.record_event(registration, 'id_claimed', actor,
            details={'claim': str(claim.pk), 'collection_confirmed': True})
        pdao.require_staff(actor, pdao.FORWARD)
        return claim


def require_actor(user):
    actor = pdao.require_staff(user)
    association.require_staff(actor, 'membership.encode_registrationintake')
    return actor


def initial_data(claim):
    source = claim.registration.current_data
    names = ('last_name', 'first_name', 'middle_name', 'suffix', 'birthdate', 'house_street', 'barangay',
             'city', 'region', 'contact_number', 'email', 'philhealth_number')
    values = {name: source[name] for name in names if source.get(name)}
    # An explicitly blank middle name or suffix is part of the recorded name.
    values.update({name: source.get(name, '') for name in ('middle_name', 'suffix')})
    values.update(pwd_number=claim.pwd_number)
    if source.get('sex') in ('Male', 'Female'):
        values['gender'] = source['sex']
    civil = {'Single': 'Single', 'Married': 'Married', 'Separated': 'Separated',
             'Widow/er': 'Widower', 'Cohabitation (Live-in)': 'Co-habitation'}
    if source.get('civil_status') in civil:
        values['civil_status'] = civil[source['civil_status']]
    employment = {'Employed': 'employed', 'Unemployed': 'unemployed', 'Self employed': 'self_employed'}
    if source.get('employment_status') in employment:
        values['employment_status'] = employment[source['employment_status']]
    # PDAO 'College' does not establish graduation; transfer exact equivalents only.
    if source.get('education') in ('Elementary', 'Vocational'):
        values['education'] = source['education']
    mapped = list(dict.fromkeys(DISABILITIES[value] for value in source.get('disability_types', []) if value in DISABILITIES))
    if len(mapped) == 1:
        values['disability_type'] = mapped[0]
    return values, mapped


def merged_data(data, initial):
    values = QueryDict('', mutable=True)
    for key in data:
        values.setlist(key, data.getlist(key) if hasattr(data, 'getlist') else
                       data[key] if isinstance(data[key], (tuple, list)) else [data[key]])
    for key, value in initial.items():
        values[key] = str(value)
    return values


class PDAOAssociationForm(OnsiteRegistrationForm):
    membership_requested = forms.BooleanField(label='The applicant wants to apply for Association membership and agrees to reuse these PDAO details for the application.')

    def __init__(self, data=None, files=None, *, claim, policy):
        if policy.get('applicant_profile') != ASSOCIATION_PDF_KIND:
            raise RegistrationUnavailable('The Association membership form is not configured for PDAO transfer.')
        self.carried, self.mapped_disabilities = initial_data(claim)
        super().__init__(merged_data(data, self.carried) if data is not None else None,
                         files, initial=self.carried, policy=policy)
        for name in self.carried:
            self.fields[name].disabled = True
        if len(self.mapped_disabilities) > 1:
            self.fields['disability_type'].choices = [('', 'Select the type for the membership form')] + [
                (value, value) for value in self.mapped_disabilities]
            self.fields['disability_type'].help_text = (
                'Your PDAO record includes multiple types. The membership form records one type; select it from your recorded classifications.')

    @property
    def submission_data(self):
        # Consent belongs to the transfer operation, not the ordinary form contract.
        values = self.data.copy()
        values.pop('membership_requested', None)
        return values


def submit_membership(key, *, user, context_id, binding, data, files=None):
    saved = []
    try:
        return _submit_membership(key, user=user, context_id=context_id, binding=binding,
                                  data=data, files=files, saved=saved)
    except Exception:
        association._cleanup(saved)
        raise


def _submit_membership(key, *, user, context_id, binding, data, files, saved):
    with transaction.atomic(), registration_write():
        actor = require_actor(user)
        registration = PDAORegistration.objects.select_for_update().filter(pk=key).first()
        if not registration:
            raise Http404
        claim = PDAOIDClaim.objects.select_for_update().filter(registration=registration).first()
        if not claim:
            raise ValidationError('Record actual PWD ID collection before starting the membership application.')
        if claim.membership_intake_id:
            return claim.membership_intake
        context, _ = association._context(context_id, binding, user=actor, channel='walk_in')
        if RegistrationIntake.objects.filter(context=context).exists():
            raise ValidationError('This form was already used. Open the membership button again.')
        form = PDAOAssociationForm(data, files, claim=claim, policy=policy_for('staff'))
        if not form.is_valid():
            raise ValidationError('Complete the remaining membership fields and confirm the applicant wants to apply.')
        intake = association.submit_registration(context_id, binding, form.submission_data, files,
            user=actor, channel='walk_in', _saved_files=saved)
        claim.membership_intake = intake
        claim.membership_started_at = timezone.now()
        claim.membership_started_by = actor
        claim.save(update_fields=['membership_intake', 'membership_started_at', 'membership_started_by'])
        registration.version += 1
        registration.save(update_fields=['version'])
        pdao.record_event(registration, 'membership_started', actor, details={
            'intake': str(intake.pk), 'reference': intake.reference, 'consent_confirmed': True,
            'source_version': registration.version - 1, 'mapped_disabilities': form.mapped_disabilities})
        require_actor(actor)
        return intake
