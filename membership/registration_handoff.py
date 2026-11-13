"""Pending intake -> existing onsite writer, with no direct Member/EWAF writes.

The configured procedure references must be actual institutional approvals in
operation. Synthetic test contracts are deliberately not ordinary defaults.
"""
from django import forms
import hashlib
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import QueryDict
from django.utils import timezone

from .forms import ApplicationForm, PROFILE_FIELDS, fingerprint, requirements_snapshot
from .registration_models import RegistrationIntake, registration_write
from .registration_policy import RegistrationUnavailable, digest, policy_for
from .registration_profile import INPUT_FIELDS, PROFILE_KIND
from .pdf_registration_forms import ASSOCIATION_PDF_KIND

HANDOFF_PROCEDURES = ('identity_procedure_reference', 'requirements_procedure_reference',
    'assessment_procedure_reference', 'identifier_procedure_reference',
    'decision_authority_reference', 'membership_requirements_fingerprint')


def contract_digest(policy):
    # Pausing public collection or changing a request budget must not strand an
    # already accepted onsite review. Actual acceptance/authority changes block.
    keys = HANDOFF_PROCEDURES + ('authority_reference', 'staff_assignments_reference',
                                'onsite_procedure_reference', 'onsite_methods')
    return digest({key: policy[key] for key in keys})


def handoff_policy():
    policy = policy_for('onsite')
    if policy.get('handoff_enabled') is not True:
        raise RegistrationUnavailable('Membership handoff is not configured for this environment.')
    if any(not isinstance(policy.get(key), str) or not policy[key].strip() for key in HANDOFF_PROCEDURES):
        raise RegistrationUnavailable('The membership handoff procedures are incomplete.')
    if policy['membership_requirements_fingerprint'] != fingerprint(requirements_snapshot()):
        raise RegistrationUnavailable('The onsite upload requirements need reconciliation and approval.')
    return policy


def handoff_available():
    try:
        handoff_policy()
        return True
    except RegistrationUnavailable:
        return False


def require_handoff_actor(user):
    from .registration_services import require_staff
    actor = require_staff(user, 'membership.onsite_registrationintake')
    if not actor.has_perms(['membership.encode_membershipapplication',
                            'membership.view_registration_documents',
                            'documents.view_membershipapplicationdocument']):
        raise PermissionDenied
    return actor


class HandoffForm(ApplicationForm):
    """Immutable applicant fields plus staff-recorded onsite acceptance basis."""
    identity_basis = forms.CharField(max_length=2000, label='Identity and representative verification findings',
        widget=forms.Textarea(attrs={'rows': 3}))
    requirements_basis = forms.CharField(max_length=2000, label='Acceptance findings for the completed form and all Association requirements',
        help_text='Record findings under the approved procedure, including the physical long envelope. Sightings alone are not acceptance.',
        widget=forms.Textarea(attrs={'rows': 3}))
    assessor = forms.CharField(max_length=150, label='Responsible socioeconomic assessor')
    assessed_on = forms.DateField(label='Assessment date', widget=forms.DateInput(attrs={'type': 'date'}))
    assessment_basis = forms.CharField(max_length=2000, label='Completed socioeconomic assessment and its record reference',
        help_text='Use the actual authorized assessment. This does not create an EWAF assessment or score.',
        widget=forms.Textarea(attrs={'rows': 3}))
    control_number_basis = forms.CharField(max_length=2000, label='Source of the legitimately assigned control number',
        widget=forms.Textarea(attrs={'rows': 2}))
    duplicate_review = forms.CharField(max_length=2000, label='Existing-member and duplicate review findings',
        help_text='Unresolved identity or existing-member matches must be resolved before continuing. Never merge solely by name.',
        widget=forms.Textarea(attrs={'rows': 2}))
    accepted = forms.BooleanField(label='I am authorized to record these completed onsite checks and assessment; no prerequisite remains unresolved.')
    basis_fields = ('identity_basis', 'requirements_basis', 'assessor', 'assessed_on',
                    'assessment_basis', 'control_number_basis', 'duplicate_review', 'accepted')

    def __init__(self, data=None, files=None, *, intake, policy):
        self.intake = intake
        self.revision = intake.revisions.get(number=intake.current_revision)
        self.handoff_contract = policy
        source = self.revision.data
        self.pdf_profile = source.get('profile_kind') == ASSOCIATION_PDF_KIND
        if source.get('profile_kind') not in (PROFILE_KIND, ASSOCIATION_PDF_KIND):
            raise RegistrationUnavailable('This older form requires authorized field reconciliation before handoff.')
        if source['profile_kind'] == ASSOCIATION_PDF_KIND:
            # Only directly equivalent declarations are prefilled. Family size
            # is not dependents; 4Ps is not income; a PWD ID is not an Association
            # control number. Staff complete the separate onsite assessment.
            initial = {name: source[name] for name in (
                'first_name', 'middle_name', 'last_name', 'birthdate', 'barangay', 'contact_number', 'email')}
            initial.update(municipality=source['city'], no_middle_name=not source['middle_name'])
            if not initial['contact_number']:
                # A blank optional online contact must not freeze an internally
                # required field; staff can collect it during onsite completion.
                initial.pop('contact_number')
        else:
            initial = {name: source[name] for name in INPUT_FIELDS}
        if data is not None:
            # Ignore tampered applicant fields. Corrections must be retained as
            # a new pending revision before handoff, never hidden in this form.
            merged = QueryDict('', mutable=True)
            for key in data:
                merged.setlist(key, data.getlist(key) if hasattr(data, 'getlist') else
                               data[key] if isinstance(data[key], (list, tuple)) else [data[key]])
            for name, value in initial.items():
                merged.setlist(name, value if isinstance(value, list) else [value])
            data = merged
        super().__init__(data, files, initial=initial)
        self.initial.update(initial)  # shared profile mixin initializes this M2M
        for name in initial:
            self.fields[name].disabled = True
        if self.pdf_profile:
            for name in PROFILE_FIELDS + ('disability_types', 'disability_selection_present'):
                if name != 'control_number':
                    self.fields.pop(name, None)
            self.registration_values = {name: source.get(name) for name in
                ('household_monthly_income', 'household_members')}
            self.registration_values['registration_profile'] = source
        self.fields['control_number'].label = 'Assigned Association control number'
        self.fields['control_number'].help_text = 'Use the legitimate identifier required by the approved existing membership procedure. The AMR reference is not this number.'
        self.initial['submission_token'] = signing.dumps({'key': str(intake.request_key),
            'requirements': fingerprint(self.snapshot), 'registration': intake.reference,
            'revision': intake.current_revision, 'version': intake.version,
            'contract': contract_digest(policy)}, salt='membership.submit')
        self.style_fields()

    @property
    def submitted_sections(self):
        source = self.revision.data
        return [(title, [(label, value) for label, value in rows if value != 'Not provided'])
                for title, rows in source.get('profile_sections', []) + source.get('digital_sections', [])]

    def clean(self):
        if not self.pdf_profile:
            return super().clean()
        values = forms.ModelForm.clean(self)
        self.clean_uploads()
        source = self.revision.data
        from .models import MembershipApplication
        from members.models import DisabilityType
        blank = MembershipApplication()
        # Sparse PDF declarations stay sparse. No invented dependent count,
        # individual income, classification, or socioeconomic assessment.
        values.update({name: getattr(blank, name) for name in PROFILE_FIELDS if name != 'control_number'})
        from .pdf_registration_forms import stored_name_suffix
        values.update(stored_name_suffix(source))
        for name in ('full_name', 'first_name', 'middle_name', 'last_name', 'address', 'contact_number', 'email', 'barangay'):
            values[name] = source.get(name, '')
        from datetime import date
        values['birthdate'] = date.fromisoformat(source['birthdate'])
        values.update(municipality=source['city'], no_middle_name=not source.get('middle_name'),
            disability_information=source.get('disability_type', ''),
            employment_status=source.get('employment_status', ''),
            employment_information=source.get('employment_status', '').replace('_', ' '))
        values['disability_types'] = DisabilityType.objects.filter(name=source.get('disability_type', ''), is_active=True)
        return values

    def _post_clean(self):
        if not self.pdf_profile:
            return super()._post_clean()
        # ModelForm cannot construct removed controls from a sparse source form.
        # Validate the remaining assigned identifier through its native model field.
        field = self.instance._meta.get_field('control_number')
        if 'control_number' in self.cleaned_data:
            try:
                field.clean(self.cleaned_data['control_number'], self.instance)
            except ValidationError as error:
                self.add_error('control_number', error)

    def clean_submission_token(self):
        key = super().clean_submission_token()
        token = signing.loads(self.data.get('submission_token', ''), salt='membership.submit', max_age=86400)
        if (key != self.intake.request_key or token.get('registration') != self.intake.reference
                or token.get('revision') != self.intake.current_revision
                or token.get('contract') != contract_digest(self.handoff_contract)
                or type(token.get('version')) is not int):
            raise ValidationError('Reload the current registration review before continuing.')
        self.registration_version = token['version']
        return key

    def clean_assessed_on(self):
        value = self.cleaned_data['assessed_on']
        if value > timezone.localdate():
            raise ValidationError('An assessment cannot be recorded in the future.')
        return value

    def clean_control_number(self):
        value = super().clean_control_number()
        if value.startswith('AMR-'):
            raise ValidationError('Use the legitimately assigned control number, not a registration reference.')
        return value

    def basis(self):
        return {key: self.cleaned_data[key].isoformat() if key == 'assessed_on' else self.cleaned_data[key]
                for key in self.basis_fields}

    @property
    def acceptance_fields(self):
        return [self[key] for key in self.basis_fields]

    def request_digest(self):
        files = {}
        for key in self.files:
            upload = self.files[key]
            value = hashlib.sha256()
            for chunk in upload.chunks():
                value.update(chunk)
            upload.seek(0)
            files[key] = {'sha256': value.hexdigest(), 'size': upload.size, 'type': upload.content_type}
        return digest({'revision': self.revision.pk, 'control_number': self.cleaned_data['control_number'],
                       'basis': self.basis(), 'requirements': self.snapshot, 'files': files})


def lock_handoff(form, user, reference):
    """Called INSIDE the native writer transaction, after its settings lock."""
    require_handoff_actor(user)
    policy = handoff_policy()
    if not isinstance(form, HandoffForm) or not form.is_valid() or form.snapshot != requirements_snapshot():
        raise ValidationError('Use the validated current registration handoff form.')
    intake = RegistrationIntake.objects.select_for_update().get(reference=reference)
    if (intake.pk != form.intake.pk or intake.current_revision != form.revision.number
            or contract_digest(policy) != contract_digest(form.handoff_contract)):
        raise ValidationError('The registration or procedure changed. Reload before continuing.')
    if intake.membership_application_id:
        proof = intake.actions.filter(action='membership_handoff', revision=form.revision).first()
        if (not proof or proof.version_before != form.registration_version
                or proof.payload.get('basis') != form.basis()
                or proof.payload.get('request_digest') != form.request_digest()
                or proof.payload.get('control_number') != form.cleaned_data['control_number']):
            raise ValidationError('This registration is already linked. Open its existing membership review.')
        return intake
    if intake.version != form.registration_version or intake.state != 'onsite_review':
        raise ValidationError('Record current onsite findings and reload before preparing membership review.')
    observation = intake.actions.filter(action='onsite_observations', revision=form.revision).last()
    if not observation or observation.payload.get('procedure') != policy['onsite_procedure_reference']:
        raise ValidationError('Record current onsite findings under the approved procedure.')
    findings = observation.payload.get('findings', {})
    from .registration_forms import OnsiteForm
    required_items = (OnsiteForm.pdf_keys if form.revision.data.get('profile_kind') == ASSOCIATION_PDF_KIND
                      else OnsiteForm.keys)
    if any(findings.get(key, {}).get('finding') != 'sighted'
           or findings.get(key, {}).get('method') not in policy['onsite_methods']
           for key in required_items):
        raise ValidationError('The completed form and every applicable Association checklist item must be reviewed onsite before acceptance can be recorded.')
    from members.models import Member
    from .models import MembershipApplication
    number = form.cleaned_data['control_number']
    if Member.objects.filter(control_number=number).exists() or MembershipApplication.objects.filter(
            control_number=number, status='pending').exists():
        raise ValidationError('An existing Member or pending membership review uses this control number. Resolve the duplicate first.')
    return intake


def link_handoff(intake, application, form, user):
    from .registration_services import record_action
    with registration_write():
        before = intake.version
        intake.membership_application = application
        intake.state = 'membership_review'
        intake.version += 1
        intake.save(update_fields=['membership_application', 'state', 'version'])
        record_action(intake, 'membership_handoff', form.revision, actor=user, before=before,
            reason='Authorized onsite acceptance retained; existing membership review prepared.',
            payload={'basis': form.basis(), 'policy_digest': contract_digest(form.handoff_contract),
                     'request_digest': form.request_digest(),
                     'policy': form.handoff_contract, 'control_number': application.control_number,
                     'application_reference': str(application.reference)})


def linked_intake(application_id):
    return RegistrationIntake.objects.filter(membership_application_id=application_id).first()


def require_linked_access(application_id, user, *, documents=False):
    from .registration_services import require_staff
    intake = linked_intake(application_id)
    if intake:
        require_staff(user, 'membership.view_registration_documents' if documents else 'membership.view_registrationintake')
    return intake


def guard_linked_review(application, user, capability):
    """Every legacy verification/decision entry point uses the same guard."""
    from .registration_services import require_staff
    intake = linked_intake(application.pk)
    if not intake:
        return None
    actor = require_staff(user, 'membership.review_registrationintake')
    if not actor.has_perm(capability):
        raise PermissionDenied
    policy = handoff_policy()
    intake = RegistrationIntake.objects.select_for_update().get(pk=intake.pk)
    proof = intake.actions.filter(action='membership_handoff', revision__number=intake.current_revision).first()
    if (intake.state != 'membership_review' or not proof
            or proof.payload.get('policy_digest') != contract_digest(policy)
            or application.submission_key != intake.request_key):
        raise ValidationError('The current registration acceptance or approved procedure is unavailable. No decision was made.')
    return intake


def record_linked_review(intake, application, user, action, notes):
    if intake is None:
        return
    from .registration_services import record_action
    with registration_write():
        before = intake.version
        intake.version += 1
        intake.save(update_fields=['version'])
        record_action(intake, action, intake.revisions.get(number=intake.current_revision), actor=user,
            reason=notes, before=before, payload={'application_reference': str(application.reference),
                'application_version': application.version, 'status': application.status})
