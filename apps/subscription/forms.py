from django import forms

from apps.core.forms import BaseForm

from .models import (
    BillingRecord,
    Subscription,
    SubscriptionItem,
    SubscriptionPlan,
    UsageRecord,
)


class SubscriptionPlanForm(BaseForm):
    class Meta:
        model = SubscriptionPlan
        fields = ['name', 'code', 'description', 'billing_cycle', 'price',
                  'currency', 'features', 'notes']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'features': forms.Textarea(attrs={'rows': 3,
                                              'placeholder': '["기능1", "기능2"]'}),
        }


class SubscriptionForm(BaseForm):
    class Meta:
        model = Subscription
        fields = ['partner', 'plan', 'status', 'start_date', 'end_date',
                  'next_billing_date', 'auto_renew', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'next_billing_date': forms.DateInput(attrs={'type': 'date'}),
        }


class SubscriptionItemForm(BaseForm):
    class Meta:
        model = SubscriptionItem
        fields = ['product', 'quantity', 'unit_price', 'notes']


class BillingRecordForm(BaseForm):
    class Meta:
        model = BillingRecord
        fields = ['billing_date', 'amount', 'notes']
        widgets = {
            'billing_date': forms.DateInput(attrs={'type': 'date'}),
        }


class UsageRecordForm(BaseForm):
    class Meta:
        model = UsageRecord
        fields = ['metric_name', 'quantity', 'recorded_date', 'notes']
        widgets = {
            'recorded_date': forms.DateInput(attrs={'type': 'date'}),
        }
