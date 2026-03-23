from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from apps.inventory.models import Product
from apps.sales.models import Partner
from .models import PurchaseOrder, PurchaseOrderItem


class PurchaseOrderResource(resources.ModelResource):
    partner_code = fields.Field(
        column_name='partner_code',
        attribute='partner',
        widget=ForeignKeyWidget(Partner, field='code'),
    )

    class Meta:
        model = PurchaseOrder
        fields = (
            'po_number', 'partner_code', 'order_date',
            'expected_date', 'status',
        )
        import_id_fields = ('po_number',)
        skip_unchanged = True
        report_skipped = True


class PurchaseOrderItemResource(resources.ModelResource):
    po_number = fields.Field(
        column_name='po_number',
        attribute='purchase_order',
        widget=ForeignKeyWidget(PurchaseOrder, field='po_number'),
    )
    product_code = fields.Field(
        column_name='product_code',
        attribute='product',
        widget=ForeignKeyWidget(Product, field='code'),
    )

    class Meta:
        model = PurchaseOrderItem
        fields = (
            'po_number', 'product_code', 'quantity', 'unit_price',
        )
        import_id_fields = ('po_number', 'product_code')
        skip_unchanged = True
        report_skipped = True
