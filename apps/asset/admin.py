from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import AssetCategory, FixedAsset, DepreciationRecord


@admin.register(AssetCategory)
class AssetCategoryAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'useful_life_years', 'depreciation_method')
    search_fields = ('code', 'name')


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
