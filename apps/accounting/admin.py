from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Currency, ExchangeRate,
    TaxRate, TaxInvoice, FixedCost, WithholdingTax, AccountCode, Voucher, VoucherLine,
    AccountReceivable, AccountPayable, Payment, BankAccount,
    AccountTransfer, PaymentDistribution,
    CostSettlement, CostSettlementItem, SalesSettlement, SalesSettlementOrder,
    Budget, ClosingPeriod, CostCenter, DashboardWidget,
    CreditCard, CardTransaction, CardBilling,
    Company, InterCompanyTransaction, ConsolidationPeriod, ConsolidatedReport,
    BankConnection, BankStatement, BankTransaction,
    CashReceipt,
    PlatformFinancialConfig,
)
from .models_baddebt import BadDebtAllowance
from .models_advance import AdvanceReceived, AdvancePaid
from .models_cardslip import CardSalesSlip
from .models_recon import BankReconRule, CardReconRule, VoucherApprovalConfig


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


@admin.register(CashReceipt)
class CashReceiptAdmin(SimpleHistoryAdmin):
    list_display = (
        'receipt_number', 'issued_at', 'purpose', 'identifier',
        'partner', 'total_amount', 'status',
    )
    list_filter = ('purpose', 'status')
    search_fields = ('receipt_number', 'identifier', 'partner__name')
    date_hierarchy = 'issued_at'
    readonly_fields = ('receipt_number', 'cancelled_at')


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


class CostSettlementItemInline(admin.TabularInline):
    model = CostSettlementItem
    extra = 0
    raw_id_fields = ('product',)


@admin.register(CostSettlement)
class CostSettlementAdmin(SimpleHistoryAdmin):
    list_display = ('settlement_number', 'period_type', 'period_start', 'period_end', 'total_inventory_value')
    list_filter = ('period_type',)
    inlines = [CostSettlementItemInline]


class SalesSettlementOrderInline(admin.TabularInline):
    model = SalesSettlementOrder
    extra = 0
    raw_id_fields = ('order',)


@admin.register(SalesSettlement)
class SalesSettlementAdmin(SimpleHistoryAdmin):
    list_display = (
        'settlement_number', 'settlement_date', 'total_revenue',
        'total_cost', 'total_profit', 'commission_paid',
    )
    list_filter = ('commission_paid',)
    inlines = [SalesSettlementOrderInline]


@admin.register(Budget)
class BudgetAdmin(SimpleHistoryAdmin):
    list_display = ('account', 'year', 'month', 'budget_amount')
    list_filter = ('year', 'month')
    raw_id_fields = ('account',)


@admin.register(ClosingPeriod)
class ClosingPeriodAdmin(SimpleHistoryAdmin):
    list_display = ('year', 'month', 'is_closed', 'closed_at', 'closed_by')
    list_filter = ('year', 'is_closed')


@admin.register(CostCenter)
class CostCenterAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'center_type', 'parent', 'department', 'manager')
    list_filter = ('center_type',)
    search_fields = ('code', 'name')
    raw_id_fields = ('parent', 'department', 'manager')


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'widget_type', 'sort_order', 'is_visible', 'user')
    list_filter = ('widget_type', 'is_visible')


@admin.register(CreditCard)
class CreditCardAdmin(SimpleHistoryAdmin):
    list_display = ('name', 'card_type', 'card_issuer', 'card_number_last4', 'cardholder', 'monthly_limit', 'used_amount')
    list_filter = ('card_type', 'card_issuer')
    search_fields = ('name', 'cardholder')
    raw_id_fields = ('employee', 'payment_account', 'account_code')


@admin.register(CardTransaction)
class CardTransactionAdmin(SimpleHistoryAdmin):
    list_display = ('card', 'transaction_date', 'merchant_name', 'amount', 'category', 'is_cancelled')
    list_filter = ('category', 'is_cancelled')
    search_fields = ('merchant_name', 'authorization_number')
    raw_id_fields = ('card', 'partner', 'voucher', 'billing')


@admin.register(CardBilling)
class CardBillingAdmin(SimpleHistoryAdmin):
    list_display = ('card', 'billing_month', 'total_amount', 'paid_amount', 'status')
    list_filter = ('status',)
    raw_id_fields = ('card', 'payment')


@admin.register(Company)
class CompanyAdmin(SimpleHistoryAdmin):
    list_display = ('code', 'name', 'legal_name', 'tax_id', 'country_code', 'parent')
    list_filter = ('country_code',)
    search_fields = ('code', 'name', 'legal_name')
    raw_id_fields = ('parent', 'currency')


@admin.register(InterCompanyTransaction)
class InterCompanyTransactionAdmin(SimpleHistoryAdmin):
    list_display = ('from_company', 'to_company', 'transaction_date', 'amount', 'status')
    list_filter = ('status',)
    raw_id_fields = ('from_company', 'to_company', 'voucher_from', 'voucher_to')


@admin.register(ConsolidationPeriod)
class ConsolidationPeriodAdmin(SimpleHistoryAdmin):
    list_display = ('year', 'month', 'status', 'consolidated_at')
    list_filter = ('year', 'status')


@admin.register(ConsolidatedReport)
class ConsolidatedReportAdmin(SimpleHistoryAdmin):
    list_display = ('period', 'report_type', 'generated_at')
    list_filter = ('report_type',)
    raw_id_fields = ('period',)


@admin.register(BankConnection)
class BankConnectionAdmin(SimpleHistoryAdmin):
    list_display = ('bank_name', 'bank_code', 'account_number', 'account_holder', 'connection_type', 'status')
    list_filter = ('connection_type', 'status')
    search_fields = ('bank_name', 'account_number')
    raw_id_fields = ('company',)


@admin.register(BankStatement)
class BankStatementAdmin(SimpleHistoryAdmin):
    list_display = ('connection', 'statement_date', 'opening_balance', 'closing_balance', 'transaction_count', 'status')
    list_filter = ('status',)
    raw_id_fields = ('connection',)


@admin.register(BankTransaction)
class BankTransactionAdmin(SimpleHistoryAdmin):
    list_display = ('statement', 'transaction_date', 'description', 'amount', 'match_status')
    list_filter = ('match_status',)
    search_fields = ('description', 'counterparty', 'reference_number')
    raw_id_fields = ('statement', 'matched_voucher', 'matched_payment')


@admin.register(PlatformFinancialConfig)
class PlatformFinancialConfigAdmin(SimpleHistoryAdmin):
    list_display = (
        'code', 'name', 'payment_method_default',
        'settlement_cycle_days', 'commission_rate',
        'tax_invoice_issuer', 'vat_classification_default',
        'is_enabled', 'is_active',
    )
    list_filter = (
        'tax_invoice_issuer', 'cash_receipt_issuer', 'card_receipt_issuer',
        'vat_classification_default', 'is_enabled', 'is_active',
    )
    search_fields = ('code', 'name')


@admin.register(BadDebtAllowance)
class BadDebtAllowanceAdmin(SimpleHistoryAdmin):
    list_display = (
        'receivable', 'estimated_date', 'aging_bucket',
        'allowance_rate', 'allowance_amount', 'voucher', 'is_active',
    )
    list_filter = ('aging_bucket', 'is_active')
    search_fields = ('receivable__partner__name',)
    raw_id_fields = ('receivable', 'voucher')
    date_hierarchy = 'estimated_date'


@admin.register(AdvanceReceived)
class AdvanceReceivedAdmin(SimpleHistoryAdmin):
    list_display = (
        'partner', 'customer', 'amount', 'applied_amount',
        'received_date', 'status', 'is_active',
    )
    list_filter = ('status', 'is_active')
    search_fields = ('partner__name', 'customer__name')
    raw_id_fields = ('partner', 'customer', 'received_voucher', 'applied_to_order')
    date_hierarchy = 'received_date'


@admin.register(AdvancePaid)
class AdvancePaidAdmin(SimpleHistoryAdmin):
    list_display = (
        'partner', 'amount', 'applied_amount',
        'paid_date', 'status', 'is_active',
    )
    list_filter = ('status', 'is_active')
    search_fields = ('partner__name',)
    raw_id_fields = ('partner', 'paid_voucher', 'applied_to_po')
    date_hierarchy = 'paid_date'


@admin.register(CardSalesSlip)
class CardSalesSlipAdmin(SimpleHistoryAdmin):
    list_display = (
        'slip_number', 'approved_at', 'card_brand', 'approval_code',
        'card_number_masked', 'total_amount', 'status',
    )
    list_filter = ('status', 'card_brand', 'is_active')
    search_fields = ('slip_number', 'approval_code', 'merchant_number')
    raw_id_fields = ('order', 'partner', 'card_transaction')
    date_hierarchy = 'approved_at'


@admin.register(BankReconRule)
class BankReconRuleAdmin(SimpleHistoryAdmin):
    list_display = (
        'priority', 'name', 'match_field', 'pattern',
        'amount_tolerance', 'date_tolerance_days', 'is_active_rule',
    )
    list_filter = ('match_field', 'is_active_rule', 'is_active')
    search_fields = ('name', 'pattern')
    raw_id_fields = ('bank_account', 'target_partner')
    ordering = ('priority', 'name')


@admin.register(CardReconRule)
class CardReconRuleAdmin(SimpleHistoryAdmin):
    list_display = (
        'priority', 'name', 'card', 'merchant_pattern', 'is_active_rule',
    )
    list_filter = ('is_active_rule', 'is_active')
    search_fields = ('name', 'merchant_pattern')
    raw_id_fields = ('card', 'target_partner', 'target_account')
    ordering = ('priority', 'name')


@admin.register(VoucherApprovalConfig)
class VoucherApprovalConfigAdmin(SimpleHistoryAdmin):
    list_display = (
        'auto_voucher_default_status',
        'auto_approval_amount_threshold',
        'manual_approval_amount_threshold',
    )
