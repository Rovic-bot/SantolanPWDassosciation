from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeDoneView
from django.urls import path, reverse_lazy

from .forms import StaffAuthenticationForm
from .views import StaffPasswordChangeView

app_name = 'accounts'
urlpatterns = [
    path('login/', LoginView.as_view(
        template_name='accounts/login.html', authentication_form=StaffAuthenticationForm), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('password/change/', StaffPasswordChangeView.as_view(
        template_name='accounts/password_change.html',
        success_url=reverse_lazy('accounts:password_change_done')), name='password_change'),
    path('password/changed/', PasswordChangeDoneView.as_view(
        template_name='accounts/password_change_done.html'), name='password_change_done'),
]
