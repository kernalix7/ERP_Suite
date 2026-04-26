from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from apps.sales.models import Partner
from .models import (
    AccountCode, FixedCost, TaxInvoice, Voucher, WithholdingTax,
    AccountReceivable, AccountPayable, BankAccount, Payment,
)


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


class BankAccountResource(resources.ModelResource):
    """결제계좌 import_export — 마이그레이션 시 기초잔액 포함 가능."""

    account_code = fields.Field(
        column_name='account_code',
        attribute='account_code',
        widget=ForeignKeyWidget(AccountCode, field='code'),
    )

    class Meta:
        model = BankAccount
        fields = (
            'name', 'account_type', 'owner', 'bank',
            'account_number', 'account_code',
            'opening_balance', 'balance', 'is_default',
        )
        import_id_fields = ('account_number',)
        skip_unchanged = True
        report_skipped = True


class AccountReceivableResource(resources.ModelResource):
    """미수금 — 기초이월 import 권장."""

    partner_code = fields.Field(
        column_name='partner_code',
        attribute='partner',
        widget=ForeignKeyWidget(Partner, field='code'),
    )

    class Meta:
        model = AccountReceivable
        fields = (
            'partner_code', 'amount', 'paid_amount',
            'due_date', 'status', 'notes',
        )
        skip_unchanged = True
        report_skipped = True


class AccountPayableResource(resources.ModelResource):
    """미지급금 — 기초이월 import 권장."""

    partner_code = fields.Field(
        column_name='partner_code',
        attribute='partner',
        widget=ForeignKeyWidget(Partner, field='code'),
    )

    class Meta:
        model = AccountPayable
        fields = (
            'partner_code', 'amount', 'paid_amount',
            'due_date', 'status', 'notes',
        )
        skip_unchanged = True
        report_skipped = True


class PaymentResource(resources.ModelResource):
    """입출금 — 자동 시그널 작동에 주의 (BankAccount.balance 자동갱신)."""

    partner_code = fields.Field(
        column_name='partner_code',
        attribute='partner',
        widget=ForeignKeyWidget(Partner, field='code'),
    )
    bank_account_number = fields.Field(
        column_name='bank_account_number',
        attribute='bank_account',
        widget=ForeignKeyWidget(BankAccount, field='account_number'),
    )

    class Meta:
        model = Payment
        fields = (
            'payment_number', 'payment_type', 'partner_code',
            'bank_account_number', 'amount', 'payment_date',
            'payment_method', 'reference', 'is_advance',
        )
        import_id_fields = ('payment_number',)
        skip_unchanged = True
        report_skipped = True
