from django import forms
from apps.core.forms import BaseForm
from .models import (
    Currency, ExchangeRate,
    TaxRate, TaxInvoice, FixedCost, WithholdingTax, AccountCode, Voucher, VoucherLine,
    AccountReceivable, AccountPayable, Payment, BankAccount,
    AccountTransfer, PaymentDistribution,
    CreditCard, CardTransaction,
    CostCenter, DashboardWidget,
    Company, InterCompanyTransaction, ConsolidationPeriod,
    BankConnection, BankStatement,
    CashReceipt, CashReceiptItem,
)


class CurrencyForm(BaseForm):
    class Meta:
        model = Currency
        fields = ['code', 'name', 'symbol', 'decimal_places', 'is_base', 'notes']


class ExchangeRateForm(BaseForm):
    class Meta:
        model = ExchangeRate
        fields = ['currency', 'rate_date', 'rate', 'notes']
        widgets = {
            'rate_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class TaxRateForm(BaseForm):
    class Meta:
        model = TaxRate
        fields = ['name', 'code', 'rate', 'is_default', 'effective_from', 'effective_to', 'notes']
        widgets = {
            'effective_from': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'effective_to': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class TaxInvoiceForm(BaseForm):
    class Meta:
        model = TaxInvoice
        fields = [
            'invoice_number', 'invoice_type', 'partner', 'order', 'issue_date',
            'supply_amount', 'tax_amount', 'total_amount', 'description', 'notes',
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class CashReceiptForm(BaseForm):
    class Meta:
        model = CashReceipt
        fields = [
            'issued_at', 'purpose', 'identifier', 'partner',
            'supply_amount', 'vat', 'notes',
        ]
        widgets = {
            'issued_at': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        supply = cleaned.get('supply_amount') or 0
        vat = cleaned.get('vat') or 0
        if supply < 0 or vat < 0:
            raise forms.ValidationError('공급가액/부가세는 0 이상이어야 합니다.')
        return cleaned


class CashReceiptCancelForm(forms.Form):
    cancel_reason = forms.CharField(
        label='취소사유', max_length=200, required=True,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-input'}),
    )


class CashReceiptItemForm(BaseForm):
    class Meta:
        model = CashReceiptItem
        fields = ['name', 'quantity', 'unit_price', 'supply_amount', 'vat', 'source_order_item']
        widgets = {
            'source_order_item': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('name', 'quantity', 'unit_price', 'supply_amount', 'vat'):
            self.fields[name].required = False


CashReceiptItemFormSet = forms.inlineformset_factory(
    CashReceipt, CashReceiptItem,
    form=CashReceiptItemForm,
    extra=0,
    can_delete=True,
)


class FixedCostForm(BaseForm):
    class Meta:
        model = FixedCost
        fields = ['category', 'name', 'amount', 'month', 'is_recurring', 'recurring_unit', 'notes']
        widgets = {
            'month': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class WithholdingTaxForm(BaseForm):
    class Meta:
        model = WithholdingTax
        fields = [
            'tax_type', 'payee_name', 'payment_date', 'gross_amount',
            'tax_rate', 'tax_amount', 'net_amount', 'notes',
        ]
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class AccountCodeForm(BaseForm):
    class Meta:
        model = AccountCode
        fields = ['code', 'name', 'account_type', 'parent', 'notes']


class VoucherForm(BaseForm):
    class Meta:
        model = Voucher
        fields = ['voucher_number', 'voucher_type', 'voucher_date', 'description', 'notes']
        widgets = {
            'voucher_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class VoucherLineForm(BaseForm):
    class Meta:
        model = VoucherLine
        fields = ['account', 'debit', 'credit', 'description', 'cost_center']


VoucherLineFormSet = forms.inlineformset_factory(
    Voucher, VoucherLine,
    form=VoucherLineForm,
    extra=3,
    can_delete=True,
)


class AccountReceivableForm(BaseForm):
    class Meta:
        model = AccountReceivable
        fields = ['partner', 'order', 'invoice', 'amount', 'paid_amount', 'due_date', 'status', 'notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class AccountPayableForm(BaseForm):
    class Meta:
        model = AccountPayable
        fields = ['partner', 'purchase_order', 'invoice', 'amount', 'paid_amount', 'due_date', 'status', 'notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class BankAccountForm(BaseForm):
    class Meta:
        model = BankAccount
        fields = [
            'name', 'account_type', 'owner', 'bank', 'account_number',
            'account_code', 'opening_balance', 'is_default', 'show_on_dashboard', 'notes',
        ]


class PaymentForm(BaseForm):
    class Meta:
        model = Payment
        fields = ['payment_number', 'payment_type', 'partner', 'bank_account', 'amount', 'payment_date', 'payment_method', 'reference', 'notes']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class AccountTransferForm(BaseForm):
    class Meta:
        model = AccountTransfer
        fields = ['transfer_number', 'from_account', 'to_account', 'amount', 'transfer_date', 'description', 'notes']
        widgets = {
            'transfer_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        from_acc = cleaned.get('from_account')
        to_acc = cleaned.get('to_account')
        if from_acc and to_acc and from_acc == to_acc:
            raise forms.ValidationError('출금계좌와 입금계좌가 같을 수 없습니다.')
        return cleaned


class PaymentDistributionForm(BaseForm):
    class Meta:
        model = PaymentDistribution
        fields = ['bank_account', 'amount', 'description']


PaymentDistributionFormSet = forms.inlineformset_factory(
    Payment, PaymentDistribution,
    form=PaymentDistributionForm,
    extra=2,
    can_delete=True,
)


class CreditCardForm(BaseForm):
    class Meta:
        model = CreditCard
        fields = [
            'name', 'card_type', 'card_issuer', 'card_number_last4',
            'cardholder', 'employee', 'expiry_date', 'monthly_limit',
            'billing_day', 'payment_account', 'account_code', 'notes',
        ]


class CardTransactionForm(BaseForm):
    class Meta:
        model = CardTransaction
        fields = [
            'card', 'transaction_date', 'merchant_name', 'amount',
            'tax_amount', 'installments', 'authorization_number',
            'category', 'partner', 'notes',
        ]
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class CostCenterForm(BaseForm):
    class Meta:
        model = CostCenter
        fields = ['code', 'name', 'parent', 'center_type', 'department', 'manager', 'notes']


# ──── Phase 15: 다중법인/연결회계 ────

class CompanyForm(BaseForm):
    class Meta:
        model = Company
        fields = ['name', 'code', 'legal_name', 'tax_id', 'country_code',
                  'currency', 'address', 'parent', 'notes']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
        }


class InterCompanyTransactionForm(BaseForm):
    class Meta:
        model = InterCompanyTransaction
        fields = ['from_company', 'to_company', 'transaction_date', 'description',
                  'amount', 'currency_code', 'status', 'notes']
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ConsolidationPeriodForm(BaseForm):
    class Meta:
        model = ConsolidationPeriod
        fields = ['year', 'month', 'companies', 'notes']
        widgets = {
            'companies': forms.CheckboxSelectMultiple(),
        }


# ──── Phase 15: 오픈뱅킹 연동 ────

class BankConnectionForm(BaseForm):
    class Meta:
        model = BankConnection
        fields = ['bank_name', 'bank_code', 'account_number', 'account_holder',
                  'connection_type', 'status', 'company', 'notes']


class BankStatementImportForm(forms.Form):
    """은행 명세서 가져오기"""
    connection = forms.ModelChoiceField(
        label='은행연결',
        queryset=BankConnection.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    file = forms.FileField(
        label='명세서 파일',
        widget=forms.FileInput(attrs={'class': 'form-input'}),
    )
