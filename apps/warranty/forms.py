from django import forms
from apps.core.forms import BaseForm
from .models import ProductRegistration


class ProductRegistrationForm(BaseForm):
    class Meta:
        model = ProductRegistration
        fields = [
            'serial_number', 'product', 'customer_name', 'phone', 'email',
            'purchase_date', 'purchase_channel', 'warranty_start', 'warranty_end',
            'photo', 'is_verified', 'notes',
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'warranty_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'warranty_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }
