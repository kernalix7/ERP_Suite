from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import ServiceRequest, RepairRecord


class RepairRecordInline(admin.TabularInline):
    model = RepairRecord
    extra = 0


@admin.register(ServiceRequest)
class ServiceRequestAdmin(SimpleHistoryAdmin):
    list_display = ('request_number', 'customer', 'product', 'request_type', 'status', 'received_date', 'is_warranty')
    list_filter = ('status', 'request_type', 'is_warranty')
    search_fields = ('request_number', 'customer__name')
    inlines = [RepairRecordInline]


@admin.register(RepairRecord)
class RepairRecordAdmin(SimpleHistoryAdmin):
    list_display = ('service_request', 'repair_date', 'cost', 'technician')
