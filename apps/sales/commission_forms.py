from django import forms
from apps.core.forms import BaseForm
from .commission import CommissionRate, CommissionRecord


class CommissionRateForm(BaseForm):
    class Meta:
        model = CommissionRate
        fields = ['partner', 'product', 'rate', 'notes']


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
