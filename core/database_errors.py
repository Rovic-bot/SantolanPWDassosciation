"""Identify duplicate keys without hiding unrelated database integrity failures."""
from django.db import IntegrityError


def is_unique_violation(error):
    if not isinstance(error, IntegrityError):
        return False
    cause = error.__cause__
    return bool(
        (error.args and error.args[0] == 1062)
        or getattr(cause, 'sqlstate', None) == '23505'
        or getattr(cause, 'pgcode', None) == '23505'
    )
