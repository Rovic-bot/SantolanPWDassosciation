from django.urls import path, include
from program_intake import views as intake
from config.urls import urlpatterns as application_urls
from .views import explore
from .review_views import document_review

urlpatterns = [path('testing/', explore, name='testing_explore'),
    path('programs/<uuid:pk>/verify/', intake.verify),
    path('programs/<uuid:pk>/apply/', intake.apply),
    path('', include('program_intake.urls')),
    path('documents/<uuid:document_id>/verify/', document_review, name='testing_document_review'),
    *application_urls]
