"""Shared publication recency for public and administrative program browsing."""
from datetime import timedelta

from django.db.models import Q


NEW_PROGRAM_WINDOW = timedelta(hours=1)


def newly_published_condition(at):
    return Q(status='published', published_at__gt=at - NEW_PROGRAM_WINDOW,
             published_at__lte=at)
