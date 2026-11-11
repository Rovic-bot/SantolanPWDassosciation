"""Deployment health wiring; all existing application URLs stay unchanged."""
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe


@never_cache
@require_safe
def health(request):
    """Process liveness only: no database queries or identifying information."""
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('healthz/', health, name='deployment-health'),
    path('', include('config.urls')),
]
