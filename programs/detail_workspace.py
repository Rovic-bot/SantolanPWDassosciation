"""Read-only presentation of the existing program operations and publication gates."""
from typing import TypedDict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse

from .application_workflow import enabled
from .models import Program
from .portfolio import card_presentation
from .publication_guidance import missing_draft_guidance


class ReadinessCheck(TypedDict):
    label: str
    complete: bool
    detail: str


def ewaf_summary(program, user) -> dict:
    from ewaf.operational_services import VIEW, latest_configuration
    from ewaf.vault_policy import scoring_pending
    from ewaf.dataset_methods import LABELS

    summary = {'accessible': user.has_perms(VIEW), 'configured': False,
               'pending': False, 'model': 'Not assigned', 'revision': '',
               'state': 'Configuration needed', 'ties': 'Not recorded'}
    if not program.ewaf_applicable or not summary['accessible']:
        return summary
    try:
        row = latest_configuration(program, require_locked=False)
    except ValidationError:
        return summary
    summary.update(configured=True, pending=scoring_pending(row.policy),
        model=LABELS.get(row.policy.get('method'), 'Program-specific EWAF'),
        revision=f'Version {row.revision}', state=row.get_status_display(),
        ties=row.policy.get('tie_procedure') or 'See the approved selection method',
        scoring_policy='Built-in fixed scoring' if row.policy.get('fixed_scoring_version') else f'Shared policy revision {row.dataset_policy.revision}' if row.dataset_policy_id else
        'No shared scoring policy bound')
    if row.vault_revision_id:
        summary['source'] = f'Shared vault revision {row.vault_revision.revision}'
    else:
        summary['source'] = 'Program configuration'
    summary['url'] = reverse('ewaf:operational_workspace', args=[program.pk])
    return summary


def detail_context(program: Program, user, *, ewaf_problem: str, pdao_status: str) -> dict:
    workflow = enabled()
    guidance = missing_draft_guidance(program)
    selection_method = guidance.get('selection_method', program.selection_method)
    photo_instructions = guidance.get('photo_instructions', program.photo_instructions)
    authorized = bool(program.policy_authorized_at and program.policy_authorized_by_id)
    authorization_consistent = bool(program.policy_authorized_at) == bool(program.policy_authorized_by_id)
    dates_valid = bool(program.registration_opens_at and program.registration_closes_at
                       and program.registration_opens_at < program.registration_closes_at)
    if program.starts_at and program.ends_at:
        dates_valid = dates_valid and program.starts_at < program.ends_at
    if program.ends_at:
        dates_valid = dates_valid and program.registration_closes_at <= program.ends_at
    checks: list[ReadinessCheck] = [
        {'label': 'Program details', 'complete': bool(program.name.strip() and program.assistance_type.strip()),
            'detail': 'Title and assistance type'},
        {'label': 'Schedule and capacity', 'complete': bool(dates_valid and program.slots),
            'detail': 'Registration dates and beneficiary slots'},
        {'label': 'Selection and evidence', 'complete': bool(not workflow or
            (selection_method.strip() and photo_instructions.strip())),
            'detail': 'Selection method and identity-evidence instructions'},
        {'label': 'Disability eligibility', 'complete': bool(program.eligibility_profile_types),
            'detail': 'At least one applicable disability type'},
        {'label': 'EWAF configuration', 'complete': not bool(ewaf_problem),
            'detail': ewaf_problem or 'Publication configuration available'},
    ]
    if settings.PDAO_ENFORCEMENT_ENABLED:
        checks.append({'label': 'External approval', 'complete': pdao_status == 'Approval recorded',
                       'detail': pdao_status})
    ready = all(item['complete'] for item in checks) and authorization_consistent
    checks.append({'label': 'Program authorization', 'complete': authorized,
                   'detail': 'Recorded with publication' if authorization_consistent else
                   'The recorded authorization needs review'})
    completed = sum(item['complete'] for item in checks)
    incomplete = len(checks) - completed
    readiness_label = 'Complete' if not incomplete else f'{incomplete} check{"s" if incomplete != 1 else ""} remaining'
    title_parts = program.name.rsplit(' ', 1)
    published = program.status == 'published'
    lifecycle = [
        {'label': 'Draft', 'done': True, 'detail': 'Created', 'current': program.status == 'draft'},
        {'label': 'Published', 'done': published, 'detail': 'Public' if published else 'Not published',
         'current': published},
    ]
    return {'detail_capacity': card_presentation(program), 'detail_checks': checks,
            'detail_selection_method': selection_method, 'detail_photo_instructions': photo_instructions,
            'detail_guidance_pending': bool(guidance),
            'detail_completed': completed, 'detail_total': len(checks),
            'detail_progress': round(completed * 100 / len(checks)),
            'detail_readiness_label': readiness_label, 'detail_ready': ready,
            'detail_title_lead': title_parts[0] if len(title_parts) > 1 else '',
            'detail_title_accent': title_parts[-1], 'detail_lifecycle': lifecycle,
            'detail_ewaf': ewaf_summary(program, user)}
