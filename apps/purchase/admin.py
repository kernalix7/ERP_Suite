from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem,
    RFQ, RFQItem, RFQResponse, VendorScore,
)


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


class RFQItemInline(admin.TabularInline):
    model = RFQItem
    extra = 1


@admin.register(RFQ)
class RFQAdmin(SimpleHistoryAdmin):
    list_display = ('rfq_number', 'title', 'status', 'requested_by', 'due_date', 'is_active')
    list_filter = ('status', 'is_active')
    search_fields = ('rfq_number', 'title')
    inlines = [RFQItemInline]


@admin.register(RFQItem)
class RFQItemAdmin(SimpleHistoryAdmin):
    list_display = ('rfq', 'product', 'quantity', 'is_active')
    search_fields = ('rfq__rfq_number', 'product__name')
    raw_id_fields = ('rfq', 'product')


@admin.register(RFQResponse)
class RFQResponseAdmin(SimpleHistoryAdmin):
    list_display = ('rfq', 'partner', 'response_date', 'total_amount', 'delivery_days', 'is_selected')
    list_filter = ('is_selected', 'is_active')
    search_fields = ('rfq__rfq_number', 'partner__name')
    raw_id_fields = ('rfq', 'partner')


@admin.register(VendorScore)
class VendorScoreAdmin(SimpleHistoryAdmin):
    list_display = ('partner', 'evaluation_date', 'delivery_score', 'quality_score', 'price_score', 'service_score', 'overall_score')
    list_filter = ('evaluation_date', 'is_active')
    search_fields = ('partner__name', 'partner__code')
    raw_id_fields = ('partner', 'evaluator')
