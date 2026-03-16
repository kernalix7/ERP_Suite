from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import MarketplaceConfig, MarketplaceOrder, SyncLog


@admin.register(MarketplaceConfig)
class MarketplaceConfigAdmin(SimpleHistoryAdmin):
    list_display = ('shop_name', 'is_active')


@admin.register(MarketplaceOrder)
class MarketplaceOrderAdmin(SimpleHistoryAdmin):
    list_display = ('store_order_id', 'product_name', 'buyer_name', 'quantity', 'price', 'status', 'ordered_at')
    list_filter = ('status', 'ordered_at')
    search_fields = ('store_order_id', 'product_name', 'buyer_name')


@admin.register(SyncLog)
class SyncLogAdmin(SimpleHistoryAdmin):
    list_display = ('direction', 'started_at', 'completed_at', 'total_count', 'success_count', 'error_count')
    list_filter = ('direction', 'started_at')
