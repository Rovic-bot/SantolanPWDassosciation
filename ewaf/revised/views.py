from uuid import UUID, uuid4

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.views.decorators.debug import sensitive_post_parameters
from accounts.decorators import dashboard_required
from programs.models import Program
from . import services
from .models import RevisedPreviewRun as Run
from .forms import PreviewForm
from .math import CRITERIA, NAMES, DEFAULTS, LIMITS, CalculationError, display, number, proposal


def private(response):
    response['Cache-Control'] = 'no-store, private'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def weight_rows(form):
    return [{'code': code, 'name': name, 'field': form[code], 'lower': lower, 'upper': upper,
             'default': default} for code, name, (lower, upper), default in zip(CRITERIA, NAMES, LIMITS, DEFAULTS)]


def remaining_weight(form):
    values = {code: str(form[code].value()) for code in CRITERIA[:4]}
    try:
        weights = proposal(values)
    except CalculationError:
        return {'hm_percent': '—', 'weight_total': 'Invalid'}
    return {'hm_percent': display(weights[4] * 100), 'weight_total': '100.00'}


def breakdown(config):
    data = config.data if hasattr(config, 'data') else config
    rows = []
    for index, (code, name) in enumerate(zip(CRITERIA, NAMES)):
        row = {'criterion': code, 'name': name, 'weight': data['weights'][index],
               'percent': display(number(data['weights'][index]['exact']) * 100)}
        if data['ahp']:
            row.update({key: data['ahp'][key][index] for key in ('matrix', 'normalized_matrix', 'column_sums', 'wsv', 'cv')})
        rows.append(row)
    return rows


@never_cache
@dashboard_required
@sensitive_post_parameters()
@require_http_methods(['GET', 'POST'])
def preview(request):
    current = services.actor(request.user)
    program = None
    if request.GET.get('program'):
        try:
            program_id = UUID(request.GET['program'])
        except (ValueError, TypeError) as error:
            raise Http404 from error
        program = get_object_or_404(Program, pk=program_id, ewaf_applicable=True)
    schema = services.available()
    can_calculate = current.has_perm('ewaf.calculate_revisedpreview')
    form = PreviewForm(request.POST if request.method == 'POST' else None,
        initial={'expected': services.token(program) if schema and program else '', 'request_key': uuid4()})
    config = result = pool = None
    status = 200
    if request.method == 'POST':
        services.actor(current, 'calculate')
        if request.POST.get('action') == 'OFFICIAL':
            return private(JsonResponse({'errors': services.official_readiness(program)}, status=400))
        if request.POST.get('action') not in ('PREVIEW', 'RETAIN'):
            form.add_error(None, 'Choose preview or retain a synthetic preview.')
        elif form.is_valid():
            try:
                if request.POST['action'] == 'RETAIN':
                    if not schema or not program:
                        raise ValidationError('Retained history requires the new preview schema and a selected program context.')
                    run = services.retain(program.pk, user=current, expected=form.cleaned_data['expected'],
                        request_key=form.cleaned_data['request_key'], reason=form.cleaned_data['reason'], **form.calculation_arguments())
                    return private(redirect('ewaf:revised_run', run_id=run.pk))
                config, pool, result = services.preview(user=current, program=program, **form.calculation_arguments())
            except ValidationError as error:
                form.add_error(None, error)
        if form.errors:
            status = 400
    elif can_calculate:
        config, pool, result = services.preview(user=current, program=program)
    context = {'revised_method': True, 'form': form, 'controls': weight_rows(form), **remaining_weight(form), 'program': program,
        'programs': Program.objects.filter(ewaf_applicable=True), 'can_calculate': can_calculate,
        'schema_available': schema, 'blockers': services.official_readiness(program),
        'configuration': config.data if config else None, 'math_rows': breakdown(config) if config else [],
        'result': result, 'pool': pool.data if pool else None,
        'history': Paginator(Run.objects.filter(program=program), 20).get_page(request.GET.get('page')) if schema and program else None}
    return private(render(request, 'ewaf/revised/preview.html', context, status=status))


@never_cache
@dashboard_required
@sensitive_post_parameters()
@require_http_methods(['GET', 'POST'])
def retained(request, run_id):
    current = services.actor(request.user)
    if not services.available():
        return private(HttpResponse('Revised synthetic history schema is not installed.', status=503))
    run = get_object_or_404(Run.objects.select_related('program', 'actor'), pk=run_id)
    run.clean()
    errors = []
    if request.method == 'POST':
        try:
            services.review(run.pk, user=current, expected=request.POST.get('expected'),
                finding=request.POST.get('finding'), reason=request.POST.get('reason'))
            return private(redirect('ewaf:revised_run', run_id=run.pk))
        except ValidationError as error:
            errors = error.messages
    return private(render(request, 'ewaf/revised/retained.html', {
        'revised_method': True, 'run': run, 'program': run.program, 'configuration': run.configuration,
        'math_rows': breakdown(run.configuration), 'pool': run.pool, 'result': run.result,
        'is_current': services.current(run), 'expected': services.review_token(run), 'errors': errors,
        'reviews': run.reviews.all(), 'can_review': current.has_perm('ewaf.review_revisedpreview'),
        'can_export': current.has_perm('ewaf.export_revisedpreview')}, status=400 if errors else 200))


@never_cache
@dashboard_required
@require_http_methods(['GET'])
def export(request, run_id):
    services.actor(request.user, 'export')
    if not services.available():
        return private(HttpResponse('Revised synthetic history schema is not installed.', status=503))
    get_object_or_404(Run, pk=run_id)
    format = request.GET.get('format', 'json')
    try:
        data = services.export(run_id, user=request.user, format=format)
    except ValidationError as error:
        return private(JsonResponse({'errors': error.messages}, status=400))
    response = HttpResponse(data, content_type={'json': 'application/json', 'csv': 'text/csv; charset=utf-8',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}[format])
    response['Content-Disposition'] = f'attachment; filename="synthetic-ewaf-preview-{run_id}.{format}"'
    return private(response)
