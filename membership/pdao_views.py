"""Transient PDAO form preparation: no registration, reference or PDAO transfer."""
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_safe

from .guidance import membership_guidance
from .pdf_registration_forms import PDAOForm, ASSOCIATION_PDF, PDAO_PDF


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
@csrf_protect
@sensitive_post_parameters()
def prepare(request):
    if getattr(settings, 'PDAO_REGISTRATION_ENABLED', False):
        from .pdao_registration_views import apply
        return apply(request)
    # Data is used for this response only: never placed in sessions, database,
    # files, URLs, logs, the Association inbox, or an external service.
    try:
        length = int(request.META.get('CONTENT_LENGTH') or 0)
    except ValueError:
        return HttpResponse(status=400)
    if length < 0 or length > 64 * 1024:
        return HttpResponse('The form is too large. No uploads are needed.', status=413)
    form = PDAOForm(request.POST if request.method == 'POST' else None,
                    request.FILES if request.method == 'POST' else None,
                    initial={'date_applied': timezone.localdate(), 'accomplished_by': 'Applicant'})
    if request.method == 'POST' and form.is_valid():
        response = render(request, 'membership/registration/pdao_print.html', {
            'submitted': form.submitted_data(), **membership_guidance()})
    else:
        response = render(request, 'membership/registration/pdao_apply.html', {
            'form': form}, status=400 if form.errors else 200)
    # HTML form POSTs under no-referrer can send Origin: null, which Django
    # correctly rejects. Retain the origin for our own forms while withholding
    # the referrer from external destinations.
    response['Referrer-Policy'] = 'same-origin'
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


@require_safe
def blank_form(request, category):
    # Only these two owner-supplied blank forms may be served publicly.
    filename = {'association': ASSOCIATION_PDF, 'pdao': PDAO_PDF}.get(category)
    if filename is None:
        raise Http404
    try:
        handle = (settings.BASE_DIR / filename).open('rb')
    except FileNotFoundError:
        raise Http404 from None
    response = FileResponse(handle, content_type='application/pdf', as_attachment=True, filename=filename)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "sandbox; default-src 'none'"
    return response
