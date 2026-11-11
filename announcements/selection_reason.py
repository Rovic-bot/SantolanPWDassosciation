"""Versioned public explanation, bound to the exact reviewed result source."""
from django.core.exceptions import ValidationError

from ewaf.evidence import digest

MAX_LENGTH = 2000
VERSION = 1


def clean_selection_reason(value):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError('Explain why these members were selected before publishing the results.')
    value = value.strip()
    if len(value) > MAX_LENGTH:
        raise ValidationError('Keep the selection reason to 2,000 characters or fewer.')
    return value


def with_selection_reason(payload, source_digest, reason):
    reason = clean_selection_reason(reason)
    return ({**payload, 'selection_reason': reason, 'selection_reason_version': VERSION},
        digest({'result_source': source_digest, 'selection_reason': reason,
                'selection_reason_version': VERSION}))


def retained_selection_reason(payload, source_digest, retained):
    # Historical authorized revisions predate this field and keep their original
    # digest rules. No reason is invented or backfilled for those publications.
    if 'selection_reason' not in retained and 'selection_reason_version' not in retained:
        return payload, source_digest
    version = retained.get('selection_reason_version')
    if type(version) is not int or version != VERSION:
        raise ValidationError('This selection explanation version is not supported.')
    return with_selection_reason(payload, source_digest, retained.get('selection_reason'))
