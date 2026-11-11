from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import dashboard_required
from .certificate_delivery import retry_certificates
from .certificate_models import SelectionCertificateEmail
from .certificate_pdf import attachment_details
from .generation import publisher


@never_cache
@dashboard_required
@require_POST
def retry(request, program_id):
    publisher(request.user)
    try:
        count = retry_certificates(program_id, user=request.user)
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    else:
        messages.success(request, f'{count} pending certificate emails queued.' if count
                         else 'No certificate emails are currently available to retry.')
    return redirect('announcements:prepare_results', program_id=program_id)


@never_cache
@dashboard_required
@require_GET
def download(request, pk):
    publisher(request.user)
    job = get_object_or_404(SelectionCertificateEmail, pk=pk)
    filename, content_type = attachment_details(job.document)
    response = HttpResponse(bytes(job.document), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
