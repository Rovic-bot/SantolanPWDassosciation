from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from accounts.decorators import dashboard_required
from .approval_email import retry_approval_email
from .approval_email_models import MembershipApprovalEmail
from .registration_services import require_staff


@never_cache
@dashboard_required
@require_POST
def retry(request, reference, email_id):
    require_staff(request.user, 'membership.decide_membershipapplication')
    get_object_or_404(MembershipApprovalEmail, pk=email_id, intake__reference=reference)
    try:
        retry_approval_email(email_id, reference=reference, user=request.user,
                             confirmed=request.POST.get('confirm') == '1')
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    else:
        messages.success(request, 'Approval email retry recorded. The membership decision remains saved.')
    return redirect(reverse('membership:registration_detail', args=[reference]) + '#membership-approval-email')


@never_cache
@dashboard_required
@require_POST
def retry_pending(request, reference, email_id):
    from .pending_email import retry_pending_email
    from .pending_email_models import MembershipPendingEmail
    require_staff(request.user, 'membership.decide_membershipapplication')
    get_object_or_404(MembershipPendingEmail, pk=email_id, intake__reference=reference)
    try:
        if request.POST.get('confirm') != '1':
            raise ValidationError('Confirm the pending-email retry.')
        retry_pending_email(reference, user=request.user, identifier=email_id)
    except ValidationError as error:
        messages.error(request, ' '.join(error.messages))
    else:
        messages.success(request, 'Pending email retry recorded. The application remains pending.')
    return redirect(reverse('membership:registration_detail', args=[reference]) + '#pending-email-history')
