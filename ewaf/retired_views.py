"""Read-only bookmark redirects for the removed EWAF auxiliary screens."""
from urllib.parse import urlencode

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from accounts.decorators import dashboard_required
from programs.models import Program, ProgramApplication
from .operational_models import OperationalRun
from .operational_services import actor
from .revised.live_models import SharedDatasetPolicy


@never_cache
@dashboard_required
@require_safe
def dataset_inputs(request, reference):
    actor(request.user)
    application = get_object_or_404(ProgramApplication, pk=reference)
    return redirect(reverse('ewaf:operational_workspace', args=[application.program_id]) + '#readiness')


@never_cache
@dashboard_required
@require_safe
def dataset_policy(request, policy_id=None):
    actor(request.user)
    if policy_id is not None:
        get_object_or_404(SharedDatasetPolicy, pk=policy_id)
    return redirect('ewaf:vault')


@never_cache
@dashboard_required
@require_safe
def calculation_guide(request, pk):
    actor(request.user)
    program = get_object_or_404(Program, pk=pk, ewaf_applicable=True)
    url = reverse('ewaf:operational_workspace', args=[program.pk])
    if request.GET.get('run'):
        try:
            run_id = int(request.GET['run'])
        except ValueError:
            raise Http404 from None
        run = get_object_or_404(OperationalRun, pk=run_id, program=program)
        url += '?' + urlencode({'run': run.pk})
    return redirect(url + '#results')
