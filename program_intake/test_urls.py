from django.urls import include, path
from config.urls import urlpatterns as application_urls
from . import views

urlpatterns = [path('programs/<uuid:pk>/verify/', views.verify),
    path('programs/<uuid:pk>/apply/', views.apply), path('', include('program_intake.urls')), *application_urls]
