from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Equipment, EquipmentDowntime, MaintenanceSchedule, MaintenanceWorkOrder, SparePart


@admin.register(Equipment)
class EquipmentAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'category', 'status', 'department', 'location')
    list_filter = ('status', 'category')
    search_fields = ('code', 'name', 'serial_number')


@admin.register(MaintenanceSchedule)
class MaintenanceScheduleAdmin(SimpleHistoryAdmin):
    list_display = ('equipment', 'title', 'maintenance_type', 'frequency_days', 'next_due', 'assigned_to')
    list_filter = ('maintenance_type',)
    raw_id_fields = ('equipment', 'assigned_to')


@admin.register(MaintenanceWorkOrder)
class MaintenanceWorkOrderAdmin(SimpleHistoryAdmin):
    list_display = ('wo_number', 'equipment', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority')
    search_fields = ('wo_number',)
    raw_id_fields = ('equipment', 'schedule', 'assigned_to')


@admin.register(SparePart)
class SparePartAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'current_stock', 'min_stock', 'unit_cost')
    search_fields = ('code', 'name')


@admin.register(EquipmentDowntime)
class EquipmentDowntimeAdmin(SimpleHistoryAdmin):
    list_display = ('equipment', 'start_time', 'end_time', 'reason')
    list_filter = ('equipment',)
    raw_id_fields = ('equipment', 'work_order')
