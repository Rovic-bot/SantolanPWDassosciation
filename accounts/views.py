from urllib.parse import urlencode

from django.contrib.auth.views import PasswordChangeView
from django.contrib.auth.models import User
from django.contrib.auth import update_session_auth_hash
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from audit.models import SecurityEvent
from audit.signals import record_event
from .authority_services import protect_request, enlisted


@never_cache
@csrf_protect
@require_http_methods(['GET', 'HEAD', 'POST'])
def legacy_admin_login(request):
    """Use the main staff sign-in screen and its Dashboard destination."""
    query = urlencode({'next': reverse('core:dashboard')}, safe='/')
    return HttpResponseRedirect(f"{reverse('accounts:login')}?{query}")


@method_decorator(never_cache, name='dispatch')
class StaffPasswordChangeView(PasswordChangeView):
    def post(self, request, *args, **kwargs):
        # Acquire the fence before constructing/validating the password form.
        # Password and SecurityEvent commit with invalidation; rotate the session
        # only after that successful commit, matching Django's own-session rule.
        with protect_request(request, User, own_password=True, credential=True):
            response = super().post(request, *args, **kwargs)
        if hasattr(self, '_authority_password_user'):
            update_session_auth_hash(request, self._authority_password_user)
        return response

    def form_valid(self, form):
        if enlisted():
            user = form.save()
            record_event(self.request, SecurityEvent.Action.PASSWORD_CHANGED, user)
            self._authority_password_user = user
            return HttpResponseRedirect(self.get_success_url())
        response = super().form_valid(form)
        record_event(self.request, SecurityEvent.Action.PASSWORD_CHANGED, self.request.user)
        return response
