"""Full-name presentation for permission-checked Admin pages only."""
from collections import defaultdict
from copy import deepcopy

from django.core.exceptions import ValidationError

from core.permissions import require_workspace_permissions
from .participation import applicants
from .results import RESULT_PERMISSIONS, mask_identity


def admin_projection(program, payload, *, user):
    require_workspace_permissions(user, *RESULT_PERMISSIONS)
    result = deepcopy(payload)
    source = applicants(program)
    by_reference = {row['public_reference']: row for row in source}
    legacy = defaultdict(list)
    for row in source:
        try:
            masked = mask_identity(row['member__full_name'], row['public_reference'])
        except ValidationError:
            continue
        legacy[(masked['name'], masked['reference'])].append(row)
    for key in ('applicants', 'rows'):
        for row in result.get(key, []):
            match = by_reference.get(row['reference'])
            if match is None:
                matches = legacy.get((row['name'], row['reference']), [])
                match = matches[0] if len(matches) == 1 else None
            row['name'] = match['member__full_name'] if match else 'Name unavailable in this historical snapshot'
        if key in result:
            result[key].sort(key=lambda row: (row['name'].casefold(), row['reference']))
    result['private_names'] = True
    return result


def review_pool(program, roster):
    """Presentation only, after the view has authorized the private roster."""
    selected_references = {row['reference'] for row in roster.get('rows', [])}
    submitted = dict(program.applications.values_list('public_reference', 'submitted_at'))
    applicants = [
        {**row, 'selected': row['reference'] in selected_references,
         'submitted_at': submitted.get(row['reference'])}
        for row in roster.get('applicants', [])
    ]
    count = len(selected_references)
    return {
        'applicants': applicants, 'selected': roster.get('rows', []),
        'applicant_count': len(applicants), 'selected_count': count,
        'available_slots': max(program.slot_limit - count, 0) if program.slot_limit is not None else None,
        'over_capacity': program.slot_limit is not None and count > program.slot_limit,
    }
