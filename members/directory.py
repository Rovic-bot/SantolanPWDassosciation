"""Read-only presentation of the existing, permission-checked member registry."""
from typing import NotRequired, TypedDict

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator

from .forms import MEMBER_STATUSES
from .models import DisabilityType, Member, MemberEvent
from .review_models import InformationReview
from .review_services import available as reviews_available
from .update_models import MemberUpdateRequest


class MemberPreview(TypedDict):
    id: str
    name: str
    initials: str
    control_number: str
    classification: str
    status: str
    status_label: str
    needs_review: bool
    joined: str
    mobile: str
    updated: str
    full_url: str
    edit_url: str
    update_url: str
    verification: NotRequired[str]
    note: NotRequired[str]


def member_preview(member: Member, user) -> MemberPreview:
    if hasattr(member, 'directory_update_id'):
        update_id, update_state = member.directory_update_id, member.directory_update_state
    else:
        update = MemberUpdateRequest.objects.filter(member=member, state__in=MemberUpdateRequest.OPEN_STATES).first()
        update_id, update_state = (update.pk, update.state) if update else (None, '')
    status, status_label = member.status, member.status.title()
    if member.is_active and not member.archived_at and update_id:
        status = 'needs_verification' if update_state == 'needs_verification' else 'update_needed'
        status_label = 'Needs verification' if status == 'needs_verification' else 'Update needed'
    words = member.full_name.split()
    initials = (words[0][0] + words[-1][0] if len(words) > 1 else member.full_name[:2]).upper()
    classifications = [item.name for item in member.disability_types.all()]
    if not classifications and member.disability_type_id:
        classifications = [member.disability_type.name]
    if not classifications and isinstance(member.registration_profile, dict):
        recorded = member.registration_profile.get('disability_type')
        if isinstance(recorded, str) and recorded.strip():
            classifications = [recorded]
    result: MemberPreview = {
        'id': str(member.pk), 'name': member.full_name, 'initials': initials,
        'control_number': member.control_number,
        'classification': ', '.join(classifications) or 'Not recorded',
        'status': status, 'status_label': status_label,
        'update_url': reverse('members:update_review', args=[update_id]) if update_id else '',
        'needs_review': bool(getattr(member, 'directory_review', False)),
        'joined': timezone.localtime(member.joined_at).strftime('%b %d, %Y'),
        'mobile': member.contact_number or 'Not recorded',
        'updated': timezone.localtime(member.updated_at).strftime('%b %d, %Y · %I:%M %p'),
        'full_url': reverse('members:detail', args=[member.pk]),
        'edit_url': (reverse('members:edit', args=[member.pk])
                     if user.has_perm('members.change_member') and not member.archived_at else ''),
    }
    if user.has_perm('membership.view_membershipapplication'):
        verified = member.application.prpwd_verified
        result['verification'] = ('PRPWD: manually verified' if verified is True else
                                  'PRPWD: not verified' if verified is False else 'PRPWD: not recorded')
    if user.has_perm('members.view_memberevent'):
        result['note'] = Truncator(getattr(member, 'directory_note', '') or '').chars(360)
    return result


def directory_context(*, user, query: str, status: str, disability: str = '', page=None) -> dict:
    can_review = user.has_perm('members.view_informationreview') and reviews_available()
    pending_updates = MemberUpdateRequest.objects.filter(member_id=OuterRef('pk'), state__in=MemberUpdateRequest.OPEN_STATES)
    all_records = Member.objects.annotate(directory_update_id=Subquery(pending_updates.values('pk')[:1]),
        directory_update_state=Subquery(pending_updates.values('state')[:1]),
        update_verification_blocked=Exists(pending_updates.filter(state='needs_verification')))
    if can_review:
        pending = InformationReview.objects.filter(state__in=('received', 'under_review', 'needs_information'))
        # Program-linked concerns retain the existing review-view permission gate.
        if not user.has_perms(('programs.view_program', 'programs.view_programapplication')):
            pending = pending.filter(application__isnull=True)
        all_records = all_records.annotate(directory_review=Exists(pending.filter(member_id=OuterRef('pk'))))

    totals = all_records.aggregate(total=Count('pk'),
        active=Count('pk', filter=Q(is_active=True, archived_at__isnull=True, update_verification_blocked=False)),
        new=Count('pk', filter=Q(joined_at__year=timezone.localdate().year)))
    metrics = [
        {'value': f'{totals["total"]:,}', 'label': 'Total members', 'accent': 'cyan',
         'detail': f'{totals["new"]:,} joined this year'},
        {'value': f'{totals["active"]:,}', 'label': 'Active records', 'accent': 'green',
         'detail': f'{totals["active"] / totals["total"]:.1%} of all records' if totals['total'] else 'No member records yet'},
    ]
    records = all_records
    if status == 'archived':
        records = records.filter(archived_at__isnull=False)
    elif status in ('active', 'inactive'):
        records = records.filter(archived_at__isnull=True, is_active=status == 'active')
        if status == 'active':
            records = records.filter(update_verification_blocked=False)
    elif status in ('update_needed', 'needs_verification'):
        records = records.filter(archived_at__isnull=True, is_active=True,
            directory_update_state__in=['needs_verification'] if status == 'needs_verification' else ['submitted', 'invited'])
    elif status == 'review':
        if not can_review:
            raise PermissionDenied('Information reviews are unavailable for this account.')
        records = records.filter(directory_review=True)
    else:
        status = ''
    if query:
        records = records.filter(Q(full_name__icontains=query) | Q(control_number__icontains=query))
    disability_choices = list(DisabilityType.objects.all())
    disability_error = ''
    if disability:
        if disability not in {str(item.pk) for item in disability_choices}:
            records = records.none()
            disability_error = 'Choose a listed disability type.'
        else:
            # Match the structured classifications shown in the directory. The
            # older single field is a fallback only when no multiple types exist.
            records = records.filter(Q(disability_types__pk=disability) |
                Q(disability_types__isnull=True, disability_type_id=disability)).distinct()
    if user.has_perm('members.view_memberevent'):
        latest_note = MemberEvent.objects.filter(member_id=OuterRef('pk')).exclude(notes='').order_by('-occurred_at', '-pk')
        records = records.annotate(directory_note=Subquery(latest_note.values('notes')[:1]))
    records = records.select_related('application', 'disability_type').prefetch_related('disability_types')
    page_obj = Paginator(records, 20).get_page(page)
    previews = [member_preview(member, user) for member in page_obj]
    statuses = list(MEMBER_STATUSES)
    statuses[1:1] = [('update_needed', 'Update needed'), ('needs_verification', 'Needs verification')]
    if can_review:
        statuses.insert(1, ('review', 'Review'))
    return {
        'page_obj': page_obj, 'query': query, 'status': status, 'statuses': statuses,
        'disability': disability, 'disability_choices': disability_choices, 'disability_error': disability_error,
        'directory_members': previews, 'selected_member': previews[0] if previews else None,
        'directory_metrics': metrics,
        'can_register_member': user.has_perms(('membership.view_membershipapplication',
                                              'membership.encode_membershipapplication')),
        'can_view_member_notes': user.has_perm('members.view_memberevent'),
    }
