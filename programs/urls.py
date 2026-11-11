from django.urls import path
from . import views, photo_views, approval_views, binding_views, proposals, tracking_views, application_workflow_views, information_confirmation_views
from . import decision_email_views
from . import picture_views

app_name = 'programs'
urlpatterns = [
    path('<uuid:pk>/picture/', picture_views.public, name='public_picture'),
    path('tracking/', tracking_views.verify, name='tracking'),
    path('manage/information/<uuid:reference>/', information_confirmation_views.review, name='information_review'),
    path('tracking/progress/', tracking_views.progress, name='tracking_progress'),
    path('tracking/finish/', tracking_views.finish, name='tracking_finish'),
    path('tracking/receipt-qr/<uuid:pk>/', tracking_views.receipt_qr, name='tracking_receipt_qr'),
    path('photos/', photo_views.queue, name='photo_queue'),
    path('photos/<uuid:reference>/', photo_views.review, name='photo_review'),
    path('photos/<uuid:reference>/<uuid:photo_id>/', photo_views.photo, name='photo'),
    path('corrections/<uuid:reference>/', photo_views.correction, name='correction'),
    path('status/<str:token>/', views.application_status, name='status'),
    path('status/<str:token>/qr.png', views.application_qr, name='qr'),
    path('', views.public_list, name='list'),
    path('manage/', views.manage_list, name='manage_list'),
    path('manage/new/', views.edit, name='create'),
    path('manage/pdao-readiness/', binding_views.readiness, name='pdao_readiness'),
    path('manage/<uuid:pk>/terms/', binding_views.terms_review, name='terms_review'),
    path('manage/<uuid:pk>/terms/<int:revision_id>/', binding_views.revision_detail, name='terms_revision'),
    path('manage/<uuid:pk>/pdao/', approval_views.approval_history, name='pdao_history'),
    path('manage/<uuid:pk>/', views.manage_detail, name='manage_detail'),
    path('manage/<uuid:pk>/edit/', views.edit, name='edit'),
    path('manage/<uuid:pk>/picture/', picture_views.preview, name='picture'),
    path('manage/<uuid:pk>/proposal.pdf', proposals.proposal, name='proposal'),
    path('manage/<uuid:pk>/requirements/new/', views.requirement_edit, name='requirement_add'),
    path('manage/<uuid:pk>/requirements/<int:requirement_id>/', views.requirement_edit, name='requirement_edit'),
    path('manage/<uuid:pk>/applications/', views.applications, name='applications'),
    path('manage/<uuid:pk>/applications/<uuid:reference>/', views.application_detail, name='application_detail'),
    path('manage/<uuid:pk>/applications/<uuid:reference>/emails/<uuid:email_id>/retry/', decision_email_views.retry, name='decision_email_retry'),
    path('manage/<uuid:pk>/applications/<uuid:reference>/documents/<uuid:document_id>/', views.download_document, name='document'),
    path('manage/<uuid:pk>/applications/<uuid:reference>/documents/<uuid:document_id>/revisions/<int:revision_id>/', views.download_document, name='document_revision'),
    path('<uuid:pk>/', views.public_detail, name='detail'),
    path('<uuid:pk>/verify/', application_workflow_views.verify, name='verify'),
    path('<uuid:pk>/apply/', application_workflow_views.apply, name='apply'),
    path('<uuid:pk>/submitted/', views.submitted, name='submitted'),
]
