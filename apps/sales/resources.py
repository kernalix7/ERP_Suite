from import_export import fields, resources, widgets

from apps.inventory.models import Product
from .models import Partner, Customer, Order, Quotation, Shipment
from .commission import CommissionRate


class PartnerResource(resources.ModelResource):
    class Meta:
        model = Partner
        fields = (
            'code', 'name', 'partner_type', 'business_number',
            'representative', 'contact_name', 'phone', 'email', 'address',
        )
        import_id_fields = ('code',)
        skip_unchanged = True
        report_skipped = True


class CustomerResource(resources.ModelResource):
    class Meta:
        model = Customer
        fields = ('name', 'phone', 'email', 'address')
        import_id_fields = ('name', 'phone')
        skip_unchanged = True
        report_skipped = True


class CommissionRateResource(resources.ModelResource):
    partner_code = fields.Field(
        column_name='partner_code',
        attribute='partner',
        widget=widgets.ForeignKeyWidget(Partner, field='code'),
    )
    product_code = fields.Field(
        column_name='product_code',
        attribute='product',
        widget=widgets.ForeignKeyWidget(Product, field='code'),
    )

    class Meta:
        model = CommissionRate
        fields = ('partner_code', 'product_code', 'rate')
        import_id_fields = ('partner_code', 'product_code')
        skip_unchanged = True
        report_skipped = True


class OrderResource(resources.ModelResource):
    partner_code = fields.Field(
        column_name='partner_code',
        attribute='partner',
        widget=widgets.ForeignKeyWidget(Partner, field='code'),
    )
    customer_name = fields.Field(
        column_name='customer_name',
        attribute='customer',
        widget=widgets.ForeignKeyWidget(Customer, field='name'),
    )

    class Meta:
        model = Order
        fields = (
            'order_number', 'order_type', 'partner_code', 'customer_name',
            'order_date', 'status', 'shipping_method', 'tracking_number',
            'shipping_address', 'notes',
        )
        import_id_fields = ('order_number',)
        skip_unchanged = True
        report_skipped = True


class QuotationResource(resources.ModelResource):
    partner_code = fields.Field(
        column_name='partner_code',
        attribute='partner',
        widget=widgets.ForeignKeyWidget(Partner, field='code'),
    )
    customer_name = fields.Field(
        column_name='customer_name',
        attribute='customer',
        widget=widgets.ForeignKeyWidget(Customer, field='name'),
    )

    class Meta:
        model = Quotation
        fields = (
            'quote_number', 'partner_code', 'customer_name',
            'quote_date', 'valid_until', 'status', 'notes',
        )
        import_id_fields = ('quote_number',)
        skip_unchanged = True
        report_skipped = True


class ShipmentResource(resources.ModelResource):
    order_number = fields.Field(
        column_name='order_number',
        attribute='order',
        widget=widgets.ForeignKeyWidget(Order, field='order_number'),
    )

    class Meta:
        model = Shipment
        fields = (
            'shipment_number', 'order_number', 'shipping_type',
            'carrier', 'tracking_number', 'status', 'shipped_date',
            'delivered_date', 'receiver_name', 'receiver_phone',
            'receiver_address',
        )
        import_id_fields = ('shipment_number',)
        skip_unchanged = True
        report_skipped = True
