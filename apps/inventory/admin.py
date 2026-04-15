from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Category, Product, Warehouse, StockMovement, StockTransfer, StockLot,
    StockCount, StockCountItem, WarehouseStock, SerialNumber,
)


@admin.register(Category)
class CategoryAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'parent', 'is_active')
    list_filter = ('is_active',)


@admin.register(Product)
class ProductAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'product_type', 'unit_price', 'current_stock', 'safety_stock', 'is_active')
    list_filter = ('product_type', 'category', 'is_active')
    search_fields = ('code', 'name')


@admin.register(Warehouse)
class WarehouseAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'location', 'is_active')


@admin.register(StockMovement)
class StockMovementAdmin(SimpleHistoryAdmin):
    list_display = ('movement_number', 'movement_type', 'product', 'warehouse', 'quantity', 'movement_date')
    list_filter = ('movement_type', 'warehouse', 'movement_date')
    search_fields = ('movement_number', 'product__name')


@admin.register(StockTransfer)
class StockTransferAdmin(SimpleHistoryAdmin):
    list_display = ('transfer_number', 'product', 'from_warehouse', 'to_warehouse', 'quantity', 'transfer_date')
    list_filter = ('from_warehouse', 'to_warehouse')


@admin.register(StockLot)
class StockLotAdmin(SimpleHistoryAdmin):
    list_display = (
        'lot_number', 'product', 'warehouse',
        'initial_quantity', 'remaining_quantity',
        'unit_cost', 'received_date', 'expiry_date',
    )
    list_filter = ('warehouse', 'received_date', 'is_active')
    search_fields = ('lot_number', 'product__name', 'product__code')
    raw_id_fields = ('product', 'warehouse', 'stock_movement')


class StockCountItemInline(admin.TabularInline):
    model = StockCountItem
    extra = 0


@admin.register(StockCount)
class StockCountAdmin(SimpleHistoryAdmin):
    list_display = ('count_number', 'warehouse', 'count_date', 'status', 'is_active')
    list_filter = ('status', 'is_active')
    search_fields = ('count_number',)
    inlines = [StockCountItemInline]


@admin.register(StockCountItem)
class StockCountItemAdmin(SimpleHistoryAdmin):
    list_display = ('stock_count', 'product', 'system_quantity', 'actual_quantity', 'difference', 'adjusted')
    list_filter = ('adjusted', 'is_active')
    search_fields = ('product__name', 'product__code')
    raw_id_fields = ('stock_count', 'product')


@admin.register(WarehouseStock)
class WarehouseStockAdmin(SimpleHistoryAdmin):
    list_display = ('warehouse', 'product', 'quantity', 'is_active')
    list_filter = ('warehouse', 'is_active')
    search_fields = ('product__name', 'product__code')
    raw_id_fields = ('warehouse', 'product')


@admin.register(SerialNumber)
class SerialNumberAdmin(SimpleHistoryAdmin):
    list_display = ('serial', 'product', 'status', 'warehouse', 'production_date', 'is_active')
    list_filter = ('status', 'is_active')
    search_fields = ('serial', 'product__name', 'product__code')
    raw_id_fields = ('product', 'warehouse', 'production_record')
