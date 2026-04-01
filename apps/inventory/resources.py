from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from .models import Product, Category, Warehouse


class ProductResource(resources.ModelResource):
    category = fields.Field(
        column_name='category__code',
        attribute='category',
        widget=ForeignKeyWidget(Category, field='code'),
    )

    class Meta:
        model = Product
        fields = (
            'code', 'name', 'product_type', 'category',
            'unit', 'unit_price', 'cost_price', 'safety_stock',
        )
        import_id_fields = ('code',)
        skip_unchanged = True
        report_skipped = True

    def before_import_row(self, row, **kwargs):
        """카테고리코드가 비어있으면 None 처리"""
        cat_code = row.get('category__code', '')
        if cat_code and not Category.objects.filter(code=cat_code).exists():
            Category.objects.create(code=cat_code, name=cat_code)


class CategoryResource(resources.ModelResource):
    parent_name = fields.Field(
        column_name='parent_name',
        attribute='parent',
        widget=ForeignKeyWidget(Category, field='code'),
    )

    class Meta:
        model = Category
        fields = ('code', 'name', 'parent_name')
        import_id_fields = ('code',)
        skip_unchanged = True
        report_skipped = True


class WarehouseResource(resources.ModelResource):
    class Meta:
        model = Warehouse
        fields = ('code', 'name', 'location')
        import_id_fields = ('code',)
        skip_unchanged = True
        report_skipped = True
