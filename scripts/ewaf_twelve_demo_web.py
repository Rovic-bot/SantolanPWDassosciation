"""Routes and visual identification available only in the isolated demo settings."""
import os
from pathlib import Path


def verify_connection(sender=None, connection=None, **kwargs):
    from django.conf import settings
    from django.core.exceptions import ImproperlyConfigured
    manifest = getattr(settings, 'EWAF_TWELVE_DEMO', {})
    if not manifest or connection.vendor != 'mysql':
        raise ImproperlyConfigured('Dedicated EWAF demo MySQL required.')
    with connection.cursor() as cursor:
        cursor.execute('SELECT DATABASE(), @@datadir, @@port, @@server_uuid')
        name, datadir, port, server_uuid = cursor.fetchone()
    if (name != manifest['database'] or Path(datadir).resolve() != Path(manifest['datadir']).resolve()
            or int(port) != manifest['mysql_port'] or server_uuid != manifest['server_uuid']):
        connection.close()
        raise ImproperlyConfigured('EWAF demo database identity mismatch; refusing access.')


class DevelopmentIdentityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        from django.http import HttpResponseBadRequest
        if not getattr(settings, 'EWAF_TWELVE_DEMO', None):
            return HttpResponseBadRequest('Dedicated demo settings required.')
        response = self.get_response(request)
        response['X-Santolan-Environment'] = 'MAIN-DEVELOPMENT'
        return response


def health(request):
    from django.conf import settings
    from django.http import JsonResponse
    manifest = settings.EWAF_TWELVE_DEMO
    return JsonResponse({'purpose': manifest['purpose'], 'instance_id': manifest['instance_id'], 'pid': os.getpid()})


def index(request):
    from django.contrib.auth.views import redirect_to_login
    from django.shortcuts import redirect
    from core.permissions import require_workspace_permissions
    from ewaf.operational_services import VIEW
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    require_workspace_permissions(request.user, *VIEW)
    return redirect('ewaf:operational_programs')


# Import the ordinary routes lazily, after Django's application registry is ready.
def _routes():
    from django.urls import include, path
    return [path('ewaf-demo/health/', health), path('ewaf-demo/', index), path('', include('config.urls'))]


def __getattr__(name):
    if name == 'urlpatterns':
        return _routes()
    raise AttributeError(name)
