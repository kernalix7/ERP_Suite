from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    AdPlatform, AdCampaign, AdCreative,
    AdPerformance, AdBudget,
)


@admin.register(AdPlatform)
class AdPlatformAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'platform_type', 'is_connected')
    list_filter = ('platform_type', 'is_connected')


@admin.register(AdCampaign)
class AdCampaignAdmin(SimpleHistoryAdmin):
    list_display = (
        'name', 'platform', 'campaign_type',
        'status', 'budget', 'spent',
    )
    list_filter = ('status', 'campaign_type', 'platform')


@admin.register(AdCreative)
class AdCreativeAdmin(SimpleHistoryAdmin):
    list_display = (
        'name', 'campaign', 'creative_type', 'status',
    )
    list_filter = ('creative_type', 'status')


@admin.register(AdPerformance)
class AdPerformanceAdmin(SimpleHistoryAdmin):
    list_display = (
        'campaign', 'date', 'impressions',
        'clicks', 'conversions', 'cost', 'revenue',
    )
    list_filter = ('date', 'campaign')
    date_hierarchy = 'date'


@admin.register(AdBudget)
class AdBudgetAdmin(SimpleHistoryAdmin):
    list_display = (
        'year', 'month', 'platform',
        'planned_budget', 'actual_spent',
    )
    list_filter = ('year', 'platform')
