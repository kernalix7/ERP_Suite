from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Partner, Customer, Order, OrderItem
from .commission import CommissionRate, CommissionRecord


@admin.register(Partner)
class PartnerAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'partner_type', 'phone', 'contact_name')
    list_filter = ('partner_type',)
    search_fields = ('name', 'code')


@admin.register(Customer)
class CustomerAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'phone', 'product', 'serial_number', 'warranty_end')
    search_fields = ('name', 'phone', 'serial_number')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1


@admin.register(Order)
class OrderAdmin(SimpleHistoryAdmin):
    list_display = ('order_number', 'partner', 'customer', 'order_date', 'status', 'total_amount')
    list_filter = ('status',)
    inlines = [OrderItemInline]


@admin.register(CommissionRate)
class CommissionRateAdmin(SimpleHistoryAdmin):
    list_display = ('partner', 'product', 'rate')


@admin.register(CommissionRecord)
class CommissionRecordAdmin(SimpleHistoryAdmin):
    list_display = ('partner', 'order', 'commission_amount', 'status', 'settled_date')
    list_filter = ('status',)
