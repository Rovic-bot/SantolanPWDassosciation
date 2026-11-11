from django.urls import path
from . import views

app_name = 'events'
urlpatterns = [
    path('manage/', views.manage_list, name='manage_list'),
    path('manage/observances/', views.observances, name='observances'),
    path('manage/observances/new/', views.observance_edit, name='observance_create'),
    path('manage/observances/<uuid:pk>/', views.observance_detail, name='observance_detail'),
    path('manage/observances/<uuid:pk>/edit/', views.observance_edit, name='observance_edit'),
    path('manage/observances/<uuid:pk>/image/', views.observance_preview_image, name='observance_preview_image'),
    path('manage/observances/<uuid:pk>/history/<uuid:revision_id>/image/', views.observance_revision_image, name='observance_revision_image'),
    path('observances/<uuid:pk>/image/', views.observance_image, name='observance_image'),
    path('observances/<uuid:pk>/', views.observance_public_detail, name='observance_public_detail'),
    path('manage/new/', views.edit, name='create'),
    path('manage/<uuid:pk>/', views.manage_detail, name='manage_detail'),
    path('manage/<uuid:pk>/edit/', views.edit, name='edit'),
    path('manage/<uuid:pk>/image/', views.preview_image, name='preview_image'),
    path('manage/<uuid:pk>/attendance/', views.attendance_list, name='attendance_list'),
    path('manage/<uuid:pk>/attendance/new/', views.attendance_detail, name='attendance_create'),
    path('manage/<uuid:pk>/attendance/<uuid:reference>/', views.attendance_detail, name='attendance_detail'),
    path('manage/<uuid:pk>/registrations/', views.registrations, name='registrations'),
    path('manage/<uuid:pk>/registrations/<uuid:reference>/', views.registration_detail, name='registration_detail'),
    path('<uuid:pk>/', views.public_detail, name='detail'),
    path('<uuid:pk>/image/', views.public_image, name='image'),
    path('<uuid:pk>/register/', views.register, name='register'),
    path('<uuid:pk>/registered/', views.registered, name='registered'),
]
