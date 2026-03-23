from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Partner, Customer, CustomerPurchase, Order, OrderItem,
    Quotation, QuotationItem, Shipment,
    ShippingCarrier, ShipmentTracking,
)
from .commission import CommissionRate, CommissionRecord


@admin.register(Partner)
class PartnerAdmin(SimpleHistoryAdmin):
    list_display = (
        'code', 'name', 'partner_type', 'phone', 'contact_name',
    )
    list_filter = ('partner_type',)
    search_fields = ('name', 'code')


class CustomerPurchaseInline(admin.TabularInline):
    model = CustomerPurchase
    extra = 1


@admin.register(Customer)
class CustomerAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'phone', 'email')
    search_fields = ('name', 'phone')
    inlines = [CustomerPurchaseInline]


@admin.register(CustomerPurchase)
class CustomerPurchaseAdmin(SimpleHistoryAdmin):
    list_display = (
        'customer', 'product', 'serial_number',
        'purchase_date', 'warranty_end',
    )
    search_fields = ('customer__name', 'serial_number')
    list_filter = ('product',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = (
        'order_number', 'order_type', 'partner', 'customer',
        'assigned_to', 'order_date', 'status', 'total_amount',
    )
    list_filter = ('status', 'order_type')
    search_fields = ('order_number', 'partner__name', 'customer__name')
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
        'shipment_number', 'order', 'shipping_type', 'carrier',
        'tracking_number', 'status', 'shipped_date',
    )
    list_filter = ('status', 'shipping_type', 'carrier')
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


@admin.register(ShippingCarrier)
class ShippingCarrierAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'is_default')
    search_fields = ('code', 'name')


@admin.register(ShipmentTracking)
class ShipmentTrackingAdmin(SimpleHistoryAdmin):
    list_display = (
        'shipment', 'status', 'location', 'tracked_at',
    )
    list_filter = ('status',)
    search_fields = (
        'shipment__shipment_number',
    )
