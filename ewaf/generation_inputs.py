"""Ordered source locks and finite expiry for disposable five-criterion capture."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.utils import timezone


def lock_sources(program, *, maximum=None):
    from assistance.models import EligibilityStatus, AssistanceCase, AssistanceRelease
    from documents.models import DocumentType, MembershipDocumentRequirement, MembershipApplicationDocument, DocumentVerification
    from events.models import Event
    from members.models import Member, DisabilityType
    from membership.models import MembershipSettings, MembershipApplication
    from programs.models import (ProgramApplication, ProgramApprovalControl, ProgramRequirement,
        ProgramDocument, ApplicationPhoto, PhotoVerification)
    from .models import ConfigurationRevision, ConfigurationValidation, CriterionAssessment
    from .pool_contracts import MAX_APPLICATIONS

    list(Event.objects.select_for_update().filter(application_program=program).order_by('pk'))
    if ProgramApplication.objects.filter(program=program).count() > (MAX_APPLICATIONS if maximum is None else maximum):
        raise ValidationError('WHOLE_POOL_UNSUPPORTED')
    applications = list(ProgramApplication.objects.select_for_update().filter(program=program).order_by('pk'))
    member_ids = sorted({row.member_id for row in applications})
    members = {pk: Member.objects.select_for_update().get(pk=pk) for pk in member_ids}
    intakes = [row.application_id for row in members.values()]
    list(MembershipSettings.objects.select_for_update().order_by('pk'))
    list(MembershipApplication.objects.select_for_update().filter(pk__in=intakes).order_by('pk'))
    list(EligibilityStatus.objects.select_for_update().order_by('pk'))
    list(ProgramApprovalControl.objects.select_for_update().filter(program=program).order_by('pk'))
    list(DocumentType.objects.select_for_update().order_by('pk'))
    list(MembershipDocumentRequirement.objects.select_for_update().order_by('pk'))
    list(DisabilityType.objects.select_for_update().order_by('pk'))
    list(ProgramRequirement.objects.select_for_update().filter(program=program).order_by('pk'))
    list(ConfigurationRevision.objects.select_for_update().filter(program=program).order_by('pk'))
    list(ConfigurationValidation.objects.select_for_update().filter(program=program).order_by('pk'))
    list(CriterionAssessment.objects.select_for_update().filter(program=program).order_by('pk'))
    documents = list(MembershipApplicationDocument.objects.select_for_update().filter(application_id__in=intakes).order_by('pk'))
    list(DocumentVerification.objects.select_for_update().filter(document_id__in=[row.pk for row in documents]).order_by('pk'))
    ids = [row.pk for row in applications]
    list(ProgramDocument.objects.select_for_update().filter(application_id__in=ids).order_by('pk'))
    photos = list(ApplicationPhoto.objects.select_for_update().filter(application_id__in=ids).order_by('pk'))
    list(PhotoVerification.objects.select_for_update().filter(photo_id__in=[row.pk for row in photos]).order_by('pk'))
    list(AssistanceCase.objects.select_for_update().filter(application_id__in=ids).order_by('pk'))
    release_ids = list(AssistanceRelease.objects.filter(application__member_id__in=member_ids).values_list('pk', flat=True))
    list(AssistanceRelease.objects.select_for_update().filter(pk__in=release_ids).order_by('pk'))
    for row in applications:
        row.program, row.member = program, members[row.member_id]
    return applications


def deadline(program, snapshot, now):
    """Day-based evidence expires no later than the next evaluation midnight.

All existing evidence expiry/freshness contracts use inclusive calendar dates.
Earlier event/program timestamp boundaries conservatively shorten this ceiling.
No lifetime is promised between a last clock check and transaction commit.
"""
    from events.models import Event
    zone = ZoneInfo(snapshot['timezone'])
    local = now.astimezone(zone)
    if snapshot['evaluation_date'] != str(local.date()):
        raise ValidationError('EVALUATION_DAY_CHANGED')
    candidates = [datetime.combine(local.date() + timedelta(days=1), time.min, zone)]
    for source in [program, *Event.objects.filter(application_program=program).order_by('pk')]:
        for field in ('published_at', 'registration_opens_at', 'registration_closes_at', 'starts_at', 'ends_at', 'resubmission_closes_at'):
            value = getattr(source, field, None)
            if value is not None:
                if timezone.is_naive(value):
                    raise ValidationError('SOURCE_BOUNDARY_TIMEZONE_REQUIRED')
                if value > now:
                    candidates.append(value)
    return min(candidates)
