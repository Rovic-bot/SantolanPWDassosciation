"""Read-only program overview for the assistance releases workspace."""
from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.utils import timezone

from programs.catalog import REGISTRATION, SORTS
from programs.models import Program, ProgramApplication
from .models import AssistanceRelease


def receipt_counts(programs):
    """Summarize all programs together, without loading members or ranking runs."""
    if not programs:
        return {}
    applications = ProgramApplication.objects.filter(program_id__in=[program.pk for program in programs]).order_by().annotate(
        has_receipt=Exists(AssistanceRelease.objects.successful().filter(application_id=OuterRef('pk'))))
    selected = Q(program__ewaf_applicable=False, assistance_case__decision='approved')
    from programs.mandatory_ewaf import retained_selected_ids
    retained = set().union(*(retained_selected_ids(program) for program in programs))
    selected |= Q(pk__in=retained)
    reserved = Q(assistance_case__decision='approved')
    if any(program.ewaf_applicable for program in programs):
        from ewaf.operational_services import available
        from ewaf.operational_models import OperationalDecision
        if available():
            latest = OperationalDecision.objects.filter(
                program_id=OuterRef('program_id'), application_id=OuterRef('pk')
            ).order_by('-revision').values('outcome')[:1]
            applications = applications.annotate(latest_decision=Subquery(latest))
            ewaf_selected = Q(program__ewaf_applicable=True, latest_decision='SELECTED')
            selected |= ewaf_selected
            reserved |= ewaf_selected
    counts = applications.values('program_id').annotate(
        applicant_count=Count('pk'),
        selected_count=Count('pk', filter=selected),
        received_count=Count('pk', filter=Q(has_receipt=True)),
        pending_count=Count('pk', filter=selected & Q(has_receipt=False)),
        allocated_count=Count('pk', filter=reserved),
    )
    return {row['program_id']: row for row in counts}


def workspace(request):
    programs = list(Program.objects.with_public_application_status(at=timezone.now()))
    counts = receipt_counts(programs)
    types = sorted({program.assistance_type for program in programs})
    query = request.GET.get('q', '').strip()[:200]
    assistance_type = request.GET.get('assistance_type', '')
    assistance_type = assistance_type if assistance_type in types else ''
    status = request.GET.get('status', '')
    status = status if status in Program.Status.values else ''
    registration = request.GET.get('registration', '')
    registration = registration if registration in dict(REGISTRATION) else ''
    sort = request.GET.get('sort', 'newest')
    sort = sort if sort in dict(SORTS) else 'newest'
    with_applications = request.GET.get('with_applications') == '1'
    keys = {
        'newest': lambda p: (-p.created_at.timestamp(), str(p.pk)),
        'oldest': lambda p: (p.created_at.timestamp(), str(p.pk)),
        'az': lambda p: (p.name.casefold(), str(p.pk)),
        'za': lambda p: (p.name.casefold(), str(p.pk)),
        'start': lambda p: (p.starts_at is None, p.starts_at, str(p.pk)),
        'end': lambda p: (p.ends_at is None, p.ends_at, str(p.pk)),
    }
    programs.sort(key=keys[sort], reverse=sort == 'za')
    for program in programs:
        summary = counts.get(program.pk, dict(applicant_count=0, selected_count=0,
            received_count=0, pending_count=0, allocated_count=0)).copy()
        total = summary['received_count'] + summary['pending_count']
        summary['beneficiary_count'] = total
        summary['percent'] = round(100 * summary['received_count'] / total) if total else 0
        summary['available_slots'] = max(0, program.slot_limit - summary['allocated_count']) if program.slot_limit is not None else None
        if summary['pending_count']:
            summary.update(state='review', label='Receipts pending')
        elif summary['received_count']:
            summary.update(state='ready', label='Receipts recorded')
        elif summary['applicant_count']:
            summary.update(state='pending', label='Awaiting selection')
        else:
            summary.update(state='pending', label='No applicants yet')
        summary['search'] = ' '.join((program.name, program.public_code or '', program.description, program.assistance_type))
        summary['visible'] = ((not query or query.casefold() in summary['search'].casefold())
            and (not assistance_type or program.assistance_type == assistance_type)
            and (not status or program.status == status)
            and (not registration or program.public_application_status == registration)
            and (not with_applications or summary['applicant_count'] > 0))
        program.release_summary = summary
    matches = [program for program in programs if program.release_summary['visible']]
    selected_id = request.GET.get('selected', '')
    if selected_id not in {str(program.pk) for program in matches}:
        selected_id = str(matches[0].pk) if matches else ''
    for program in programs:
        program.release_summary['selected'] = str(program.pk) == selected_id
    # Like the EWAF list, all lightweight rows/panels are ready for instant
    # selection and filtering. Neither operation performs a write or a fetch.
    return {
        'program_rows': programs, 'selected_id': selected_id,
        'page_obj': Paginator(matches, max(20, len(matches))).get_page(1),
        'query': query, 'assistance_types': types, 'assistance_type': assistance_type,
        'statuses': Program.Status.choices, 'status': status,
        'registration_options': REGISTRATION, 'registration': registration,
        'sort_options': SORTS, 'sort': sort, 'with_applications': with_applications,
    }
