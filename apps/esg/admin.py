from django.contrib import admin

from .models import (
    CarbonEmission, ComplianceRequirement, ESGCategory, ESGMetric,
    ESGRecord, ESGReport, SafetyIncident,
)


@admin.register(ESGCategory)
class ESGCategoryAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category_type', 'parent', 'is_active']
    list_filter = ['category_type', 'is_active']
    search_fields = ['name', 'code']


@admin.register(ESGMetric)
class ESGMetricAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'category', 'unit', 'target_value', 'measurement_frequency']
    list_filter = ['measurement_frequency', 'category__category_type']
    search_fields = ['name', 'code']


@admin.register(ESGRecord)
class ESGRecordAdmin(admin.ModelAdmin):
    list_display = ['metric', 'period_start', 'period_end', 'value', 'verified', 'recorded_by']
    list_filter = ['verified', 'is_active']


@admin.register(CarbonEmission)
class CarbonEmissionAdmin(admin.ModelAdmin):
    list_display = ['source', 'scope', 'amount_kg', 'period', 'facility']
    list_filter = ['scope', 'is_active']
    search_fields = ['source', 'facility']


@admin.register(SafetyIncident)
class SafetyIncidentAdmin(admin.ModelAdmin):
    list_display = ['incident_number', 'date', 'severity', 'status', 'injured_count', 'location']
    list_filter = ['severity', 'status', 'is_active']
    search_fields = ['incident_number', 'description']


@admin.register(ComplianceRequirement)
class ComplianceRequirementAdmin(admin.ModelAdmin):
    list_display = ['name', 'regulation', 'status', 'due_date', 'responsible']
    list_filter = ['status', 'is_active']
    search_fields = ['name', 'regulation']


@admin.register(ESGReport)
class ESGReportAdmin(admin.ModelAdmin):
    list_display = ['title', 'report_type', 'period_start', 'period_end', 'status']
    list_filter = ['report_type', 'status']
