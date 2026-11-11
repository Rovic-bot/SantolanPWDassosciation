from django.contrib import admin
from ewaf.reference_invalidation import ReferenceTransactions
from audit.admin import ReadOnlyAuditAdmin
from .models import MembershipEvent, MembershipSettings


@admin.register(MembershipSettings)
class MembershipSettingsAdmin(ReferenceTransactions, admin.ModelAdmin):
    fields = ('prpwd_url',)

    def has_add_permission(self, request):
        return not MembershipSettings.objects.exists() and super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MembershipEvent)
class MembershipEventAdmin(ReadOnlyAuditAdmin):
    list_display = ('occurred_at', 'application', 'actor_label', 'action', 'description')
    list_filter = ('action',)
    list_select_related = ('application',)

    def has_view_permission(self, request, obj=None):
        return (request.user.has_perm('membership.view_membershipapplication')
                and super().has_view_permission(request, obj))
