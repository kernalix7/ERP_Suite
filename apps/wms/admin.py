from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import BinLocation, PickOrder, PickOrderItem, PutAwayTask, WarehouseZone, WavePlan


@admin.register(WarehouseZone)
class WarehouseZoneAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'warehouse', 'zone_type', 'is_active')
    list_filter = ('zone_type', 'warehouse')
    search_fields = ('code', 'name')


@admin.register(BinLocation)
class BinLocationAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'zone', 'row', 'column', 'level', 'is_occupied')
    list_filter = ('is_occupied', 'zone')
    search_fields = ('code',)


@admin.register(PickOrder)
class PickOrderAdmin(SimpleHistoryAdmin):
    list_display = ('pick_number', 'order', 'status', 'priority', 'assigned_to', 'created_at')
    list_filter = ('status', 'priority')
    search_fields = ('pick_number',)
    raw_id_fields = ('order', 'assigned_to')


@admin.register(PickOrderItem)
class PickOrderItemAdmin(SimpleHistoryAdmin):
    list_display = ('pick_order', 'product', 'bin_location', 'quantity', 'picked_qty')
    raw_id_fields = ('pick_order', 'product', 'bin_location')


@admin.register(PutAwayTask)
class PutAwayTaskAdmin(SimpleHistoryAdmin):
    list_display = ('pk', 'product', 'quantity', 'status', 'suggested_bin', 'actual_bin')
    list_filter = ('status',)
    raw_id_fields = ('goods_receipt', 'product', 'suggested_bin', 'actual_bin', 'assigned_to')


@admin.register(WavePlan)
class WavePlanAdmin(SimpleHistoryAdmin):
    list_display = ('wave_number', 'name', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('wave_number', 'name')
