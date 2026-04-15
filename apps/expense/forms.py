from django import forms

from apps.core.forms import BaseForm
from .models import (
    CardTransaction, CorporateCard, ExpenseCategory, ExpenseClaim,
    ExpenseItem, ExpensePolicy,
)


class ExpensePolicyForm(BaseForm):
    class Meta:
        model = ExpensePolicy
        fields = [
            'name', 'category', 'max_amount', 'requires_receipt',
            'requires_approval', 'daily_limit', 'monthly_limit',
            'applicable_roles', 'notes',
        ]
        widgets = {
            'applicable_roles': forms.TextInput(attrs={
                'placeholder': '["대리","과장","부장"]',
            }),
        }


class ExpenseCategoryForm(BaseForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'code', 'account_code', 'parent', 'policy', 'notes']


class ExpenseClaimForm(BaseForm):
    class Meta:
        model = ExpenseClaim
        fields = ['title', 'notes']


class ExpenseItemForm(BaseForm):
    class Meta:
        model = ExpenseItem
        fields = [
            'category', 'date', 'description', 'amount', 'tax_amount',
            'receipt_file', 'is_corporate_card', 'card_transaction_id',
            'merchant_name', 'notes',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }


class ExpenseItemInlineFormSet(forms.BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for form in self.forms:
            for field in form.fields.values():
                if isinstance(field.widget, forms.Textarea):
                    field.widget.attrs.setdefault('class', 'form-input h-24')
                elif isinstance(field.widget, forms.CheckboxInput):
                    field.widget.attrs.setdefault('class', 'form-checkbox')
                else:
                    field.widget.attrs.setdefault('class', 'form-input')


ExpenseItemFormSet = forms.inlineformset_factory(
    ExpenseClaim, ExpenseItem,
    form=ExpenseItemForm,
    formset=ExpenseItemInlineFormSet,
    extra=1, can_delete=True,
)


class CorporateCardForm(BaseForm):
    class Meta:
        model = CorporateCard
        fields = ['card_number_last4', 'employee', 'card_type', 'monthly_limit', 'notes']


class CardTransactionMatchForm(forms.Form):
    expense_item = forms.ModelChoiceField(
        label='경비 항목',
        queryset=ExpenseItem.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-input'}),
        required=False,
    )
