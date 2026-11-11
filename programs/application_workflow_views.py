from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .forms import MembershipCheckForm
from . import application_workflow as workflow
from .models import Program
from .services import reserve_verification
from .tracking_views import private_response


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def verify(request, pk):
    if not workflow.enabled():
        from .views import verify as legacy_verify
        return legacy_verify(request, pk)
    program = get_object_or_404(Program.objects.public(), pk=pk)
    form = MembershipCheckForm(request.POST if request.method == 'POST' else None,
        initial={'version': program.version})
    outcome, message, status = '', '', 200
    available = workflow.availability(program)
    if request.method == 'POST':
        request.session.pop('program_verification', None)
        if not reserve_verification(request.POST.get('control_number', '')[:100], request.META.get('REMOTE_ADDR', '')):
            form.add_error(None, 'Too many attempts. Please try again later or contact the Association Help Desk.')
            status = 429
        elif form.is_valid() and available:
            try:
                grant, outcome, message = workflow.verify(pk, **form.cleaned_data)
            except ValidationError as error:
                form.add_error(None, error)
                outcome = 'unable'
            else:
                if grant:
                    request.session.cycle_key()
                    request.session['program_verification'] = grant
                    return private_response(redirect('programs:apply', pk=pk))
        elif not available:
            message = 'Applications are currently unavailable. Review the schedule or contact the Association Help Desk.'
        else:
            outcome = 'unable'
            form.add_error(None, workflow.FAILED)
    response = private_response(render(request, 'programs/workflow/verify.html', {
        'program': program, 'form': form, 'screening': outcome, 'screening_message': message,
        'applications_available': available}, status=status))
    if status == 429:
        response['Retry-After'] = str(settings.PROGRAM_VERIFICATION_WINDOW_SECONDS)
    return response


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def apply(request, pk):
    from .views import apply as existing_apply
    if not workflow.enabled():
        return existing_apply(request, pk)
    program = get_object_or_404(Program.objects.public(), pk=pk)
    if not workflow.secure_grant(request.session.get('program_verification'), program):
        request.session.pop('program_verification', None)
        return private_response(redirect('programs:verify', pk=pk))
    return private_response(existing_apply(request, pk))
