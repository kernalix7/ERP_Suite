from django import forms
from apps.core.forms import BaseForm
from .models import ProductRegistration


class ProductRegistrationForm(BaseForm):
    class Meta:
        model = ProductRegistration
        fields = [
            'serial_number', 'product', 'customer', 'customer_name', 'phone', 'email',
            'purchase_date', 'purchase_channel', 'warranty_start', 'warranty_end',
            'photo', 'is_verified', 'notes',
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'warranty_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'warranty_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get('customer')
        if customer and not cleaned.get('customer_name'):
            cleaned['customer_name'] = customer.name
        if customer and not cleaned.get('phone'):
            cleaned['phone'] = customer.phone or ''
        if customer and not cleaned.get('email'):
            cleaned['email'] = customer.email or ''
        return cleaned
