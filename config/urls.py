from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from accounts.forms import StaffAuthenticationForm
from accounts.views import legacy_admin_login
from members.views import member_list
from programs.views import manage_list as program_portfolio
from programs.views import edit as program_builder
from programs.views import manage_detail as program_detail
from events.views import calendar_workspace
from core.workspace import application_programs
from ewaf.operational_views import programs as ewaf_selection

admin.site.site_header = 'Santolan PWD Administration'
admin.site.site_title = 'Santolan PWD'
admin.site.index_title = 'Administration'
admin.site.login_form = StaffAuthenticationForm
urlpatterns = [
    path('reports/', include('reports.urls')),
    path('ewaf/', include('ewaf.urls')),
    path('assistance/', include('assistance.urls')),
    path('programs/', include('programs.urls')),
    path('documents/', include('documents.urls')),
    path('events/', include('events.urls')),
    path('members/', include('members.urls')),
    path('announcements/', include('announcements.urls')),
    path('membership/', include('membership.urls')),
    path('accounts/', include('accounts.urls')),
    re_path(r'^admin/members/registration/?$', RedirectView.as_view(
        pattern_name='membership:encode', permanent=False), name='onsite_registration'),
    re_path(r'^admin/members/?$', member_list, name='member_directory'),
    re_path(r'^admin/programs/?$', program_portfolio, name='program_portfolio'),
    re_path(r'^admin/programs/create/?$', program_builder, name='program_builder'),
    re_path(r'^admin/programs/detail/?$', program_detail, name='program_detail'),
    re_path(r'^admin/events/?$', calendar_workspace, name='event_workspace'),
    re_path(r'^admin/applications/?$', application_programs, name='application_workspace'),
    re_path(r'^admin/ewaf/?$', ewaf_selection, name='ewaf_selection'),
    re_path(r'^admin/login/?$', legacy_admin_login, name='legacy_admin_login'),
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]
