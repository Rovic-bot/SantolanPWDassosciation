"""Canonical terms and guards. These contain no applicant records or budgets."""
import hashlib
import json
from contextlib import contextmanager
from datetime import datetime, timezone as datetime_timezone
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet

PROGRAM_FIELDS = ('name', 'description', 'assistance_type', 'registration_opens_at',
    'registration_closes_at', 'starts_at', 'ends_at', 'slots', 'amount', 'benefit',
    'requirements', 'ewaf_applicable', 'selection_method', 'photo_instructions', 'resubmission_closes_at')
EVENT_FIELDS = ('title', 'description', 'location', 'starts_at', 'ends_at',
                'registration_opens_at', 'registration_closes_at', 'capacity')
REQUIREMENT_FIELDS = ('id', 'label', 'kind', 'instructions', 'is_required', 'is_active', 'position')
FROZEN = 'Approved or previously published program terms are protected. Major revisions require the future reapproval workflow.'
SCHEMA_VERSION = 1


@contextmanager
def terms_lock():
    # One small installation-wide mutex, always acquired before program/event/
    # classification rows. Also serializes first binding and unlinked event edits.
    from .models import ProgramTermsLock
    with transaction.atomic():
        ProgramTermsLock.objects.get_or_create(pk=1)
        ProgramTermsLock.objects.select_for_update().get(pk=1)
        yield


def protected_programs():
    from .models import Program
    return Program.objects.filter(Q(published_at__isnull=False) | Q(status__in=['published', 'cancelled']) |
                                  Q(pdao_approval_records__isnull=False) | Q(approval_bindings__isnull=False))


def is_protected(program):
    return bool(program.pk and not program._state.adding and protected_programs().filter(pk=program.pk).exists())


def guard_program_form(form, *, validate_schedule=False):
    from .application_workflow import enabled
    protected = is_protected(form.instance) or (enabled() and form.instance.policy_authorized_at)
    changed = set(form.changed_data) & (set(PROGRAM_FIELDS) | {'eligible_disability_types'})
    if changed and protected:
        if validate_schedule:
            from .schedule_services import EDITABLE_FIELDS, validate_schedule as check_schedule
            if changed <= EDITABLE_FIELDS:
                from .models import Program
                check_schedule(Program.objects.get(pk=form.instance.pk), form.cleaned_data)
                return
        raise ValidationError(FROZEN)


def guard_requirement_form(form):
    if (form.instance._state.adding or set(form.changed_data) & set(form.Meta.fields)):
        program_id = form.instance.program_id
        from .application_workflow import enabled
        from .models import Program
        if program_id and (protected_programs().filter(pk=program_id).exists() or
                enabled() and Program.objects.filter(pk=program_id, policy_authorized_at__isnull=False).exists()):
            raise ValidationError(FROZEN)


def guard_reference(instance):
    # Django can UPDATE an existing primary key even on an instance constructed
    # with _state.adding=True. Do not let that bypass reference protection.
    if instance.pk is None:
        return
    from .models import ProgramRequirement
    if instance._meta.label_lower == 'members.disabilitytype':
        fields = ('name', 'is_active')
        used = protected_programs().filter(eligible_disability_types=instance)
    else:
        fields = ('name', 'description')
        used = protected_programs().filter(pk__in=ProgramRequirement.objects.filter(
            reusable_document_type=instance).values('program_id'))
    old = type(instance).objects.filter(pk=instance.pk).values(*fields).first()
    if old and any(old[name] != getattr(instance, name) for name in fields) and used.exists():
        raise ValidationError(FROZEN)


class ProtectedReferenceQuerySet(QuerySet):
    def _guard(self):
        from .models import ProgramRequirement
        if self.model._meta.label_lower == 'members.disabilitytype':
            used = protected_programs().filter(eligible_disability_types__in=self.values('pk'))
        else:
            used = protected_programs().filter(pk__in=ProgramRequirement.objects.filter(
                reusable_document_type__in=self.values('pk')).values('program_id'))
        if used.exists():
            raise ValidationError(FROZEN)

    def update(self, **kwargs):
        from ewaf.reference_invalidation import require_reference_writer
        require_reference_writer()
        with terms_lock():
            self._guard()
            return super().update(**kwargs)

    def delete(self):
        from ewaf.reference_invalidation import require_reference_writer
        require_reference_writer()
        with terms_lock():
            self._guard()
            return super().delete()

    def bulk_update(self, objs, fields, **kwargs):
        from ewaf.reference_invalidation import require_reference_writer
        require_reference_writer()
        with terms_lock():
            self.filter(pk__in=[obj.pk for obj in objs])._guard()
            return super().bulk_update(objs, fields, **kwargs)

    def bulk_create(self, objs, **kwargs):
        from ewaf.reference_invalidation import require_reference_writer
        require_reference_writer()
        if kwargs.get('update_conflicts'):
            raise ValidationError('Reference replacement through bulk upsert is not supported.')
        return super().bulk_create(objs, **kwargs)


def guard_event(old, proposed):
    ids = {value for value in (old.application_program_id if old else None, proposed.application_program_id) if value}
    if not ids or not protected_programs().filter(pk__in=ids).exists():
        return
    if (old is None or old.application_program_id != proposed.application_program_id or
            any(getattr(old, field) != getattr(proposed, field) for field in EVENT_FIELDS)):
        raise ValidationError(FROZEN)


def canonical_value(value):
    if isinstance(value, datetime):
        return value.astimezone(datetime_timezone.utc).isoformat(timespec='microseconds')
    if isinstance(value, Decimal):
        return format(value, '.2f')
    return value


def snapshot_terms(program):
    from events.models import Event
    requirements = []
    for requirement in program.configured_requirements.select_related('reusable_document_type').order_by('position', 'pk'):
        item = {field: getattr(requirement, field) for field in REQUIREMENT_FIELDS}
        ref = requirement.reusable_document_type
        item['document_type'] = {'id': ref.pk, 'name': ref.name, 'description': ref.description} if ref else None
        requirements.append(item)
    event = Event.objects.filter(application_program=program).first()
    return {'schema': SCHEMA_VERSION, 'program_id': str(program.pk),
        'program': {field: canonical_value(getattr(program, field)) for field in PROGRAM_FIELDS},
        'requirements': requirements,
        'disability_qualifications': list(program.eligible_disability_types.order_by('pk').values('id', 'name', 'is_active')),
        'event': {'id': str(event.pk), **{field: canonical_value(getattr(event, field)) for field in EVENT_FIELDS}} if event else None}


def terms_digest(snapshot):
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()
