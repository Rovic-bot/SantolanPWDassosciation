"""Code-owned scoring; database records retain weights and audited snapshots only.

The owner adopted the previous calculation rules as permanent on November 10.
No shared-policy row, fixture, fake approval or seed data is needed. Retain this
version/file unchanged for replay; a future rule change requires a new version.
"""
import json
from copy import deepcopy
from datetime import timezone as utc_timezone
from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils import timezone

from .evidence import digest

VERSION = 'santolan-fixed-scoring-2026-11-10-v1'


def is_fixed(configuration):
    return bool(configuration and configuration.policy.get('fixed_scoring_version'))


def definition():
    from .revised.composite_ses import FORMULA
    from .revised.contracts import NAMES
    from . import dataset_methods as methods
    result = json.loads(Path(__file__).with_name('fixed_scoring_rules_v1.json').read_text(encoding='utf-8'))
    result['ses_formula'] = deepcopy(FORMULA)
    result['criteria'] = {code: {'measure': NAMES[code], 'direction': direction}
        for code, direction in zip(methods.criteria(result['method']), methods.directions(result['method']))}
    result['shared_policy_digest'] = digest(result)
    return result


def validate(configuration):
    """Validate a retained snapshot against its immutable code-owned version."""
    from .revised.contracts import weight_snapshot
    from .dataset_methods import COMPOSITE
    if (configuration.policy != definition() or configuration.status != 'LOCKED'
            or configuration.dataset_policy_id or configuration.evidence_policy_id
            or not configuration.vault_revision_id or configuration.judgments != {}):
        raise ValidationError('The fixed scoring version or its retained snapshot is invalid.')
    weights = weight_snapshot(configuration.vault_revision, COMPOSITE)
    if configuration.validation != {'weights': weights['weights'], 'weight_version': weights['id'],
            'weight_digest': weights['digest'], 'method': 'retained_locked_vector'}:
        raise ValidationError('Retain the exact approved weights used to bind fixed scoring.')
    if not configuration.assessment_cutoff or timezone.is_naive(configuration.assessment_cutoff):
        raise ValidationError('The fixed scoring snapshot needs the program assessment cutoff.')
    if (configuration.previous_id and (configuration.previous.program_id != configuration.program_id
            or configuration.revision != configuration.previous.revision + 1)
            or not configuration.previous_id and configuration.revision != 1):
        raise ValidationError('The fixed scoring predecessor is invalid.')


def require_binding(configuration):
    from .revised.live_services import dataset_source
    validate(configuration)
    if configuration.source != dataset_source(configuration.program):
        raise ValidationError('Program terms changed after scoring setup. Review the program configuration.')
    if configuration.assessment_cutoff != configuration.program.registration_closes_at:
        raise ValidationError('The assessment cutoff must match the approved registration closing time.')


def bind(program, *, user, rebind=False, reason=None):
    """Called within an authorized publication/weight-approval transaction.

    Existing scored/legacy bindings remain intact. Only an unbound composite
    intake receives the code rules. No ranking or member decision is generated.
    """
    from .operational_models import OperationalConfiguration as Configuration, OperationalRun
    from .revised.live_services import dataset_source
    from .revised.contracts import weight_snapshot
    from .vault_services import active
    from .dataset_methods import COMPOSITE, is_composite
    from .evidence_services import persist, reasoned
    from programs.approval_policy import require_binding as require_terms
    from core.permissions import require_workspace_permissions
    from programs.terms import terms_lock
    with terms_lock():
        require_workspace_permissions(user, 'programs.view_program', 'programs.publish_program')
        program = type(program).objects.select_for_update().get(pk=program.pk)
        if not program.ewaf_applicable or not program.policy_authorized_by_id:
            return None
        previous = Configuration.objects.filter(program=program).first()
        if is_fixed(previous):
            previous.clean()
            if not rebind:
                require_binding(previous)
                return previous
        if previous and not is_fixed(previous) and (previous.dataset_policy_id or not is_composite(previous.policy)
                or previous.policy.get('configuration_scope') != 'weights_and_sources'):
            return None
        if OperationalRun.objects.filter(program=program).exists():
            return None
        revision = previous.vault_revision if is_fixed(previous) else active(COMPOSITE)
        if not revision:
            raise ValidationError('Approve the four-criterion weights in Configuration before publishing.')
        require_terms(program, first_publication=program.published_at is None)
        if not program.registration_closes_at:
            raise ValidationError('Set the registration closing time before applying fixed scoring.')
        weights = weight_snapshot(revision, COMPOSITE)
        row = Configuration(program=program, previous=previous,
            revision=previous.revision + 1 if previous else 1,
            status='LOCKED', vault_revision=revision, policy=definition(), judgments={},
            validation={'weights': weights['weights'], 'weight_version': weights['id'],
                        'weight_digest': weights['digest'], 'method': 'retained_locked_vector'},
            assessment_cutoff=program.registration_closes_at.astimezone(utc_timezone.utc),
            source=dataset_source(program),
            **reasoned(user, reason or 'Applied owner-confirmed fixed scoring from application code with approved weights; no applicants ranked or selected.', True))
        validate(row)
        row = persist(row)
        row.clean()
        return row
