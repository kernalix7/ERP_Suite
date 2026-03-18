from django import forms
from apps.core.forms import BaseForm
from .models import Partner, Customer, Order, OrderItem


class PartnerForm(BaseForm):
    class Meta:
        model = Partner
        fields = [
            'code', 'name', 'partner_type', 'business_number',
            'representative', 'contact_name', 'phone', 'email', 'address', 'notes',
        ]


class CustomerForm(BaseForm):
    class Meta:
        model = Customer
        fields = [
            'name', 'phone', 'email', 'address',
            'purchase_date', 'product', 'serial_number', 'warranty_end', 'notes',
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'warranty_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class OrderForm(BaseForm):
    class Meta:
        model = Order
        fields = [
            'order_number', 'partner', 'customer', 'order_date',
            'delivery_date', 'shipping_address', 'notes',
        ]
        widgets = {
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class OrderStatusForm(BaseForm):
    """매니저 이상만 사용 가능한 상태 변경 폼"""
    class Meta:
        model = Order
        fields = ['status']


class OrderItemForm(BaseForm):
    class Meta:
        model = OrderItem
        fields = ['product', 'quantity', 'unit_price']


OrderItemFormSet = forms.inlineformset_factory(
    Order, OrderItem,
    form=OrderItemForm,
    extra=3,
    can_delete=True,
)
