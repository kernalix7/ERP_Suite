from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Currency, ExchangeRate,
    TaxRate, TaxInvoice, FixedCost, WithholdingTax, AccountCode, Voucher, VoucherLine,
    AccountReceivable, AccountPayable, Payment, BankAccount,
    AccountTransfer, PaymentDistribution,
)


@admin.register(Currency)
class CurrencyAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'symbol', 'decimal_places', 'is_base')


@admin.register(ExchangeRate)
class ExchangeRateAdmin(SimpleHistoryAdmin):
    list_display = ('currency', 'rate_date', 'rate')
    list_filter = ('currency',)


@admin.register(TaxRate)
class TaxRateAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'code', 'rate', 'is_default', 'effective_from')


@admin.register(TaxInvoice)
class TaxInvoiceAdmin(SimpleHistoryAdmin):
    list_display = ('invoice_number', 'invoice_type', 'partner', 'supply_amount', 'tax_amount', 'issue_date')
    list_filter = ('invoice_type',)


@admin.register(FixedCost)
class FixedCostAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'category', 'amount', 'month', 'is_recurring')
    list_filter = ('category',)


@admin.register(WithholdingTax)
class WithholdingTaxAdmin(SimpleHistoryAdmin):
    list_display = ('payee_name', 'tax_type', 'gross_amount', 'tax_amount', 'net_amount', 'payment_date')
    list_filter = ('tax_type',)


@admin.register(AccountCode)
class AccountCodeAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'account_type', 'parent')
    list_filter = ('account_type',)


class VoucherLineInline(admin.TabularInline):
    model = VoucherLine
    extra = 1


@admin.register(Voucher)
class VoucherAdmin(SimpleHistoryAdmin):
    list_display = ('voucher_number', 'voucher_type', 'voucher_date', 'description', 'approval_status')
    list_filter = ('voucher_type', 'approval_status')
    inlines = [VoucherLineInline]


@admin.register(AccountReceivable)
class AccountReceivableAdmin(SimpleHistoryAdmin):
    list_display = (
        'partner', 'amount', 'paid_amount',
        'due_date', 'status',
    )
    list_filter = ('status',)


@admin.register(AccountPayable)
class AccountPayableAdmin(SimpleHistoryAdmin):
    list_display = (
        'partner', 'amount', 'paid_amount',
        'due_date', 'status',
    )
    list_filter = ('status',)


@admin.register(BankAccount)
class BankAccountAdmin(SimpleHistoryAdmin):
    list_display = (
        'name', 'account_type', 'owner', 'bank',
        'account_number', 'balance', 'is_default',
    )
    list_filter = ('account_type',)


@admin.register(Payment)
class PaymentAdmin(SimpleHistoryAdmin):
    list_display = (
        'payment_number', 'payment_type', 'partner',
        'bank_account', 'amount', 'payment_date', 'payment_method',
    )
    list_filter = ('payment_type', 'payment_method', 'bank_account')


@admin.register(AccountTransfer)
class AccountTransferAdmin(SimpleHistoryAdmin):
    list_display = (
        'transfer_number', 'from_account', 'to_account',
        'amount', 'transfer_date',
    )


@admin.register(PaymentDistribution)
class PaymentDistributionAdmin(SimpleHistoryAdmin):
    list_display = ('payment', 'bank_account', 'amount')
