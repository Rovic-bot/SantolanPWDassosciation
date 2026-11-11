"""New versioned foundation records; historical evidence digests are unchanged.

Supported ORM guards are not protection against privileged SQL/Python tampering.
Only the isolated foundation transaction may insert history or CAS mutable rows.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone as datetime_timezone
import re

from django.core.exceptions import ValidationError
from django.db import connection, models
from django.utils import timezone

from .evidence import canonical, digest
from .evidence_records import EvidenceQuerySet

MAX_GENERATION = 9223372036854775807
DIGEST_VERSION = 'g18-generation-record-1'
PROTOCOL = 'g18-generation-development-1'
COVERAGE = 'g18-2b-foundation-nonpromotable-1'
ENGINE_PROFILE = 'durable-pool-development-2:historical-five-1'
SYSTEM_CODES = ('DISPOSABLE_BOOTSTRAP', 'DEVELOPMENT_EXPIRY', 'DEVELOPMENT_REPLACEMENT',
                'VERIFIED_MEMBER_SUBMISSION')
_owner = ContextVar('generation_transaction_owner', default=None)


def canonical_payload(value):
    """New contract only: aware timestamps use UTC before canonical hashing."""
    if isinstance(value, datetime):
        if timezone.is_naive(value):
            raise ValidationError('AWARE_GENERATION_TIME_REQUIRED')
        value = value.astimezone(datetime_timezone.utc)
    elif isinstance(value, dict):
        value = {key: canonical_payload(item) for key, item in value.items()}
    elif isinstance(value, (tuple, list)):
        value = [canonical_payload(item) for item in value]
    return canonical(value)


def require_owner():
    from scripts.durable_test_runner import require_disposable
    require_disposable()
    if (not connection.in_atomic_block or _owner.get() !=
            (connection.connection, id(connection.atomic_blocks[0]))):
        raise ValidationError('GENERATION_TRANSACTION_REQUIRED')


@contextmanager
def _owned_transaction():
    if not connection.in_atomic_block:
        raise ValidationError('GENERATION_TRANSACTION_REQUIRED')
    token = _owner.set((connection.connection, id(connection.atomic_blocks[0])))
    try:
        require_owner()
        yield
    finally:
        _owner.reset(token)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}', value):
        raise ValidationError('GENERATION_IDENTIFIER_INVALID')


def bounded(value, *, positive=False):
    if type(value) is not int or not (int(positive) <= value <= MAX_GENERATION):
        raise ValidationError('GENERATION_BOUND_INVALID')
    return value


class StateQuerySet(EvidenceQuerySet):
    def update(self, **kwargs):
        require_owner()
        return models.QuerySet.update(self, **kwargs)


class GenerationState(models.Model):
    objects = StateQuerySet.as_manager()

    class Meta:
        abstract = True
        base_manager_name = 'objects'
        default_permissions = ()

    def save(self, *args, **kwargs):
        require_owner()
        if not self._state.adding:
            raise ValidationError('USE_GENERATION_CAS')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('GENERATION_STATE_PROTECTED')


class GenerationRecord(models.Model):
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)
    digest = models.CharField(max_length=64, editable=False)
    objects = EvidenceQuerySet.as_manager()

    class Meta:
        abstract = True
        base_manager_name = 'objects'
        default_permissions = ()

    def payload(self):
        # Generated audit PKs are excluded; FK/O2O PKs remain part of the payload.
        return canonical_payload({'version': DIGEST_VERSION, 'model': self._meta.label_lower,
            'fields': {f.attname: getattr(self, f.attname) for f in self._meta.fields
                       if f.name not in ('id', 'digest')}})

    def clean(self):
        if not re.fullmatch('[0-9a-f]{64}', self.digest or '') or digest(self.payload()) != self.digest:
            raise ValidationError('GENERATION_DIGEST_MISMATCH')
        for field in self._meta.fields:
            value = getattr(self, field.attname)
            if isinstance(field, models.DateTimeField) and (value is None or timezone.is_naive(value)):
                raise ValidationError('AWARE_GENERATION_TIME_REQUIRED')
            if isinstance(field, models.PositiveBigIntegerField):
                bounded(value)
            if field.name.endswith('digest') and not re.fullmatch('[0-9a-f]{64}', value or ''):
                raise ValidationError('GENERATION_DIGEST_FORMAT_INVALID')
        if hasattr(self, 'reason_code'):
            identifier(self.reason_code)
            if not self.reason.strip() or len(self.reason) > 2000:
                raise ValidationError('GENERATION_REASON_REQUIRED')
            if not self.actor_label.strip():
                raise ValidationError('GENERATION_ACTOR_LABEL_REQUIRED')
        if hasattr(self, 'system_code'):
            if bool(self.actor_id) == bool(self.system_code):
                raise ValidationError('GENERATION_ACTOR_XOR_SYSTEM')
            if self.system_code and self.system_code not in SYSTEM_CODES:
                raise ValidationError('UNSUPPORTED_GENERATION_SYSTEM')
        from .generation_services import _validate_record
        _validate_record(self)

    def save(self, *args, **kwargs):
        require_owner()
        if not self._state.adding:
            raise ValidationError('GENERATION_HISTORY_IMMUTABLE')
        self.full_clean()
        kwargs['force_insert'] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('GENERATION_HISTORY_IMMUTABLE')
