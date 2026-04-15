from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import DemandForecast, ForecastParameter, SOPLineItem, SOPMeeting, SOPScenario


@admin.register(ForecastParameter)
class ForecastParameterAdmin(SimpleHistoryAdmin):
    list_display = ('product', 'method', 'lookback_months', 'weight_recent', 'smoothing_factor')
    list_filter = ('method',)
    raw_id_fields = ('product',)


@admin.register(DemandForecast)
class DemandForecastAdmin(SimpleHistoryAdmin):
    list_display = ('product', 'period_start', 'period_end', 'forecast_method', 'forecast_qty', 'actual_qty', 'accuracy_pct')
    list_filter = ('forecast_method',)
    raw_id_fields = ('product',)


@admin.register(SOPMeeting)
class SOPMeetingAdmin(SimpleHistoryAdmin):
    list_display = ('title', 'meeting_date', 'period', 'status')
    list_filter = ('status',)


@admin.register(SOPScenario)
class SOPScenarioAdmin(SimpleHistoryAdmin):
    list_display = ('meeting', 'name')
    raw_id_fields = ('meeting',)


@admin.register(SOPLineItem)
class SOPLineItemAdmin(SimpleHistoryAdmin):
    list_display = ('scenario', 'product', 'forecast_qty', 'planned_production', 'planned_purchase', 'planned_inventory')
    raw_id_fields = ('scenario', 'product')
