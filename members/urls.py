from django.urls import path
from . import views, review_views, document_views, update_views

app_name = 'members'
urlpatterns = [
    path('update/', update_views.start, name='update_start'),
    path('update/code/', update_views.code, name='update_code'),
    path('update/information/', update_views.information, name='update_information'),
    path('update/finish/', update_views.finish, name='update_finish'),
    path('updates/<uuid:pk>/', update_views.review, name='update_review'),
    path('reviews/<uuid:pk>/', review_views.review_detail, name='review_detail'),
    path('<int:pk>/reviews/', review_views.reviews, name='reviews'),
    path('', views.member_list, name='list'),
    path('<int:pk>/', views.member_detail, name='detail'),
    path('<int:pk>/registration/print/', views.registration_print, name='registration_print'),
    path('<int:pk>/edit/', views.member_edit, name='edit'),
    path('<int:pk>/documents/<uuid:document_id>/', views.download_document, name='document'),
    path('<int:pk>/uploaded-documents/<uuid:document_id>/', document_views.uploaded_document, name='uploaded_document'),
]
