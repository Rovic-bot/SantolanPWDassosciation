from django.urls import path
from django.views.generic.base import RedirectView
from . import views, certificate_views

app_name = 'announcements'
urlpatterns = [
    path('manage/', views.manage_list, name='manage_list'),
    path('manage/notices/', RedirectView.as_view(pattern_name='announcements:manage_list'), name='manage_notices'),
    path('manage/new/', views.edit, name='create'),
    path('manage/recipients/', views.prepare_result_draft, {'recipients': True}, name='choose_recipients'),
    path('manage/recipients/<uuid:program_id>/', views.prepare_result_draft, {'recipients': True}, name='prepare_recipients'),
    path('manage/results/', views.prepare_result_draft, name='choose_results'),
    path('manage/results/<uuid:program_id>/', views.prepare_result_draft, name='prepare_results'),
    path('manage/results/<uuid:program_id>/certificates/retry/', certificate_views.retry, name='certificate_retry'),
    path('manage/certificates/<uuid:pk>/', certificate_views.download, name='certificate_download'),
    path('manage/<uuid:pk>/', views.manage_detail, name='manage_detail'),
    path('manage/<uuid:pk>/edit/', views.edit, name='edit'),
    path('manage/<uuid:pk>/image/', views.preview_image, name='preview_image'),
    path('<uuid:pk>/', views.public_detail, name='detail'),
    path('<uuid:pk>/image/', views.public_image, name='image'),
]
