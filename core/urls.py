from django.urls import path
from . import views, content, workspace, resources, portal_editor
from membership.views import register
from announcements.views import public_list
from announcements.public_results import result_detail
from events.views import public_list as event_list
from programs.views import public_list as program_list

app_name = 'core'
urlpatterns = [
    path('resources/', resources.index, name='resources'),
    path('resources/<slug:key>/', resources.detail, name='resource_detail'),
    path('', views.home, name='home'),
    path('about/', views.public_page, {'page': 'about'}, name='about'),
    path('announcements/', public_list, name='announcements'),
    path('events/', event_list, name='events'),
    path('programs/', program_list, name='programs'),
    path('results/<uuid:pk>/', result_detail, name='result_detail'),
    path('membership/register/', register, name='membership'),
    path('contact/', views.public_page, {'page': 'contact'}, name='contact'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('workspace/applications/', workspace.application_programs, name='application_programs'),
    path('information/applications/', views.public_page, {'page': 'application-information'}, name='application_information'),
    path('information/privacy/', views.public_page, {'page': 'privacy'}, name='privacy'),
    path('information/accessibility/', views.public_page, {'page': 'accessibility'}, name='accessibility'),
    path('information/ewaf/', views.public_page, {'page': 'ewaf'}, name='ewaf_information'),
    path('information/faq/', views.public_page, {'page': 'faq'}, name='faq'),
    path('content/', content.content_list, name='content_list'),
    path('content/portal/<slug:key>/state/', portal_editor.editor_state, name='portal_state'),
    path('content/portal/<slug:key>/preview/', portal_editor.preview, name='portal_preview'),
    path('content/portal/<slug:key>/save/', portal_editor.save, name='portal_save'),
    path('portal-artwork/<slug:key>/<slug:field>/<slug:token>/', portal_editor.image, name='portal_image'),
    path('content/<slug:key>/', content.content_edit, name='content_edit'),
]
