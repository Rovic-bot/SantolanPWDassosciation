"""Small public previews; programs and authorized results remain authoritative."""
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator


def announcement_programs():
    from programs.models import Program
    now = timezone.now()
    return Program.objects.public(at=now).filter(status='published', registration_closes_at__gt=now)


def announced_public_programs():
    # Published notices remain useful after applications close and results arrive.
    from programs.models import Program
    return Program.objects.public().filter(status='published')


def public_schedule(program):
    """Public schedule fields only; do not alter the issued result snapshot."""
    return {field: getattr(program, field) for field in (
        'starts_at', 'ends_at', 'registration_opens_at', 'registration_closes_at')}


def public_notice(item):
    """Call only after the publication gate, or for a permission-checked staff preview."""
    notice = dict(pk=item.pk, title=item.title, content=item.content,
        published_at=item.published_at, category=item.category, category_label=item.category_label,
        source_office=item.source_office or 'Source not recorded',
        image=bool(item.image) and item.category == 'general',
        image_url=reverse('announcements:image', args=[item.pk]) if item.image and item.category == 'general' else '',
        image_alt=item.image_alt if item.category == 'general' else '', destination='', destination_label='')
    if item.linked_program_id:
        notice.update(title=item.linked_program.name,
            content=Truncator(item.linked_program.description).chars(400),
            program_category=item.linked_program.assistance_type,
            destination=reverse('programs:detail', args=[item.linked_program_id]),
            destination_label='View program and application information')
    elif item.program_id:
        # Never pass rows, references, member identities, or private revision metadata to notice templates.
        payload = item.result_revision.public_payload if item.result_revision_id else {}
        notice.update(content=Truncator(payload.get('description', '')).chars(400),
            source_office='Barangay Santolan PWD Association',
            destination=reverse('core:result_detail', args=[item.pk]),
            destination_label='View official program result')
    program = item.linked_program if item.linked_program_id else item.program if item.program_id else None
    if program:
        notice['schedule'] = public_schedule(program)
    if program and getattr(getattr(program, 'picture_asset', None), 'image', None):
        # Use the public presentation artwork route, never an application photo
        # or an unrestricted storage URL. That route rechecks publication.
        notice.update(image_url=reverse('programs:public_picture', args=[program.pk]),
            image_alt=f'Program image for {program.name}')
    return notice
