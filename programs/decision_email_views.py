from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.decorators import dashboard_required
from core.permissions import require_workspace_permissions
from .decision_email import retry_decision_email
from .decision_email_models import ApplicationDecisionEmail
from .models import ProgramApplication
from .review_services import DIRECT_REVIEW_PERMISSIONS


@never_cache
@dashboard_required
@require_POST
def retry(request, pk, reference, email_id):
    require_workspace_permissions(request.user, *DIRECT_REVIEW_PERMISSIONS)
    application = get_object_or_404(ProgramApplication, pk=reference, program_id=pk)
    get_object_or_404(ApplicationDecisionEmail, pk=email_id, application=application)
    try:
        retry_decision_email(email_id, application_id=application.pk, user=request.user,
                             confirmed=request.POST.get('confirm') == '1')
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    else:
        messages.success(request, 'Email retry recorded. The eligibility decision was not changed.')
    return redirect(reverse('programs:application_detail', args=[pk, reference]) + '#eligibility')
