"""Install the owner-approved recurring calendar once, preserving later edits."""
from dataclasses import asdict
from uuid import NAMESPACE_URL, uuid5

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import AnnualObservance
from .observances import REFERENCE_CATALOGUE
from .services import _observance_actor, check_notes, save_observance, change_observance_publication


def calendar_id(month):
    return uuid5(NAMESPACE_URL, f'santolan-pwd-system/annual-calendar/{month}')


@transaction.atomic
def publish_annual_calendar(*, user, notes):
    actor = _observance_actor(user, 'events.add_annualobservance', 'events.publish_annualobservance')
    check_notes(notes)
    # Serialize repeated installations by the same administrator. Stable primary
    # keys also prevent duplicate cards if different administrators race.
    get_user_model().objects.select_for_update().get(pk=actor.pk)
    created, retained = [], []
    for reference in REFERENCE_CATALOGUE:
        identifier = calendar_id(reference.month)
        existing = AnnualObservance.objects.filter(pk=identifier).first()
        if existing:
            # Never republish withdrawn/archived cards or replace edited content.
            retained.append(existing)
            continue
        if AnnualObservance.objects.filter(month=reference.month, title=reference.title).exists():
            raise ValidationError(f'An existing card matches {reference.title}. Review it before installing the calendar.')
        data = {**asdict(reference), 'version': 0, 'notes': notes,
            'target_audience': 'Association members and community readers interested in this observance.',
            'who_may_participate': 'This calendar entry announces an annual observance. Check separately published activities for participation requirements.',
            'image_alt': ''}
        item = save_observance(user=actor, data=data, creation_id=identifier)
        item = change_observance_publication(item.pk, user=actor, version=item.version,
            action='published', notes=notes)
        created.append(item)
    return created, retained
