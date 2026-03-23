from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from apps.inventory.models import Product
from .models import BOM, BOMItem


class BOMResource(resources.ModelResource):
    product = fields.Field(
        column_name='product__code',
        attribute='product',
        widget=ForeignKeyWidget(Product, field='code'),
    )

    class Meta:
        model = BOM
        fields = ('product', 'version', 'is_default', 'notes')
        import_id_fields = ('product', 'version')
        skip_unchanged = True
        report_skipped = True


class BOMItemResource(resources.ModelResource):
    bom_product = fields.Field(
        column_name='bom__product__code',
        attribute='bom',
        widget=ForeignKeyWidget(BOM, field='product__code'),
    )
    material = fields.Field(
        column_name='material__code',
        attribute='material',
        widget=ForeignKeyWidget(Product, field='code'),
    )

    class Meta:
        model = BOMItem
        fields = ('bom_product', 'material', 'quantity', 'loss_rate', 'notes')
        import_id_fields = ('bom_product', 'material')
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """BOM product code → BOM FK 변환"""
        product_code = row.get('bom__product__code')
        if product_code:
            bom = BOM.objects.filter(
                product__code=product_code, is_default=True,
            ).first()
            if bom:
                row['bom__product__code'] = bom.product.code
