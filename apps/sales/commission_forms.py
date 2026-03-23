from django import forms
from apps.core.forms import BaseForm
from .commission import CommissionRate, CommissionRecord


class CommissionRateForm(BaseForm):
    class Meta:
        model = CommissionRate
        fields = [
            'partner', 'product', 'name',
            'calc_type', 'rate', 'fixed_amount', 'notes',
        ]


class CommissionRateInlineForm(BaseForm):
    class Meta:
        model = CommissionRate
        fields = ['name', 'product', 'calc_type', 'rate', 'fixed_amount']


CommissionRateInlineFormSet = forms.inlineformset_factory(
    CommissionRate.partner.field.related_model,
    CommissionRate,
    form=CommissionRateInlineForm,
    fields=['name', 'product', 'calc_type', 'rate', 'fixed_amount'],
    extra=1,
    can_delete=True,
)


class CommissionRecordForm(BaseForm):
    class Meta:
        model = CommissionRecord
        fields = [
            'partner', 'order', 'order_amount', 'commission_rate',
            'commission_amount', 'status', 'settled_date', 'notes',
        ]
        widgets = {
            'settled_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }
