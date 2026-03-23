from django import forms
from apps.core.forms import BaseForm
from .models import (
    Currency, ExchangeRate,
    TaxRate, TaxInvoice, FixedCost, WithholdingTax, AccountCode, Voucher, VoucherLine,
    AccountReceivable, AccountPayable, Payment, BankAccount,
    AccountTransfer, PaymentDistribution,
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
        fields = ['account', 'debit', 'credit', 'description']


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
        fields = ['partner', 'invoice', 'amount', 'paid_amount', 'due_date', 'status', 'notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class BankAccountForm(BaseForm):
    class Meta:
        model = BankAccount
        fields = [
            'name', 'account_type', 'owner', 'bank', 'account_number',
            'account_code', 'opening_balance', 'is_default', 'notes',
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
