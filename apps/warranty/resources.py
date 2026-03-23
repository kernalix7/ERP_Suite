from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from apps.inventory.models import Product
from .models import ProductRegistration


class ProductRegistrationResource(resources.ModelResource):
    product_code = fields.Field(
        column_name='product_code',
        attribute='product',
        widget=ForeignKeyWidget(Product, field='code'),
    )

    class Meta:
        model = ProductRegistration
        fields = (
            'serial_number', 'product_code', 'customer_name',
            'phone', 'purchase_date', 'purchase_channel',
            'warranty_start', 'warranty_end',
        )
        import_id_fields = ('serial_number',)
        skip_unchanged = True
        report_skipped = True
