from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def dashboard_required(view):
    @login_required
    @wraps(view)
    def guarded(request, *args, **kwargs):
        if not (request.user.is_active and request.user.is_staff
                and request.user.has_perm('accounts.access_dashboard')):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return guarded
