from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from apps.sales.models import Partner
from .models import AccountCode, FixedCost, TaxInvoice, Voucher, WithholdingTax


class FixedCostResource(resources.ModelResource):
    class Meta:
        model = FixedCost
        fields = ('name', 'category', 'amount', 'month', 'is_recurring')
        import_id_fields = ('name', 'month')
        skip_unchanged = True
        report_skipped = True


class AccountCodeResource(resources.ModelResource):
    parent_code = fields.Field(
        column_name='parent_code',
        attribute='parent',
        widget=ForeignKeyWidget(AccountCode, field='code'),
    )

    class Meta:
        model = AccountCode
        fields = ('code', 'name', 'account_type', 'parent_code')
        import_id_fields = ('code',)
        skip_unchanged = True
        report_skipped = True


class TaxInvoiceResource(resources.ModelResource):
    partner_code = fields.Field(
        column_name='partner_code',
        attribute='partner',
        widget=ForeignKeyWidget(Partner, field='code'),
    )

    class Meta:
        model = TaxInvoice
        fields = (
            'invoice_number', 'invoice_type', 'partner_code',
            'issue_date', 'supply_amount', 'tax_amount',
            'total_amount', 'description',
        )
        import_id_fields = ('invoice_number',)
        skip_unchanged = True
        report_skipped = True


class VoucherResource(resources.ModelResource):
    class Meta:
        model = Voucher
        fields = (
            'voucher_number', 'voucher_type', 'voucher_date',
            'description',
        )
        import_id_fields = ('voucher_number',)
        skip_unchanged = True
        report_skipped = True


class WithholdingTaxResource(resources.ModelResource):
    class Meta:
        model = WithholdingTax
        fields = (
            'tax_type', 'payee_name', 'payment_date',
            'gross_amount', 'tax_rate', 'tax_amount', 'net_amount',
        )
        import_id_fields = ('payee_name', 'payment_date')
        skip_unchanged = True
        report_skipped = True
