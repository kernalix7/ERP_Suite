from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import AuditFinding, CAPA, InternalAudit, ISODocument, NonConformance


@admin.register(NonConformance)
class NonConformanceAdmin(SimpleHistoryAdmin):
    list_display = ('nc_number', 'title', 'source', 'severity', 'status', 'created_at')
    list_filter = ('status', 'severity', 'source')
    search_fields = ('nc_number', 'title')
    raw_id_fields = ('product', 'detected_by')


@admin.register(CAPA)
class CAPAAdmin(SimpleHistoryAdmin):
    list_display = ('capa_number', 'type', 'status', 'assigned_to', 'due_date')
    list_filter = ('status', 'type')
    search_fields = ('capa_number',)
    raw_id_fields = ('nc', 'assigned_to')


@admin.register(InternalAudit)
class InternalAuditAdmin(SimpleHistoryAdmin):
    list_display = ('audit_number', 'title', 'audit_type', 'status', 'audit_date', 'auditor')
    list_filter = ('status', 'audit_type')
    search_fields = ('audit_number', 'title')
    raw_id_fields = ('auditor',)


@admin.register(AuditFinding)
class AuditFindingAdmin(SimpleHistoryAdmin):
    list_display = ('audit', 'finding_type', 'description')
    list_filter = ('finding_type',)
    raw_id_fields = ('audit', 'capa')


@admin.register(ISODocument)
class ISODocumentAdmin(SimpleHistoryAdmin):
    list_display = ('document_number', 'title', 'category', 'revision', 'status', 'effective_date')
    list_filter = ('status', 'category')
    search_fields = ('document_number', 'title')
