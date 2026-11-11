"""Immutable short aliases for existing application references.

The shared database sequence never resets by year or service. Aliases are search
keys, not credentials; callers retain their existing authorization checks.
"""
from contextlib import contextmanager
from contextvars import ContextVar
import re

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction

KINDS = {
    'association': ('AMR', 'membership.RegistrationIntake', 'reference'),
    'membership': ('MEM', 'membership.MembershipApplication', 'reference'),
    'pdao': ('PDAO', 'membership.PDAORegistration', None),
    'program': ('PRG', 'programs.ProgramApplication', 'public_reference'),
    'event': ('EVT', 'events.EventRegistration', 'reference'),
    'attendance': ('ATT', 'events.EventAttendance', 'reference'),
    'referral': ('REF', 'assistance.ReferralTicket', 'reference'),
}
_writing = ContextVar('short_reference_writer', default=False)


@contextmanager
def reference_write():
    token = _writing.set(True)
    try:
        yield
    finally:
        _writing.reset(token)


def enabled():
    return getattr(settings, 'SHORT_REFERENCES_ENABLED', False)


def kind_for(record):
    label = record._meta.label_lower
    return next(kind for kind, (_, model, _) in KINDS.items() if model.lower() == label)


def format_code(kind, number):
    return f'{KINDS[kind][0]}-{number:06d}'


def allocate(record, using='default'):
    from .reference_models import ShortReference
    kind = kind_for(record)
    with reference_write():
        reference, _ = ShortReference.objects.using(using).get_or_create(kind=kind, object_key=str(record.pk))
    record._short_reference_code = format_code(kind, reference.pk)
    return record._short_reference_code


def short_reference(record):
    if not enabled():
        return str(getattr(record, 'public_reference', record.reference))
    if not hasattr(record, '_short_reference_code'):
        from .reference_models import ShortReference
        key = ShortReference.objects.using(record._state.db or 'default').filter(
            kind=kind_for(record), object_key=str(record.pk)).values_list('pk', flat=True).first()
        record._short_reference_code = format_code(kind_for(record), key) if key else ''
    return record._short_reference_code or str(getattr(record, 'public_reference', record.reference))


def parse_code(kind, value):
    if not enabled():
        return None
    # Full codes and their digits alone work in the matching service's inbox.
    value = str(value).strip().upper()
    prefix = KINDS[kind][0]
    match = re.fullmatch(rf'(?:{prefix}[\s-]*)?([0-9]{{1,19}})', value)
    if not match:
        return None
    number = int(match[1])
    return number if 0 < number <= 9223372036854775807 else 0


def lookup_key(kind, value):
    from .reference_models import ShortReference
    number = parse_code(kind, value)
    if number is None:
        return None
    return ShortReference.objects.filter(pk=number, kind=kind).values_list('object_key', flat=True).first() or ''


def original_reference(kind, value):
    """Resolve an alias without changing the original stored reference."""
    key = lookup_key(kind, value)
    if key is None:
        return str(value).strip()
    if not key:
        return ''
    _, label, field = KINDS[kind]
    if field is None:
        return f'PDAO-{key}'
    return str(apps.get_model(label).objects.filter(pk=key).values_list(field, flat=True).first() or '')


def filter_reference(records, kind, value, fallback):
    key = lookup_key(kind, value)
    if key:
        return records.filter(pk=key)
    if key == '' and str(value).strip().upper().startswith(KINDS[kind][0]):
        return records.none()
    return records.filter(fallback)


def display_reference(kind, value):
    """Read-only presentation for receipt contexts containing an original string."""
    if not value or not enabled():
        return str(value or '')
    from .reference_models import ShortReference
    if parse_code(kind, value) is not None:
        number = ShortReference.objects.filter(pk=parse_code(kind, value), kind=kind).values_list('pk', flat=True).first()
        return format_code(kind, number) if number else str(value)
    _, label, field = KINDS[kind]
    model = apps.get_model(label)
    if field is None:
        from uuid import UUID
        try:
            key = UUID(str(value).removeprefix('PDAO-'))
        except ValueError:
            return str(value)
        key = model.objects.filter(pk=key).values_list('pk', flat=True).first()
    else:
        try:
            key = model.objects.filter(**{field: value}).values_list('pk', flat=True).first()
        except (ValidationError, ValueError):
            return str(value)
    number = (ShortReference.objects.filter(kind=kind, object_key=str(key)).values_list('pk', flat=True).first()
              if key is not None else None)
    return format_code(kind, number) if number else str(value)


class ShortReferenceMixin:
    @property
    def short_reference(self):
        return short_reference(self)

    def save(self, *args, **kwargs):
        if not enabled() or not self._state.adding:
            return super().save(*args, **kwargs)
        using = kwargs.get('using') or self._state.db or 'default'
        with transaction.atomic(using=using):
            result = super().save(*args, **kwargs)
            allocate(self, using=using)
            return result
