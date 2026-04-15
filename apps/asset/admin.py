from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    AssetAudit, AssetAuditItem, AssetCategory, AssetTransfer,
    Certification, DepreciationRecord, FixedAsset, LeaseContract, Location,
    ReservableAsset, ReservationRule, AssetReservation, AssetMaintenance,
)


@admin.register(AssetCategory)
class AssetCategoryAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'useful_life_years', 'depreciation_method')
    search_fields = ('code', 'name')


@admin.register(Location)
class LocationAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'building', 'floor', 'room', 'parent')
    list_filter = ('building',)
    search_fields = ('code', 'name', 'building')


@admin.register(FixedAsset)
class FixedAssetAdmin(SimpleHistoryAdmin):
    list_display = ('asset_number', 'name', 'category', 'acquisition_date', 'acquisition_cost', 'book_value', 'status')
    list_filter = ('status', 'category', 'depreciation_method')
    search_fields = ('asset_number', 'name')
    raw_id_fields = ('category', 'department', 'responsible_person')


@admin.register(DepreciationRecord)
class DepreciationRecordAdmin(SimpleHistoryAdmin):
    list_display = ('asset', 'year', 'month', 'depreciation_amount', 'accumulated_amount', 'book_value_after')
    list_filter = ('year', 'month')
    raw_id_fields = ('asset',)


@admin.register(AssetTransfer)
class AssetTransferAdmin(admin.ModelAdmin):
    list_display = ['asset', 'transfer_date', 'from_department', 'to_department', 'created_at']
    list_filter = ['transfer_date', 'is_active']
    search_fields = ['asset__asset_number', 'asset__name']


@admin.register(Certification)
class CertificationAdmin(admin.ModelAdmin):
    list_display = ['cert_name', 'cert_type', 'product', 'issue_date', 'expiry_date', 'is_capitalized', 'is_active']
    list_filter = ['cert_type', 'is_capitalized', 'is_active']
    search_fields = ['cert_name', 'cert_number']


@admin.register(LeaseContract)
class LeaseContractAdmin(admin.ModelAdmin):
    list_display = ['contract_number', 'asset', 'lease_type', 'start_date', 'end_date', 'monthly_payment', 'is_active']
    list_filter = ['lease_type', 'is_active']
    search_fields = ['contract_number', 'asset__name']


@admin.register(AssetAudit)
class AssetAuditAdmin(admin.ModelAdmin):
    list_display = ['audit_date', 'auditor', 'department', 'is_active']
    list_filter = ['audit_date', 'is_active']


@admin.register(AssetAuditItem)
class AssetAuditItemAdmin(admin.ModelAdmin):
    list_display = ['audit', 'asset', 'status', 'condition', 'is_active']
    list_filter = ['status', 'condition', 'is_active']


@admin.register(ReservableAsset)
class ReservableAssetAdmin(admin.ModelAdmin):
    list_display = ['name', 'resource_type', 'location', 'capacity', 'requires_approval', 'is_active']
    list_filter = ['resource_type', 'requires_approval', 'is_active']
    search_fields = ['name']


@admin.register(ReservationRule)
class ReservationRuleAdmin(admin.ModelAdmin):
    list_display = ['asset', 'day_of_week', 'open_time', 'close_time', 'is_closed']
    list_filter = ['day_of_week', 'is_closed']


@admin.register(AssetReservation)
class AssetReservationAdmin(admin.ModelAdmin):
    list_display = ['reservation_number', 'asset', 'requester', 'start_datetime', 'end_datetime', 'status']
    list_filter = ['status', 'is_active']
    search_fields = ['reservation_number', 'asset__name', 'requester__username']


@admin.register(AssetMaintenance)
class AssetMaintenanceAdmin(admin.ModelAdmin):
    list_display = ['asset', 'maintenance_type', 'status', 'scheduled_date', 'completed_date', 'cost']
    list_filter = ['maintenance_type', 'status', 'is_active']
    search_fields = ['asset__name', 'vendor']
