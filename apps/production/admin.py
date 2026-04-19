from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    BOM, BOMItem, ProductionPlan, WorkOrder,
    ProductionRecord, StandardCost, QualityInspection,
    WorkCenter, ProductionSchedule, ProductionBatch,
)


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
    list_display = (
        'work_order', 'good_quantity', 'defect_quantity',
        'record_date', 'worker',
    )


@admin.register(StandardCost)
class StandardCostAdmin(SimpleHistoryAdmin):
    list_display = (
        'product', 'version', 'effective_date',
        'material_cost', 'labor_cost', 'overhead_cost',
        'total_standard_cost', 'is_current',
    )
    list_filter = ('is_current', 'effective_date')
    search_fields = ('product__name', 'version')


@admin.register(QualityInspection)
class QualityInspectionAdmin(SimpleHistoryAdmin):
    list_display = (
        'inspection_number', 'inspection_type', 'product',
        'inspected_quantity', 'pass_quantity', 'fail_quantity',
        'result', 'inspection_date',
    )
    list_filter = ('inspection_type', 'result', 'is_active')
    search_fields = ('inspection_number', 'product__name')
    raw_id_fields = ('product', 'production_record', 'inspector')


@admin.register(WorkCenter)
class WorkCenterAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'capacity_per_day', 'efficiency_rate', 'operating_hours', 'is_active')
    search_fields = ('code', 'name')


@admin.register(ProductionSchedule)
class ProductionScheduleAdmin(SimpleHistoryAdmin):
    list_display = ('work_order', 'work_center', 'scheduled_start', 'scheduled_end', 'status', 'is_active')
    list_filter = ('status', 'is_active')
    search_fields = ('work_order__order_number', 'work_center__code')
    raw_id_fields = ('work_order', 'work_center')


@admin.register(ProductionBatch)
class ProductionBatchAdmin(SimpleHistoryAdmin):
    list_display = (
        'batch_number', 'product', 'work_center', 'production_date',
        'shift', 'sequence', 'total_quantity', 'remaining_quantity',
    )
    list_filter = ('work_center', 'production_date', 'shift')
    search_fields = ('batch_number', 'product__name', 'product__code')
    raw_id_fields = ('product', 'production_record')
    readonly_fields = ('batch_number', 'sequence')
