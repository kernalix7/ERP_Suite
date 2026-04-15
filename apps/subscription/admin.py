from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    BillingRecord,
    Subscription,
    SubscriptionItem,
    SubscriptionPlan,
    UsageRecord,
)


class SubscriptionItemInline(admin.TabularInline):
    model = SubscriptionItem
    extra = 0


class BillingRecordInline(admin.TabularInline):
    model = BillingRecord
    extra = 0


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'code', 'billing_cycle', 'price', 'currency', 'is_active')
    list_filter = ('billing_cycle', 'is_active')
    search_fields = ('name', 'code')


@admin.register(Subscription)
class SubscriptionAdmin(SimpleHistoryAdmin):
    list_display = ('subscription_number', 'partner', 'plan', 'status',
                    'start_date', 'next_billing_date', 'auto_renew')
    list_filter = ('status', 'auto_renew')
    search_fields = ('subscription_number', 'partner__name')
    inlines = [SubscriptionItemInline, BillingRecordInline]


@admin.register(SubscriptionItem)
class SubscriptionItemAdmin(SimpleHistoryAdmin):
    list_display = ('subscription', 'product', 'quantity', 'unit_price')


@admin.register(BillingRecord)
class BillingRecordAdmin(SimpleHistoryAdmin):
    list_display = ('subscription', 'billing_date', 'amount', 'tax_amount',
                    'total', 'status')
    list_filter = ('status',)


@admin.register(UsageRecord)
class UsageRecordAdmin(SimpleHistoryAdmin):
    list_display = ('subscription', 'metric_name', 'quantity', 'recorded_date', 'billed')
    list_filter = ('billed',)
