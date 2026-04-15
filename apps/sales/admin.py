from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Customer,
    CustomerPurchase,
    CustomerSatisfaction,
    CustomerTier,
    LeadActivity,
    Order,
    OrderItem,
    Partner,
    PriceRule,
    Quotation,
    QuotationItem,
    SalesLead,
    SalesTarget,
    Shipment,
    ShipmentItem,
    ShipmentTracking,
    ShippingCarrier,
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


@admin.register(ShipmentItem)
class ShipmentItemAdmin(SimpleHistoryAdmin):
    list_display = ('shipment', 'order_item', 'quantity', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('shipment__shipment_number', 'order_item__product__name')


@admin.register(ShipmentTracking)
class ShipmentTrackingAdmin(SimpleHistoryAdmin):
    list_display = (
        'shipment', 'status', 'location', 'tracked_at',
    )
    list_filter = ('status',)
    search_fields = (
        'shipment__shipment_number',
    )


@admin.register(PriceRule)
class PriceRuleAdmin(SimpleHistoryAdmin):
    list_display = ('product', 'partner', 'min_quantity', 'unit_price', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('product__name', 'partner__name')


@admin.register(CustomerTier)
class CustomerTierAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'code', 'discount_rate', 'min_annual_purchase', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')


@admin.register(SalesTarget)
class SalesTargetAdmin(SimpleHistoryAdmin):
    list_display = ('salesperson', 'year', 'quarter', 'target_amount', 'is_active')
    list_filter = ('year', 'quarter', 'is_active')
    search_fields = ('salesperson__username',)


class LeadActivityInline(admin.TabularInline):
    model = LeadActivity
    extra = 0


@admin.register(SalesLead)
class SalesLeadAdmin(SimpleHistoryAdmin):
    list_display = ('lead_number', 'company_name', 'contact_name', 'status',
                    'assigned_to', 'expected_amount', 'is_active')
    list_filter = ('status', 'source', 'is_active')
    search_fields = ('lead_number', 'company_name', 'contact_name')
    inlines = [LeadActivityInline]


@admin.register(LeadActivity)
class LeadActivityAdmin(SimpleHistoryAdmin):
    list_display = ('lead', 'activity_type', 'activity_date', 'is_active')
    list_filter = ('activity_type', 'is_active')
    search_fields = ('lead__lead_number', 'lead__company_name')


@admin.register(CustomerSatisfaction)
class CustomerSatisfactionAdmin(SimpleHistoryAdmin):
    list_display = ('partner', 'order', 'score', 'survey_date', 'is_active')
    list_filter = ('score', 'is_active')
    search_fields = ('partner__name',)
