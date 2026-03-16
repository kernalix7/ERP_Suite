from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(SimpleHistoryAdmin):
    list_display = ('po_number', 'partner', 'order_date', 'status', 'total_amount', 'grand_total')
    list_filter = ('status',)
    search_fields = ('po_number', 'partner__name')
    inlines = [PurchaseOrderItemInline]


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(SimpleHistoryAdmin):
    list_display = ('purchase_order', 'product', 'quantity', 'unit_price', 'amount', 'received_quantity')
    search_fields = ('purchase_order__po_number', 'product__name')


class GoodsReceiptItemInline(admin.TabularInline):
    model = GoodsReceiptItem
    extra = 1


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(SimpleHistoryAdmin):
    list_display = ('receipt_number', 'purchase_order', 'receipt_date')
    search_fields = ('receipt_number', 'purchase_order__po_number')
    inlines = [GoodsReceiptItemInline]


@admin.register(GoodsReceiptItem)
class GoodsReceiptItemAdmin(SimpleHistoryAdmin):
    list_display = ('goods_receipt', 'po_item', 'received_quantity', 'is_inspected')
