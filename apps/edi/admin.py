from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    EDIDocumentType,
    EDIMapping,
    EDIPartner,
    EDISchedule,
    EDITransaction,
)


class EDIMappingInline(admin.TabularInline):
    model = EDIMapping
    extra = 0


@admin.register(EDIPartner)
class EDIPartnerAdmin(SimpleHistoryAdmin):
    list_display = ('partner', 'edi_id', 'protocol', 'is_active')
    list_filter = ('protocol', 'is_active')
    search_fields = ('edi_id', 'partner__name')


@admin.register(EDIDocumentType)
class EDIDocumentTypeAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'direction', 'format', 'is_active')
    list_filter = ('direction', 'format')
    inlines = [EDIMappingInline]


@admin.register(EDITransaction)
class EDITransactionAdmin(SimpleHistoryAdmin):
    list_display = ('transaction_id', 'partner', 'document_type', 'direction',
                    'status', 'created_at', 'processed_at')
    list_filter = ('status', 'direction')
    search_fields = ('transaction_id',)


@admin.register(EDIMapping)
class EDIMappingAdmin(SimpleHistoryAdmin):
    list_display = ('document_type', 'source_field', 'target_model', 'target_field')


@admin.register(EDISchedule)
class EDIScheduleAdmin(SimpleHistoryAdmin):
    list_display = ('partner', 'document_type', 'frequency', 'last_run', 'next_run',
                    'is_active')
    list_filter = ('frequency', 'is_active')
