"""The ordinary application routes plus a local launcher identity endpoint."""
from django.urls import include, path
from .fresh_development import health

urlpatterns = [path('__local__/health/', health), path('', include('config.urls'))]
