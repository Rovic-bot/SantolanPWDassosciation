from django.core.exceptions import PermissionDenied


def require_workspace_permissions(user, *permissions):
    if not (user.is_authenticated and user.is_active and user.is_staff
            and user.has_perms(['accounts.access_dashboard', *permissions])):
        raise PermissionDenied
