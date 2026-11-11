from django.contrib import admin, messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.debug import sensitive_post_parameters

from .authority_services import protect_request, enlisted


class AuthorityTransactions:
    """Outer request boundary includes inherited transactions, M2M and logging."""

    def add_view(self, request, *args, **kwargs):
        with protect_request(request, self.model):
            return super().add_view(request, *args, **kwargs)

    def changeform_view(self, request, *args, **kwargs):
        with protect_request(request, self.model):
            return super().changeform_view(request, *args, **kwargs)

    def delete_view(self, request, *args, **kwargs):
        with protect_request(request, self.model):
            return super().delete_view(request, *args, **kwargs)

    def changelist_view(self, request, *args, **kwargs):
        if request.method == 'POST' and enlisted() and request.POST.get('action', '') not in ('', 'delete_selected'):
            raise ValidationError('AUTHORITY_ADMIN_ACTION_NOT_INTEGRATED')
        with protect_request(request, self.model):
            return super().changelist_view(request, *args, **kwargs)


class SuperuserManagement:
    """Granting auth.change_user/group must never enable privilege escalation."""

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    has_add_permission = has_view_permission
    has_change_permission = has_view_permission
    has_delete_permission = has_view_permission


admin.site.unregister(User)
admin.site.unregister(Group)


@admin.register(User)
class AdministratorAdmin(AuthorityTransactions, SuperuserManagement, UserAdmin):
    @method_decorator(sensitive_post_parameters())
    def user_change_password(self, request, id, form_url=''):
        if request.method != 'POST' or not enlisted():
            return super().user_change_password(request, id, form_url)
        # Match installed Django 5.2 UserAdmin validation, logging and response.
        # Defer session rotation and success messaging until the DB commit.
        with protect_request(request, self.model, credential=True):
            user = self.get_object(request, unquote(id))
            if not self.has_change_permission(request, user):
                raise PermissionDenied
            if user is None:
                raise Http404
            form = self.change_password_form(user, request.POST)
            if not form.is_valid() or not (form.cleaned_data['set_usable_password'] or 'unset-password' in request.POST):
                return super().user_change_password(request, id, form_url)
            user = form.save()
            self.log_change(request, user, self.construct_change_message(request, form, None))
        messages.success(request, _('Password changed successfully.') if user.has_usable_password()
                         else _('Password-based authentication was disabled.'))
        update_session_auth_hash(request, user)
        return HttpResponseRedirect(reverse(f'{self.admin_site.name}:auth_user_change', args=(user.pk,)))

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        field = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name == 'groups':
            field.label = 'Roles (groups)'
        return field


@admin.register(Group)
class RoleAdmin(AuthorityTransactions, SuperuserManagement, GroupAdmin):
    search_fields = ('name', 'permissions__name', 'permissions__codename')
