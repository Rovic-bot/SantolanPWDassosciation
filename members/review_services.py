"""Gated staff intake/findings only. Never writes accepted sources or EWAF."""
import hashlib
import json

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from core.permissions import require_workspace_permissions
from membership.forms import StyledForm
from .models import Member
from .review_models import InformationReview, InformationReviewAction, review_write


def policy():
    value = getattr(settings, 'INFORMATION_REVIEW_POLICY', None)
    required = ('authority', 'identity_procedure', 'staff_assignment', 'privacy_retention', 'review_procedure')
    if not isinstance(value, dict) or value.get('staff_enabled') is not True or any(
            not isinstance(value.get(key), str) or not value[key].strip() for key in required):
        raise Http404('This service is unavailable.')
    routine_basis = value.get('routine_basis', '')
    if not isinstance(routine_basis, str):
        raise Http404('This service is unavailable.')
    return {key: value[key] for key in required} | {'routine_basis': routine_basis.strip()}


def available():
    try:
        policy()
    except Http404:
        return False
    return True


def actor_for(user, *, write=False, application=None):
    actor = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
    if actor is None:
        raise PermissionDenied
    permissions = ['members.view_member', 'members.view_informationreview']
    if write:
        permissions.append('members.record_informationreview')
    if application is not None:
        permissions.extend(['programs.view_program', 'programs.view_programapplication'])
    require_workspace_permissions(actor, *permissions)
    policy()
    return actor


class IntakeForm(StyledForm, forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    kind = forms.ChoiceField(choices=InformationReview._meta.get_field('kind').choices)
    trigger = forms.ChoiceField(choices=InformationReview._meta.get_field('trigger').choices)
    declaration = forms.ChoiceField(choices=InformationReview._meta.get_field('declaration').choices)
    concern = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    identity_basis = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}),
        help_text='Record the approved onsite identity procedure used; do not copy identity-document numbers here.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()


class FindingForm(StyledForm, forms.Form):
    version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    state = forms.ChoiceField(choices=InformationReview._meta.get_field('state').choices[1:])
    reason = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))
    previous_values = forms.CharField(max_length=2000, required=False, widget=forms.Textarea(attrs={'rows': 2}))
    reported_values = forms.CharField(max_length=2000, required=False, widget=forms.Textarea(attrs={'rows': 2}))
    findings = forms.CharField(max_length=2000, required=False, widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Findings are private review notes. Accepted source corrections require their existing authorized workflow.')
    observed_on = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    effective_on = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean(self):
        values = super().clean()
        if values.get('state') == 'findings_recorded' and not (values.get('findings') and values.get('observed_on')):
            raise ValidationError('Record the findings and actual observation date.')
        if values.get('observed_on') and values['observed_on'] > timezone.localdate():
            raise ValidationError('An observation cannot be recorded as already made in the future.')
        return values


def validated(form):
    if not form.is_valid():
        raise ValidationError([str(error) for errors in form.errors.values() for error in errors])
    return form.cleaned_data


@transaction.atomic
def open_review(member_id, *, user, data, application_id=None):
    actor = actor_for(user, write=True, application=application_id)
    values = validated(IntakeForm(data))
    member = Member.objects.select_for_update().get(pk=member_id)
    application = None
    if application_id:
        from programs.models import ProgramApplication
        application = ProgramApplication.objects.filter(pk=application_id, member=member).first()
        if application is None:
            raise ValidationError('The application is unavailable for this member.')
    snapshot = policy()
    if values['kind'] == 'evaluation' and (application is None or values['trigger'] != 'clarification'):
        raise ValidationError('Evaluation clarification requires the applicant\'s own program application.')
    if values['trigger'] == 'routine' and not snapshot['routine_basis']:
        raise ValidationError('Routine checks require a documented approved selection basis.')
    digest = hashlib.sha256(json.dumps({**values, 'member': member.pk, 'application': str(application_id),
        'actor': actor.pk, 'policy': snapshot}, sort_keys=True, default=str).encode()).hexdigest()
    existing = InformationReview.objects.filter(request_key=values['request_key']).first()
    if existing:
        if existing.payload_digest != digest:
            raise ValidationError('This request was already used. Reload the form.')
        return existing
    with review_write():
        actor = actor_for(user, write=True, application=application)
        record = InformationReview.objects.create(member=member, application=application, created_by=actor,
            policy_snapshot=snapshot, payload_digest=digest, **values)
        InformationReviewAction.objects.create(review=record, actor=actor, actor_label=actor.get_username(),
            action='received', reason=record.concern, after={'state': record.state, 'version': 0})
    return record


@transaction.atomic
def record_findings(pk, *, user, data):
    actor_for(user, write=True)
    values = validated(FindingForm(data))
    record = InformationReview.objects.select_for_update().get(pk=pk)
    actor = actor_for(user, write=True, application=record.application_id)
    if record.policy_snapshot != policy():
        raise ValidationError('The approved review procedure changed. A separate reconciliation is required.')
    if record.version != values.pop('version'):
        raise ValidationError('This review changed. Reload before continuing.')
    before = {'state': record.state, 'version': record.version}
    record.state = values.pop('state')
    record.version += 1
    with review_write():
        record.save(update_fields=['state', 'version'])
        actor = actor_for(user, write=True, application=record.application_id)
        InformationReviewAction.objects.create(review=record, actor=actor, actor_label=actor.get_username(),
            action='review_note', before=before, after={'state': record.state, 'version': record.version}, **values)
    return record


def staff_status(reference, *, user, category):
    """Internal minimal projection. It is NOT an approved public disclosure contract."""
    if category == 'association':
        from membership.registration_services import require_staff, normalize_reference
        from membership.registration_models import RegistrationIntake
        require_staff(user)
        row = RegistrationIntake.objects.filter(reference=normalize_reference(reference)).first()
    elif category == 'program':
        actor = get_user_model().objects.filter(pk=getattr(user, 'pk', None)).first()
        if not actor:
            raise PermissionDenied
        require_workspace_permissions(actor, 'programs.view_program', 'programs.view_programapplication')
        from programs.models import ProgramApplication
        row = ProgramApplication.objects.filter(public_reference=str(reference).strip()[:40]).first()
    else:
        raise Http404('This service is unavailable.')
    if row is None:
        raise Http404('The record is unavailable.')
    state = row.state if category == 'association' else row.status
    return {'category': category, 'state': state,
            'label': row.get_state_display() if category == 'association' else
                     ('Evaluation processed' if state == 'RANKED' else row.get_status_display())}
