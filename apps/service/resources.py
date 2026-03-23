from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from apps.inventory.models import Product
from apps.sales.models import Customer
from .models import ServiceRequest


class ServiceRequestResource(resources.ModelResource):
    customer_name = fields.Field(
        column_name='customer_name',
        attribute='customer',
        widget=ForeignKeyWidget(Customer, field='name'),
    )
    product_code = fields.Field(
        column_name='product_code',
        attribute='product',
        widget=ForeignKeyWidget(Product, field='code'),
    )

    class Meta:
        model = ServiceRequest
        fields = (
            'request_number', 'customer_name', 'product_code',
            'serial_number', 'request_type', 'status',
            'symptom', 'received_date',
        )
        import_id_fields = ('request_number',)
        skip_unchanged = True
        report_skipped = True
