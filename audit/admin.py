from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.utils.html import format_html
from django.utils import timezone
from django.urls import path

from .models import SecurityEvent
from .admin_presentation import AuditDateFilter, AuditListPresentation


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SecurityEvent)
class SecurityEventAdmin(AuditListPresentation, ReadOnlyAuditAdmin):
    list_display = ('user', 'address', 'timestamp', 'device', 'status_badge')
    list_display_links = ('user', 'timestamp')
    list_filter = ('action', 'user', AuditDateFilter)
    list_select_related = ('user',)
    search_fields = ('user__username', 'address')
    audit_date_field = 'occurred_at'

    @admin.display(description='Timestamp', ordering='occurred_at')
    def timestamp(self, obj):
        return timezone.localtime(obj.occurred_at).strftime('%Y-%m-%d %H:%M:%S')

    @admin.display(description='Device / user agent')
    def device(self, obj):
        return 'Not recorded'

    @admin.display(description='Status', ordering='action')
    def status_badge(self, obj):
        label = 'Successful' if obj.action == SecurityEvent.Action.LOGIN else obj.get_action_display()
        return format_html('<span class="directory-badge" data-state="{}">{}</span>', obj.action, label)


@admin.register(LogEntry)
class AdministrationLogAdmin(AuditListPresentation, ReadOnlyAuditAdmin):
    list_display = ('timestamp', 'user', 'action_badge', 'object_repr', 'details')
    list_filter = ('action_flag', 'content_type', 'user', AuditDateFilter)
    list_select_related = ('user', 'content_type')
    search_fields = ('object_repr', 'user__username', 'change_message')
    audit_date_field = 'action_time'

    def changelist_view(self, request, extra_context=None):
        from .activity_views import activity_list
        return activity_list(request, self)

    def get_urls(self):
        return [path('activity/<slug:source>/<str:pk>/',
                     self.admin_site.admin_view(self.activity_detail),
                     name='administration_activity')] + super().get_urls()

    def activity_detail(self, request, source, pk):
        from .activity_views import activity_detail
        return activity_detail(request, self, source, pk)

    @admin.display(description='Action time', ordering='action_time')
    def timestamp(self, obj):
        return timezone.localtime(obj.action_time).strftime('%Y-%m-%d %H:%M:%S')

    @admin.display(description='Action type', ordering='action_flag')
    def action_badge(self, obj):
        return format_html('<span class="directory-badge" data-state="action-{}">{}</span>',
            obj.action_flag, obj.get_action_flag_display())

    @admin.display(description='Details')
    def details(self, obj):
        message = obj.get_change_message()
        return format_html('<span class="directory-detail-text" title="{}">{}</span>', message, message)
