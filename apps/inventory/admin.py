from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Category, Product, Warehouse, StockMovement, StockTransfer


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
