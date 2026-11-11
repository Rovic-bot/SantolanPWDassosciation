"""Public destinations for the existing authorized result publication source."""
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .models import Announcement
from .notices import public_notice, public_schedule
from .public_claims import result_with_claim_status


def published_results():
    # This shared publication gate revalidates the source digest/current decisions.
    # Historical revisions, legacy applicant lists and private drafts are excluded.
    return Announcement.objects.filter(
        program__isnull=False, result_revision__isnull=False,
    ).published().select_related('result_revision')


def public_result(item):
    """Serialize an already-authorized publication without private ORM objects."""
    return {
        'pk': item.pk,
        'published_at': item.published_at,
        'public_payload': result_with_claim_status(item),
        'capacity_label': item.program.capacity_label,
        'schedule': public_schedule(item.program),
        'notice': public_notice(item),
    }


@never_cache
@require_safe
def result_detail(request, pk):
    item = get_object_or_404(published_results().filter(pk=pk))
    return render(request, 'results/public_detail.html', {'result': public_result(item)})
