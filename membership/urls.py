from django.urls import path
from . import views
from . import registration_views
from . import pdao_views
from . import pdao_registration_views
from . import pdao_membership_views
from . import approval_email_views

app_name = 'membership'
urlpatterns = [
    path('reviews/', pdao_registration_views.review_home, name='review_home'),
    path('registration/pdao/apply/', pdao_registration_views.apply, name='pdao_apply'),
    path('registration/pdao/receipt/', pdao_registration_views.receipt, name='pdao_receipt'),
    path('registration/pdao/receipt/form/', pdao_registration_views.receipt_form, name='pdao_receipt_form'),
    path('registration/pdao/finish/', pdao_registration_views.finish, name='pdao_finish'),
    path('reviews/pdao/', pdao_registration_views.inbox, name='pdao_inbox'),
    path('reviews/pdao/claim-notices/', pdao_registration_views.send_claim_notices, name='pdao_claim_notices'),
    path('registration/pdao/onsite/', pdao_registration_views.onsite, name='pdao_onsite'),
    path('reviews/pdao/<uuid:key>/', pdao_registration_views.detail, name='pdao_detail'),
    path('reviews/pdao/<uuid:key>/claim/', pdao_membership_views.claim_id, name='pdao_claim_id'),
    path('reviews/pdao/<uuid:key>/membership/', pdao_membership_views.membership, name='pdao_membership'),
    path('reviews/pdao/<uuid:key>/email/<uuid:email_id>/retry/', pdao_registration_views.retry_email, name='pdao_email_retry'),
    path('reviews/pdao/<uuid:key>/print/', pdao_registration_views.print_form, name='pdao_print'),
    path('registration/pdao/', pdao_views.prepare, name='pdao_prepare'),
    path('registration/forms/<slug:category>/', pdao_views.blank_form, name='blank_form'),
    path('registration/apply/', registration_views.apply, name='registration_apply'),
    path('registration/receipt/', registration_views.receipt, name='registration_receipt'),
    path('registration/finish/', registration_views.finish, name='registration_finish'),
    path('registrations/', registration_views.inbox, name='registration_inbox'),
    path('registrations/load/', registration_views.lookup, name='registration_lookup'),
    path('registrations/new/<slug:channel>/', registration_views.encode, name='registration_encode'),
    path('registrations/documents/<uuid:document_id>/', registration_views.document, name='registration_document'),
    path('registrations/<str:reference>/', registration_views.detail, name='registration_detail'),
    path('registrations/<str:reference>/email/<uuid:email_id>/retry/', approval_email_views.retry, name='approval_email_retry'),
    path('registrations/<str:reference>/pending-email/<uuid:email_id>/retry/', approval_email_views.retry_pending, name='pending_email_retry'),
    path('registrations/<str:reference>/correct/', registration_views.correct, name='registration_correct'),
    path('registrations/<str:reference>/onsite/', registration_views.onsite, name='registration_onsite'),
    path('registrations/<str:reference>/membership/', registration_views.prepare_membership, name='registration_handoff'),
    path('registrations/<str:reference>/form/<int:revision_number>/', registration_views.completed_form, name='registration_form'),
    path('applications/new/', views.encode, name='encode'),
    path('submitted/', views.submitted, name='submitted'),
    path('applications/', views.application_list, name='list'),
    path('applications/<uuid:reference>/', views.application_detail, name='detail'),
    path('documents/<uuid:document_id>/', views.download_document, name='document'),
]
