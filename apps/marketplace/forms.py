from django import forms

from apps.core.forms import BaseForm
from apps.store_modules.registry import registry
from .models import MarketplaceConfig, MarketplaceOrder


class MarketplaceConfigForm(BaseForm):
    class Meta:
        model = MarketplaceConfig
        fields = ['shop_name', 'client_id', 'client_secret', 'notes']
        widgets = {
            'client_secret': forms.PasswordInput(
                attrs={'class': 'form-input'},
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


class ReconciliationRunForm(forms.Form):
    """정산 대사 실행 폼"""
    store_module = forms.ChoiceField(label='스토어')
    from_date = forms.DateField(
        label='시작일',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )
    to_date = forms.DateField(
        label='종료일',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['store_module'].choices = registry.choices()
        self.fields['store_module'].widget.attrs['class'] = 'form-input'
