from django.contrib import admin
from ewaf.reference_invalidation import ReferenceTransactions
from .models import DocumentType, MembershipDocumentRequirement


@admin.register(DocumentType)
class DocumentTypeAdmin(ReferenceTransactions, admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MembershipDocumentRequirement)
class MembershipDocumentRequirementAdmin(ReferenceTransactions, admin.ModelAdmin):
    list_display = ('document_type', 'is_active', 'is_required', 'position')
    list_filter = ('is_active', 'is_required')

    def has_delete_permission(self, request, obj=None):
        return False
