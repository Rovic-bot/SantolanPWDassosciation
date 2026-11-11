"""Protected, transient fictional human choice; no decision persistence or release."""
from uuid import UUID
from django.core.exceptions import ValidationError
from core.permissions import require_workspace_permissions
from . import generation_processing as processing, generation_services as generation
from .four_policy import POOL_ENGINE
from .evidence import digest


def demonstrate(program_id, *, user, expected, run_id, application_id, decision, reason):
    if (decision not in ('SELECT_FOR_DEMONSTRATION', 'DEFER_FOR_REVIEW', 'WITHDRAW_DEMO') or type(reason) is not str or
            not reason.strip() or len(reason) > 1000 or type(run_id) is not int):
        raise ValidationError('FOUR_HUMAN_REASON_AND_IDENTITY_REQUIRED')
    try:
        if type(application_id) not in (str, UUID):
            raise ValueError
        application_id = UUID(str(application_id))
    except (ValueError, TypeError):
        raise ValidationError('FOUR_APPLICATION_UUID_REQUIRED')
    with processing._fence(program_id, user) as (actor, authority, program, state, applications):
        require_workspace_permissions(actor, 'assistance.decide_assistance')
        generation._expect(state, authority, expected)
        binding = processing._current(actor, authority, program, state, applications, sticky=True)
        if binding.run_id != run_id or binding.run.snapshot['engine'] != POOL_ENGINE:
            raise ValidationError('FOUR_CURRENT_RUN_REQUIRED')
        if not binding.run.results.filter(application_id=application_id).exists():
            raise ValidationError('FOUR_CONFIRMED_ELIGIBLE_RESULT_REQUIRED')
        output = {'version': 'g18-four-transient-human-choice-1', 'run_id': run_id, 'run_digest': binding.run.digest,
            'application_id': str(application_id), 'actor': actor.pk, 'expected': expected, 'reason': reason.strip(),
            'decision': decision, 'eligible': True, 'comparable': True, 'business_rank': None,
            'selected_in_demonstration': decision == 'SELECT_FOR_DEMONSTRATION', 'actually_assisted': False,
            'retention': 'NOT_PERSISTED_SCHEMA_PENDING', 'operational_ready': False}
        output['digest'] = digest(output)
        processing._current(actor, authority, program, state, applications, sticky=True)
        require_workspace_permissions(processing.durable._authorize(actor), 'assistance.decide_assistance')
        return output
