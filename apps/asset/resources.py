"""고정자산 import_export Resource — 마이그레이션 시 자산 + 누계감가상각 동시 import."""
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from .models import AssetCategory, FixedAsset


class AssetCategoryResource(resources.ModelResource):
    class Meta:
        model = AssetCategory
        fields = (
            'code', 'name', 'depreciation_method',
            'useful_life_years', 'residual_rate',
        )
        import_id_fields = ('code',)
        skip_unchanged = True
        report_skipped = True


class FixedAssetResource(resources.ModelResource):
    """유형자산 — accumulated_depreciation/book_value 직접 import 가능.

    시그널이 DepreciationRecord 생성 시 book_value를 갱신하므로,
    기초이월에는 accumulated_depreciation/book_value를 정확히 입력해야 한다.
    """

    category_code = fields.Field(
        column_name='category_code',
        attribute='category',
        widget=ForeignKeyWidget(AssetCategory, field='code'),
    )

    class Meta:
        model = FixedAsset
        fields = (
            'asset_number', 'name', 'category_code',
            'acquisition_date', 'acquisition_cost',
            'accumulated_depreciation', 'book_value',
            'useful_life_years', 'residual_rate',
            'depreciation_method', 'status',
        )
        import_id_fields = ('asset_number',)
        skip_unchanged = True
        report_skipped = True
