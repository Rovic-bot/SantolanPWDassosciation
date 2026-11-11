from io import BytesIO
from urllib.parse import urlencode
from uuid import UUID

import qrcode
from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST, require_safe

from .models import Program, ProgramApplication
from .tracking_forms import ApplicationTrackingForm
from .tracking_services import (SESSION_KEY, VERIFICATION_FAILED, progress_from_grant,
    reserve_tracking_attempt, verify_application)


def private_response(response):
    response['Cache-Control'] = 'no-store, private'
    # Preserve same-origin POST/CSRF verification, including the Finish button.
    response['Referrer-Policy'] = 'same-origin'
    response['X-Robots-Tag'] = 'noindex, nofollow, noarchive'
    return response


def tracking_url(reference):
    return reverse('programs:tracking') + '?' + urlencode({'reference': reference})


def unavailable(request):
    if SESSION_KEY in request.session:
        del request.session[SESSION_KEY]
        # Django intentionally skips automatic session saving on 5xx responses.
        request.session.save()
    return private_response(render(request, 'programs/tracking/unavailable.html', status=503))


@never_cache
@require_http_methods(['GET', 'HEAD', 'POST'])
def verify(request):
    if not settings.PROGRAM_TRACKING_ENABLED:
        return unavailable(request)
    form = ApplicationTrackingForm(request.POST if request.method == 'POST' else None,
        initial={'reference': request.GET.get('reference', '')[:40]})
    status = 200
    if request.method == 'POST':
        request.session.pop(SESSION_KEY, None)
        allowed = reserve_tracking_attempt(request.POST.get('reference', ''),
            request.META.get('REMOTE_ADDR', ''))
        if not allowed:
            form.add_error(None, 'Too many tracking attempts. Please try again later or contact the Association Help Desk.')
            status = 429
        elif form.is_valid():
            grant = verify_application(form.cleaned_data)
            if grant:
                request.session.cycle_key()
                request.session[SESSION_KEY] = grant
                return private_response(redirect('programs:tracking_progress'))
            form.add_error(None, VERIFICATION_FAILED)
    response = private_response(render(request, 'programs/tracking/verify.html', {'form': form}, status=status))
    if status == 429:
        response['Retry-After'] = str(settings.PROGRAM_VERIFICATION_WINDOW_SECONDS)
    return response


@never_cache
@require_safe
def progress(request):
    if not settings.PROGRAM_TRACKING_ENABLED:
        return unavailable(request)
    summary = progress_from_grant(request.session.get(SESSION_KEY))
    if not summary:
        request.session.pop(SESSION_KEY, None)
        return private_response(redirect('programs:tracking'))
    return private_response(render(request, 'programs/tracking/progress.html', {'progress': summary}))


@never_cache
@require_POST
def finish(request):
    request.session.pop(SESSION_KEY, None)
    return private_response(redirect('programs:tracking'))


@never_cache
@require_safe
def receipt_qr(request, pk):
    if not (settings.PROGRAM_TRACKING_ENABLED and settings.PROGRAM_TRACKING_QR_ENABLED):
        return private_response(HttpResponse(status=404))
    try:
        reference = UUID(request.session.get('program_receipt', ''))
    except (ValueError, TypeError, AttributeError):
        return private_response(HttpResponse(status=404))
    public_reference = ProgramApplication.objects.filter(pk=reference, program_id=pk,
        program__in=Program.objects.public()).values_list('public_reference', flat=True).first()
    if not public_reference:
        return private_response(HttpResponse(status=404))
    # Render locally: no reference or personal information goes to a QR provider.
    buffer = BytesIO()
    qrcode.make(request.build_absolute_uri(tracking_url(public_reference)),
        box_size=6, border=4).save(buffer, format='PNG')
    return private_response(HttpResponse(buffer.getvalue(), content_type='image/png'))

