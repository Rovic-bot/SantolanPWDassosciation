from django.contrib import admin
from ewaf.reference_invalidation import ReferenceTransactions
from .models import DisabilityType


@admin.register(DisabilityType)
class DisabilityTypeAdmin(ReferenceTransactions, admin.ModelAdmin):
    list_display = ('name', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)

    def has_delete_permission(self, request, obj=None):
        return False
