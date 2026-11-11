from django.urls import path
from .views import report

app_name = 'reports'
urlpatterns = [path(f'{kind}/', report, {'kind': kind}, name=kind)
               for kind in ('members', 'applications', 'programs', 'assistance')]
