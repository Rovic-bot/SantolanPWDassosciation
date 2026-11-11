from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.decorators import dashboard_required
from ewaf.operational_services import actor, configuration_token
from ewaf.operational_models import OperationalConfiguration
from programs.models import Program
from . import live_services as service
from .live_forms import BindingForm


def private(response):
    response['Cache-Control'] = 'no-store, private'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def unavailable():
    return private(HttpResponse('The additive dataset-policy schema/workflow is not installed or enabled. No approval or activation has occurred.', status=503))


@never_cache
@dashboard_required
@require_http_methods(['GET', 'POST'])
def binding(request, pk):
    current = actor(request.user)
    if not service.schema_available() or not service.enabled():
        return unavailable()
    program = get_object_or_404(Program, pk=pk)
    form = BindingForm(request.POST if request.method == 'POST' else None, initial={'expected': configuration_token(program)})
    if request.method == 'POST' and form.is_valid():
        try:
            service.bind(pk, user=current, expected=form.cleaned_data['expected'], policy_id=form.cleaned_data['policy'].pk,
                cutoff=form.cleaned_data['cutoff'], reason=form.cleaned_data['reason'])
            return redirect('programs:manage_detail', pk=pk)
        except ValidationError as error:
            form.add_error(None, error)
    return private(render(request, 'ewaf/revised/policy_binding.html', {'program': program, 'form': form,
        'configuration': OperationalConfiguration.objects.filter(program=program).first()}))
