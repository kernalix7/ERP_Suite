from django.contrib import admin

from .models import (
    Contract, ContractMilestone, Document, DocumentApproval,
    DocumentCategory, DocumentVersion,
)


@admin.register(DocumentCategory)
class DocumentCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'retention_years', 'parent', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code']


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ['document_number', 'title', 'category', 'status', 'owner', 'access_level', 'is_active']
    list_filter = ['status', 'access_level', 'is_active']
    search_fields = ['document_number', 'title']


@admin.register(DocumentVersion)
class DocumentVersionAdmin(admin.ModelAdmin):
    list_display = ['document', 'version_number', 'created_at']
    list_filter = ['is_active']


@admin.register(DocumentApproval)
class DocumentApprovalAdmin(admin.ModelAdmin):
    list_display = ['document', 'approver', 'status', 'approved_at']
    list_filter = ['status']


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    list_display = ['contract_number', 'title', 'contract_type', 'partner', 'status', 'start_date', 'end_date', 'value']
    list_filter = ['status', 'contract_type', 'is_active']
    search_fields = ['contract_number', 'title']


@admin.register(ContractMilestone)
class ContractMilestoneAdmin(admin.ModelAdmin):
    list_display = ['contract', 'title', 'due_date', 'amount', 'status']
    list_filter = ['status']
