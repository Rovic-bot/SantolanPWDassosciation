from django.urls import path
from . import views

app_name = 'intake'
urlpatterns = [
    path('manage/program-intake/program/<uuid:pk>/policy/', views.source_policy, name='policy'),
    path('manage/program-intake/<uuid:reference>/sources/', views.source_review, name='sources'),
]
