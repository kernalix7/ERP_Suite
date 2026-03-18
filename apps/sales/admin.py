from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Partner, Customer, Order, OrderItem,
    Quotation, QuotationItem, Shipment,
)
from .commission import CommissionRate, CommissionRecord


@admin.register(Partner)
class PartnerAdmin(SimpleHistoryAdmin):
    list_display = (
        'code', 'name', 'partner_type', 'phone', 'contact_name',
    )
    list_filter = ('partner_type',)
    search_fields = ('name', 'code')


@admin.register(Customer)
class CustomerAdmin(SimpleHistoryAdmin):
    list_display = (
        'name', 'phone', 'product',
        'serial_number', 'warranty_end',
    )
    search_fields = ('name', 'phone', 'serial_number')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = (
        'order_number', 'partner', 'customer',
        'order_date', 'status', 'total_amount',
    )
    list_filter = ('status',)
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(SimpleHistoryAdmin):
    list_display = (
        'order', 'product', 'quantity',
        'unit_price', 'amount', 'tax_amount',
    )
    list_filter = ('order__status',)
    search_fields = ('product__name', 'order__order_number')


class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1


@admin.register(Quotation)
class QuotationAdmin(SimpleHistoryAdmin):
    list_display = (
        'quote_number', 'partner', 'customer',
        'quote_date', 'status', 'total_amount',
    )
    list_filter = ('status',)
    inlines = [QuotationItemInline]


@admin.register(QuotationItem)
class QuotationItemAdmin(SimpleHistoryAdmin):
    list_display = (
        'quotation', 'product', 'quantity',
        'unit_price', 'amount', 'tax_amount',
    )
    search_fields = (
        'product__name', 'quotation__quote_number',
    )


@admin.register(Shipment)
class ShipmentAdmin(SimpleHistoryAdmin):
    list_display = (
        'shipment_number', 'order', 'carrier',
        'tracking_number', 'status', 'shipped_date',
    )
    list_filter = ('status', 'carrier')
    search_fields = (
        'shipment_number', 'tracking_number',
        'order__order_number',
    )


@admin.register(CommissionRate)
class CommissionRateAdmin(SimpleHistoryAdmin):
    list_display = ('partner', 'product', 'rate')


@admin.register(CommissionRecord)
class CommissionRecordAdmin(SimpleHistoryAdmin):
    list_display = (
        'partner', 'order', 'commission_amount',
        'status', 'settled_date',
    )
    list_filter = ('status',)
