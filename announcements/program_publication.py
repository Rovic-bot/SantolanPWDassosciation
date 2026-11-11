"""Preserve legacy records while retiring automatic applicant publication."""
from django.core.exceptions import ValidationError


def process_closed_program(pk, *, user=None, address=None):
    raise ValidationError('Application closure does not authorize publication. Program results require the separately authorized final-results workflow.')


def refresh_existing_results(program, *, user=None, address=None):
    # Decisions never silently rewrite an earlier publication snapshot.
    # results.py requires a newly reviewed revision and explicit publication.
    # Public reads withhold stale projections without rewriting retained history.
    return None
