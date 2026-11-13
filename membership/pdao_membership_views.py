"""Private, applicant-requested membership intake after confirmed ID collection."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import dashboard_required
from . import pdao_membership as services, pdao_services, registration_services
from .guidance import membership_guidance
from .pdao_models import PDAOIDClaim
from .pdao_registration_views import private_page
from .prpwd import registry_url
from .registration_policy import policy_for
from .registration_views import _session_binding


@private_page
@dashboard_required
@require_POST
@csrf_protect
@sensitive_post_parameters()
def claim_id(request, key):
    try:
        services.record_claim(key, user=request.user, data=request.POST)
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    else:
        messages.success(request, 'PWD ID collection recorded. The applicant may now request Association membership.')
    return redirect('membership:pdao_detail', key=key)


@private_page
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
@csrf_protect
@sensitive_post_parameters()
def membership(request, key):
    services.require_actor(request.user)
    registration = pdao_services.staff_record(key, request.user)
    claim = PDAOIDClaim.objects.select_related('registration', 'membership_intake').filter(registration=registration).first()
    if not claim:
        raise Http404('Record PWD ID collection before opening the membership form.')
    if claim.membership_intake_id:
        return redirect('membership:registration_detail', reference=claim.membership_intake.reference)
    policy = policy_for('staff')
    # Each PDAO transfer has its own session-bound submission context.
    binding = registration_services.binding_for(f'{_session_binding(request)}:pdao-membership:{key}')
    if request.method == 'POST':
        context_id = request.POST.get('context_id', '')
        form = services.PDAOAssociationForm(request.POST, request.FILES, claim=claim, policy=policy)
        if getattr(request, 'upload_limit_exceeded', False):
            form.is_valid()
            form.add_error(None, 'The uploads exceed the permitted total limit.')
        elif form.is_valid():
            try:
                intake = services.submit_membership(key, user=request.user, context_id=context_id,
                    binding=binding, data=request.POST, files=request.FILES)
            except ValidationError as error:
                form.add_error(None, error)
            else:
                messages.success(request, 'Association membership application saved for review with the recorded PDAO details.')
                return redirect('membership:registration_detail', reference=intake.reference)
    else:
        context_id = str(registration_services.issue_context(binding, user=request.user, channel='walk_in').pk)
        form = services.PDAOAssociationForm(claim=claim, policy=policy)
    return render(request, 'membership/onsite/intake.html', {
        **membership_guidance(), 'form': form, 'policy': policy, 'context_id': context_id,
        'title': 'Association membership from PDAO', 'pdao_transfer': registration,
        'source_disabilities': registration.current_data.get('disability_types', []),
        'prpwd_lookup_url': registry_url()}, status=400 if form.errors else 200)
