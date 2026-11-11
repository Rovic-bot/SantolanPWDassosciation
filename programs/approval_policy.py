"""Authorization projection for public queries; locked writes also verify terms."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import F, Q
from django.utils import timezone


def binding_condition(*, at=None):
    at = timezone.now() if at is None else at
    path = 'approval_control__active_binding__'
    return Q(**{
        path + 'program_id': F('pk'),
        path + 'revision_id': F('approval_control__current_revision_id'),
        path + 'revision__program_id': F('pk'),
        path + 'revision__digest': F('approval_control__current_digest'),
        path + 'revision__schema_version': 1,
        path + 'approval_record__program_id': F('pk'),
        path + 'approval_record__manual_confirmation': True,
        path + 'confirmed': True,
    }) & (Q(**{path + 'approval_record__kind': 'official'}) |
          Q(**{path + 'approval_record__kind': 'legacy', path + 'revision__number': 1, 'published_at__lte': at}))


def require_binding(program, *, first_publication=False):
    if not settings.PDAO_ENFORCEMENT_ENABLED:
        return
    from .models import Program
    from .terms import snapshot_terms, terms_digest
    records = Program.objects.filter(pk=program.pk).filter(binding_condition())
    if first_publication:
        records = records.filter(approval_control__active_binding__approval_record__kind='official')
    control = getattr(program, 'approval_control', None)
    if not records.exists() or not control or terms_digest(snapshot_terms(program)) != control.current_digest:
        raise ValidationError('The program requires an explicitly reconciled approval covering its current terms.')


def grant_authorization(program):
    if not settings.PDAO_ENFORCEMENT_ENABLED:
        return {}
    control = program.approval_control
    return {'approval_control_version': control.version, 'approval_binding': control.active_binding_id}


def grant_matches(grant, program):
    if not settings.PDAO_ENFORCEMENT_ENABLED:
        return True
    control = getattr(program, 'approval_control', None)
    return bool(control and control.active_binding_id and
                grant.get('approval_control_version') == control.version and
                grant.get('approval_binding') == control.active_binding_id)
