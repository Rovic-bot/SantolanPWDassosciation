from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from programs.models import Program
from .evidence import digest
from .models import ConfigurationRevision
from .configuration_forms import DraftForm, ValidationForm, ReviewForm, AuthorityEvidenceForm
from .configuration_services import (VIEW, configuration_context, record_configuration, record_validation,
                                     record_review, record_authority_evidence)
from .configuration_readiness import configuration_diagnostics
from .ahp_validation import CRITERIA
from .policy_reference import REVIEW_ITEMS

ACTIONS = {
    'draft': (DraftForm, record_configuration, 'ewaf.record_configurationrevision', 'Record configuration draft'),
    'validate': (ValidationForm, record_validation, 'ewaf.record_configurationvalidation', 'Retain reference validation'),
    'review': (ReviewForm, record_review, 'ewaf.record_configurationreview', 'Record configuration review'),
    'authority': (AuthorityEvidenceForm, record_authority_evidence, 'ewaf.record_configurationauthorizationevidence', 'Record non-effective authority evidence'),
}


@never_cache
@dashboard_required
@require_safe
def configuration_list(request):
    require_workspace_permissions(request.user, *VIEW)
    page = Paginator(Program.objects.order_by('name', 'pk'), 20).get_page(request.GET.get('page'))
    return render(request, 'ewaf/configuration_list.html', {'page': page})


@never_cache
@dashboard_required
@require_safe
def policy_review(request, pk):
    require_workspace_permissions(request.user, *VIEW)
    program = get_object_or_404(Program, pk=pk)
    return render(request, 'ewaf/policy_review.html', {'program': program, 'review_items': REVIEW_ITEMS})


@never_cache
@dashboard_required
@require_safe
def configuration_detail(request, pk):
    require_workspace_permissions(request.user, *VIEW)
    program = get_object_or_404(Program, pk=pk)
    result = configuration_diagnostics(pk, user=request.user)
    current = ConfigurationRevision.objects.filter(program=program).first()
    validation = current.validations.filter(pk=result['validation']).first() if current and result['validation'] else None
    calculation = validation.result.get('calculation') if validation else None
    derived_weights = [(code, calculation['weights'][code]) for code in CRITERIA] if calculation else []
    actions = [{'name': name, 'label': spec[3]} for name, spec in ACTIONS.items() if
        request.user.has_perm(spec[2]) and (name == 'draft' or current and (name == 'validate' or current.validations.exists()))]
    return render(request, 'ewaf/configuration_detail.html', {'program': program, 'result': result,
        'current': current, 'validation': validation, 'derived_weights': derived_weights, 'actions': actions})


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def configuration_action(request, pk, action):
    if action not in ACTIONS:
        raise Http404
    form_type, service, permission, label = ACTIONS[action]
    require_workspace_permissions(request.user, *VIEW, permission)
    program = get_object_or_404(Program, pk=pk)
    context = configuration_context(program)
    validation = context['histories'].get('validations')
    initial = {'expected_context': digest(context), 'policy_id': context['source']['policy'],
               'configuration_id': context['configuration'], 'validation_id': validation['id'] if validation else None,
               'input_mode': 'pairs'}
    form = form_type(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            service(pk, user=request.user, **form.cleaned_data)
            return redirect('ewaf:configuration_detail', pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
    return render(request, 'ewaf/configuration_form.html', {'program': program, 'form': form, 'label': label})


@never_cache
@dashboard_required
@require_safe
def configuration_history(request, pk):
    require_workspace_permissions(request.user, *VIEW)
    program = get_object_or_404(Program, pk=pk)
    revisions = ConfigurationRevision.objects.filter(program=program)
    selected = request.GET.get('revision')
    if selected and (not selected.isascii() or not selected.isdigit() or len(selected) > 19):
        raise Http404
    current = get_object_or_404(revisions, pk=selected) if selected else revisions.first()
    return render(request, 'ewaf/configuration_history.html', {'program': program, 'current': current,
        'page': Paginator(revisions, 10).get_page(request.GET.get('page')),
        'validations': Paginator(current.validations.all(), 10).get_page(request.GET.get('validations')) if current else None,
        'reviews': Paginator(current.reviews.all(), 10).get_page(request.GET.get('reviews')) if current else None,
        'authorities': Paginator(current.authority_evidence.all(), 10).get_page(request.GET.get('authorities')) if current else None})
