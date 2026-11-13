"""Read-only EWAF landing-page projections; never authorize or calculate scores."""
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q

from programs.catalog import capacity_context
from programs.models import Program
from . import operational_services as service
from .operational_models import OperationalConfiguration
from .weight_input import CRITERIA, NAMES, percentages
from .household_criteria import criteria_for

CONFIGURATIONS = (('ready', 'Configuration ready'), ('inherited', 'Vault assigned'), ('draft', 'Draft'),
                  ('intake_ready', 'Weights approved; scoring pending'),
                  ('review', 'Needs review'), ('unconfigured', 'Not configured'))
SORTS = (('newest', 'Newest first'), ('oldest', 'Oldest first'),
         ('az', 'Name A–Z'), ('za', 'Name Z–A'))


def configuration_summary(program):
    from .shared_weights import publication_locked
    latest = OperationalConfiguration.objects.filter(program=program).first()
    state, weights = 'unconfigured', None
    weight_version = None
    if latest:
        state = 'draft' if latest.status == 'DRAFT' else 'review'
        if latest.vault_revision_id and latest.status == 'DRAFT':
            state = 'inherited'
            from .vault_policy import scoring_pending
            if scoring_pending(latest.policy):
                from .intake_policy import validate_weights
                try:
                    validate_weights(latest)
                except ValidationError:
                    state = 'review'
                else:
                    state = 'intake_ready'
                    weights = percentages(latest.validation['weights'])
        if latest.status == 'LOCKED':
            try:
                current = service.latest_configuration(program)
                from .shared_weights import current as current_weights
                selected = current_weights(current)
            except ValidationError:
                pass
            else:
                state = 'ready'
                weights = percentages(selected['weights'] if selected else current.validation['weights'])
                weight_version = selected['id'] if selected else None
    return {'state': state, 'label': dict(CONFIGURATIONS)[state], 'weights_locked': publication_locked(program),
            'version': latest.revision if latest else None, 'weight_version': weight_version,
            'rows': [{'code': code, 'name': NAMES[code],
                      'percent': f'{weights[code] / 100:.2f}' if weights is not None else None}
                     for code in criteria_for(latest.policy) if latest] if latest else
                    [{'code': code, 'name': NAMES[code], 'percent': None} for code in CRITERIA]}


def applicant_counts(programs):
    # Recorded review outcomes do not substitute for calculation readiness.
    eligible = Q(applications__assistance_case__eligibility_id='eligible',
        applications__status__in=['ELIGIBLE', 'EWAF_READY', 'EWAF_PROCESSED', 'RANKED',
                                  'SELECTED', 'WAITLISTED', 'NOT_SELECTED', 'COMPLETED'])
    pending = (~Q(applications__status__in=['CLOSED', 'INELIGIBLE']) &
               (Q(applications__status__in=['PENDING_PHOTO_VERIFICATION', 'PHOTO_VERIFIED',
                    'VERIFICATION_FAILED', 'NEEDS_INFORMATION', 'ELIGIBILITY_REVIEW']) |
                Q(applications__assistance_case__isnull=True) |
                Q(applications__assistance_case__eligibility_id__in=['pending', 'review'])))
    return programs.annotate(applicant_count=Count('applications', distinct=True),
        eligible_count=Count('applications', filter=eligible, distinct=True),
        pending_count=Count('applications', filter=pending, distinct=True))


def cards(request):
    query = request.GET.get('q', '').strip()[:200]
    state = request.GET.get('configuration', '')
    state = state if state in dict(CONFIGURATIONS) else ''
    sort = request.GET.get('sort', 'newest')
    sort = sort if sort in dict(SORTS) else 'newest'
    programs = Program.objects.filter(ewaf_applicable=True)
    if query:
        programs = programs.filter(Q(name__icontains=query) | Q(public_code__icontains=query))
    summaries = {}
    if state:
        # Check readiness before pagination, including expired/stale locks.
        summaries = {program.pk: configuration_summary(program) for program in programs}
        programs = programs.filter(pk__in=[pk for pk, summary in summaries.items() if summary['state'] == state])
    ordering = {'newest': ('-created_at', '-pk'), 'oldest': ('created_at', 'pk'),
                'az': ('name', 'pk'), 'za': ('-name', 'pk')}[sort]
    page = Paginator(applicant_counts(programs).order_by(*ordering), 20).get_page(request.GET.get('page'))
    for program in page:
        program.ewaf_card = summaries.get(program.pk) or configuration_summary(program)
        capacity_context(program, request.user)
    return {'page_obj': page, 'query': query, 'configuration_status': state,
            'configuration_options': CONFIGURATIONS, 'sort': sort, 'sort_options': SORTS}
