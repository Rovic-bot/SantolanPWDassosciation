"""G18-B supplemental observations, not a durable invalidation generation.

No writers or historical source digest definitions are changed here. Metadata
without a revision/audit contract can still change and return between reads.
"""
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from documents.models import MembershipDocumentRequirement
from events.models import Event
from members.models import MemberEvent
from membership.models import MembershipApplication, MembershipEvent
from programs.models import ProgramLog
from .evidence import canonical, digest

VERSION = 'g18-b-source-observation-1'
ENGINE = 'durable-pool-development-2'


def observe(program, applications, user):
    # Fresh instance: never reuse Django's per-instance permission cache.
    actor = get_user_model().objects.get(pk=user.pk)
    groups = list(actor.groups.order_by('pk').values_list('pk', flat=True))
    user_type = ContentType.objects.get_for_model(actor)
    group_type = ContentType.objects.get(app_label='auth', model='group')
    authority = {
        'actor': actor.pk, 'active': actor.is_active, 'staff': actor.is_staff,
        'superuser': actor.is_superuser, 'effective': sorted(actor.get_all_permissions()),
        'direct': list(actor.user_permissions.order_by('pk').values_list('pk', flat=True)),
        'groups': groups,
        'group_permissions': list(actor.groups.order_by('pk', 'permissions__pk').values_list('pk', 'permissions__pk')),
        'user_admin_events': list(LogEntry.objects.filter(content_type=user_type,
            object_id=str(actor.pk)).order_by('pk').values_list('pk', flat=True)),
        'group_admin_events': list(LogEntry.objects.filter(content_type=group_type,
            object_id__in=[str(pk) for pk in groups]).order_by('pk').values_list('pk', flat=True)),
    }
    # Include all requirement definitions, including additions without documents.
    # This conservatively invalidates every program using membership evidence.
    requirements = list(MembershipDocumentRequirement.objects.order_by('pk').values(
        'pk', 'document_type_id', 'is_active', 'is_required', 'instructions', 'position',
        'document_type__name', 'document_type__description'))
    members = sorted({app.member_id for app in applications})
    intakes = sorted({app.member.application_id for app in applications})
    return canonical({
        'version': VERSION, 'authority_digest': digest(authority),
        'membership_requirements_digest': digest(requirements),
        'intake_digest': digest(list(MembershipApplication.objects.filter(pk__in=intakes)
            .order_by('pk').values('pk', 'version', 'requirements_snapshot'))),
        'membership_events': list(MembershipEvent.objects.filter(application_id__in=intakes)
            .order_by('pk').values_list('pk', flat=True)),
        'linked_event_digest': digest(list(Event.objects.filter(application_program=program)
            .order_by('pk').values('pk', 'version', 'status', 'published_at'))),
        'member_events': list(MemberEvent.objects.filter(member_id__in=members)
            .order_by('pk').values_list('pk', flat=True)),
        # Exclude our own historical persistence: observing a result must not
        # invalidate itself. Retain source audit identities for supported ABA.
        'program_events': list(ProgramLog.objects.filter(program=program)
            .exclude(action__startswith='durable_').order_by('pk').values_list('pk', flat=True)),
        'inventory': [str(app.pk) for app in applications],
    })
