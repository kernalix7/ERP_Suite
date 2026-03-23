from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from .models import Product, Category, Warehouse


class ProductResource(resources.ModelResource):
    category = fields.Field(
        column_name='category__name',
        attribute='category',
        widget=ForeignKeyWidget(Category, field='name'),
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
        """카테고리명이 비어있으면 None 처리"""
        cat_name = row.get('category__name', '')
        if cat_name and not Category.objects.filter(name=cat_name).exists():
            Category.objects.create(name=cat_name)


class CategoryResource(resources.ModelResource):
    parent_name = fields.Field(
        column_name='parent_name',
        attribute='parent',
        widget=ForeignKeyWidget(Category, field='name'),
    )

    class Meta:
        model = Category
        fields = ('name', 'parent_name')
        import_id_fields = ('name',)
        skip_unchanged = True
        report_skipped = True


class WarehouseResource(resources.ModelResource):
    class Meta:
        model = Warehouse
        fields = ('code', 'name', 'location')
        import_id_fields = ('code',)
        skip_unchanged = True
        report_skipped = True
