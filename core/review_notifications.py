"""Read-only, permission-scoped counts of submissions awaiting staff review."""
from django.db.models import Count, Q

from membership.models import MembershipApplication
from membership.pdao_models import PDAORegistration
from membership.registration_models import RegistrationIntake
from membership.registration_policy import available
from programs.models import ProgramApplication


PROGRAM_REVIEW_STATES = (
    ProgramApplication.Status.PENDING_PHOTO_VERIFICATION,
    ProgramApplication.Status.PHOTO_VERIFIED,
    ProgramApplication.Status.ELIGIBILITY_REVIEW,
)


def can_count_programs(user):
    return (user.is_authenticated and user.is_active and user.is_staff
            and user.has_perms(('accounts.access_dashboard', 'programs.view_program',
                                'programs.view_programapplication')))


def program_review_counts(user, program_ids):
    """One grouped query for the visible cards, independent of their sort/filter."""
    if not program_ids or not can_count_programs(user):
        return {}
    return dict(ProgramApplication.objects.filter(program_id__in=program_ids,
        status__in=PROGRAM_REVIEW_STATES).order_by().values('program_id')
        .annotate(total=Count('pk')).values_list('program_id', 'total'))


def review_counts(request):
    """Cache only within this request; never share counts between staff accounts."""
    if hasattr(request, '_review_counts'):
        return request._review_counts
    user = request.user
    counts = dict(association=0, pdao=0, membership=0, programs=0)
    if user.is_authenticated and user.is_active and user.is_staff and user.has_perm('accounts.access_dashboard'):
        if user.has_perms(('membership.view_membershipapplication',
                           'membership.view_registrationintake')) and available('staff'):
            counts['association'] = RegistrationIntake.objects.filter(channel='online').exclude(
                membership_application__status__in=(MembershipApplication.Status.APPROVED,
                                                    MembershipApplication.Status.REJECTED)).count()
        if user.has_perm('membership.view_pdaoregistration'):
            # Earlier online records can lack the channel key; onsite records
            # explicitly carry walk_in. Match the existing review-page fallback.
            counts['pdao'] = PDAORegistration.objects.filter(status=PDAORegistration.Status.RECEIVED).filter(
                Q(data__intake_channel='online') | ~Q(data__has_key='intake_channel')).count()
        if can_count_programs(user):
            counts['programs'] = ProgramApplication.objects.filter(status__in=PROGRAM_REVIEW_STATES).count()
        counts['membership'] = counts['association'] + counts['pdao']
    request._review_counts = counts
    return counts
