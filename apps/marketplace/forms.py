from django import forms

from apps.core.forms import BaseForm
from .models import MarketplaceConfig, MarketplaceOrder


class MarketplaceConfigForm(BaseForm):
    class Meta:
        model = MarketplaceConfig
        fields = ['shop_name', 'client_id', 'client_secret', 'notes']
        widgets = {
            'client_secret': forms.PasswordInput(
                attrs={'class': 'form-input'},
                render_value=True,
            ),
        }


class MarketplaceOrderForm(BaseForm):
    class Meta:
        model = MarketplaceOrder
        fields = [
            'store_order_id', 'product_name', 'option_name', 'quantity',
            'price', 'buyer_name', 'buyer_phone', 'receiver_name',
            'receiver_phone', 'receiver_address', 'status', 'ordered_at', 'notes',
        ]
        widgets = {
            'ordered_at': forms.DateTimeInput(
                attrs={'type': 'datetime-local',
                       'class': 'form-input'}
            ),
        }
