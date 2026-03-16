from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import BOM, BOMItem, ProductionPlan, WorkOrder, ProductionRecord


class BOMItemInline(admin.TabularInline):
    model = BOMItem
    extra = 1


@admin.register(BOM)
class BOMAdmin(SimpleHistoryAdmin):
    list_display = ('product', 'version', 'is_default', 'is_active')
    inlines = [BOMItemInline]


@admin.register(ProductionPlan)
class ProductionPlanAdmin(SimpleHistoryAdmin):
    list_display = ('plan_number', 'product', 'planned_quantity', 'status', 'planned_start', 'planned_end')
    list_filter = ('status',)


@admin.register(WorkOrder)
class WorkOrderAdmin(SimpleHistoryAdmin):
    list_display = ('order_number', 'production_plan', 'quantity', 'status', 'assigned_to')
    list_filter = ('status',)


@admin.register(ProductionRecord)
class ProductionRecordAdmin(SimpleHistoryAdmin):
    list_display = ('work_order', 'good_quantity', 'defect_quantity', 'record_date', 'worker')
