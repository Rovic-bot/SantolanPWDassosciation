"""Public event descriptions are separate from member application eligibility."""
from django.core.exceptions import ValidationError


EVENT_CATEGORIES = [('general', 'General Events'), ('specific', 'Specific Events')]
PARTICIPATION_FIELDS = ('event_category', 'target_audience', 'who_may_participate')
TARGET_HELP = 'Describe the group or community the event focuses on. This does not determine who may join.'
PARTICIPATION_HELP = ('State the organizer\'s participation rules. General events are open to everyone, subject '
    'to those rules. For Specific events, say whether other community members may also participate.')


def require_participation_details(item, *, scheduled=False):
    if scheduled:
        # Scheduled events use the general-event editor. Historical category
        # values are retained, but are no longer a publication prerequisite.
        return
    errors = {}
    # Annual observance authoring collects the focus audience. Participation
    # rules may be retained, but are not inferred from that audience or required
    # by the compact editor. Related activities have their own joining rules.
    for name, label in [('target_audience', 'Target Audience')]:
        if not getattr(item, name).strip():
            errors[name] = f'Complete {label} before publishing.'
    if errors:
        raise ValidationError(errors)


def guard_participation(old, proposed):
    """Preserve protected program terms without rewriting historical term digests."""
    from programs.terms import protected_programs, FROZEN
    ids = {value for value in (old.application_program_id if old else None, proposed.application_program_id) if value}
    if ids and (old is None or any(getattr(old, name) != getattr(proposed, name) for name in PARTICIPATION_FIELDS)):
        if protected_programs().filter(pk__in=ids).exists():
            raise ValidationError(FROZEN)
