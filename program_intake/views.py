from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from programs.models import Program, ProgramApplication
from programs.services import reserve_verification
from programs.views import private_status_response
from ewaf.evidence import VIEW, source_context, digest
from ewaf.operational_services import latest_configuration
from .access import FAILED, verify_member, secure_grant
from .forms import MembershipVerificationForm, SourceReviewForm, SourcePolicyForm
from . import sources


def private_form_response(response):
    response = private_status_response(response)
    # no-referrer produces Origin: null on browser form navigation. Keep
    # same-origin CSRF validation and suppress referrers to external sites.
    response['Referrer-Policy'] = 'same-origin'
    return response


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def verify(request, pk):
    program = get_object_or_404(Program.objects.public(), pk=pk)
    form = MembershipVerificationForm(request.POST if request.method == 'POST' else None,
                                      initial={'version': program.version})
    status = 200
    if request.method == 'POST':
        request.session.pop('program_verification', None)
        allowed = reserve_verification(request.POST.get('control_number', '')[:100], request.META.get('REMOTE_ADDR', ''))
        if not allowed:
            # Identical private-match wording; no member existence or failed-field disclosure.
            form.is_valid()
            form.add_error(None, FAILED)
            status = 429
        elif form.is_valid():
            try:
                grant = verify_member(pk, **form.cleaned_data)
            except ValidationError as error:
                if getattr(error, 'code', None) in ('ineligible', 'needs_information'):
                    form.add_error(None, error)
                else:
                    form.add_error(None, FAILED)
            else:
                request.session.cycle_key()
                request.session['program_verification'] = grant
                return redirect('programs:apply', pk=pk)
        else:
            form.add_error(None, FAILED)
    response = private_form_response(render(request, 'program_intake/verify.html',
        {'program': program, 'form': form, 'verification_failed': request.method == 'POST'}, status=status))
    if status == 429:
        response['Retry-After'] = str(settings.PROGRAM_VERIFICATION_WINDOW_SECONDS)
    return response


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def apply(request, pk):
    from programs.views import apply as existing_apply
    program = get_object_or_404(Program.objects.public(), pk=pk)
    if not secure_grant(request.session.get('program_verification'), program):
        request.session.pop('program_verification', None)
        return redirect('programs:verify', pk=pk)
    return private_form_response(existing_apply(request, pk))


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def source_review(request, reference):
    require_workspace_permissions(request.user, *VIEW, 'programs.view_programdocument',
                                  'program_intake.review_socioeconomic')
    application = get_object_or_404(ProgramApplication.objects.select_related('program', 'member__application'), pk=reference)
    errors, form, document, configuration = [], None, None, None
    try:
        configuration = latest_configuration(application.program)
        if not sources.uses_sources(configuration):
            raise ValidationError('This program retains its existing authorized evidence configuration. A new program source policy is required for program-document SI.')
        document = sources.si_document(application, configuration)
        token = sources.review_token(application, configuration)
        from django.utils import timezone
        form = SourceReviewForm(request.POST if request.method == 'POST' and request.POST.get('action') == 'review' else None,
            initial={'expected': token, 'observation_start': timezone.localdate(), 'observation_end': timezone.localdate()})
        if request.method == 'POST':
            try:
                if request.POST.get('action') == 'review' and form.is_valid():
                    row = sources.review_si(reference, user=request.user, **form.cleaned_data)
                    messages.success(request, 'Socioeconomic evidence review retained. Refresh the sources after completing eligibility review.')
                    return redirect('intake:sources', reference=reference)
                elif request.POST.get('action') == 'collect':
                    sources.collect_sources(reference, user=request.user, expected=request.POST.get('context'),
                        reason=request.POST.get('reason', ''), confirmed=request.POST.get('confirmed') == 'on')
                    messages.success(request, 'SI, onsite employment, confirmed receipts and onsite dependents verified and collected. Historical assessments are preserved.')
                    return redirect('intake:sources', reference=reference)
            except ValidationError as error:
                errors.extend(error.messages)
    except ValidationError as error:
        errors.extend(error.messages)
    context = source_context(application)
    return private_form_response(render(request, 'program_intake/sources.html', {
        'application': application, 'program': application.program, 'configuration': configuration,
        'document': document, 'form': form, 'errors': errors, 'context_token': digest(context),
        'si_rule': configuration.policy['criteria']['SI'] if configuration else None,
        'reviews': sources.SocioeconomicReview.objects.filter(application=application),
        'assessments': [sources.CriterionAssessment.objects.filter(application=application, criterion=code).first()
                        for code in ('SI', 'ES', 'PA', 'ND')],
        'receipt_count': context['pa']['count']}))


@never_cache
@dashboard_required
@require_http_methods(['GET', 'HEAD', 'POST'])
def source_policy(request, pk):
    from ewaf.operational_services import configuration_token
    from .policy import authorize_sources
    require_workspace_permissions(request.user, *VIEW, 'ewaf.authorize_operational', 'ewaf.record_evidencepolicyrevision')
    program = get_object_or_404(Program, pk=pk)
    form = SourcePolicyForm(request.POST if request.method == 'POST' else None, program=program,
        initial={'expected': configuration_token(program)})
    if request.method == 'POST' and form.is_valid():
        try:
            authorize_sources(pk, user=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(request, 'A new source configuration was authorized. Earlier definitions and results remain in history; review current evidence and recalculate.')
            return redirect('ewaf:operational_workspace', pk=pk)
    return private_form_response(render(request, 'program_intake/policy.html', {'program': program, 'form': form}))
