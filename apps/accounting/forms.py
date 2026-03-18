from django import forms
from apps.core.forms import BaseForm
from .models import (
    TaxRate, TaxInvoice, FixedCost, WithholdingTax, AccountCode, Voucher, VoucherLine,
    ApprovalRequest, ApprovalStep, AccountReceivable, AccountPayable, Payment,
)


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
        fields = ['category', 'name', 'amount', 'month', 'is_recurring', 'notes']
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


class ApprovalRequestForm(BaseForm):
    class Meta:
        model = ApprovalRequest
        fields = ['request_number', 'category', 'title', 'content', 'amount', 'approver', 'notes']


class ApprovalActionForm(forms.Form):
    """결재 승인/반려 폼"""
    action = forms.ChoiceField(choices=[('approve', '승인'), ('reject', '반려')])
    reject_reason = forms.CharField(
        label='반려사유', required=False,
        widget=forms.Textarea(attrs={'class': 'form-input h-24', 'rows': 3}),
    )


class ApprovalStepForm(BaseForm):
    class Meta:
        model = ApprovalStep
        fields = ['step_order', 'approver']


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


class PaymentForm(BaseForm):
    class Meta:
        model = Payment
        fields = ['payment_number', 'payment_type', 'partner', 'amount', 'payment_date', 'payment_method', 'reference', 'notes']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }
