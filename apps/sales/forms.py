from django import forms
from apps.core.forms import BaseForm
from .models import (
    Partner, Customer, CustomerPurchase,
    Order, OrderItem, Quotation, QuotationItem,
    ShippingCarrier,
)


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
        fields = ['name', 'phone', 'email', 'address', 'notes']


class CustomerPurchaseForm(BaseForm):
    class Meta:
        model = CustomerPurchase
        fields = ['product', 'serial_number', 'purchase_date', 'warranty_end']
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'warranty_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


CustomerPurchaseFormSet = forms.inlineformset_factory(
    Customer, CustomerPurchase,
    form=CustomerPurchaseForm,
    extra=1,
    can_delete=True,
)


class OrderForm(BaseForm):
    class Meta:
        model = Order
        fields = [
            'order_number', 'order_type', 'partner', 'customer',
            'assigned_to', 'order_date', 'delivery_date',
            'vat_included', 'bank_account', 'shipping_method',
            'tracking_number', 'shipping_cost', 'shipping_address', 'notes',
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
        fields = ['product', 'quantity', 'cost_price', 'unit_price']


OrderItemFormSet = forms.inlineformset_factory(
    Order, OrderItem,
    form=OrderItemForm,
    extra=3,
    can_delete=True,
)


class QuotationForm(BaseForm):
    class Meta:
        model = Quotation
        fields = [
            'quote_number', 'partner', 'customer', 'quote_date',
            'valid_until', 'vat_included', 'notes',
        ]
        widgets = {
            'quote_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class QuotationItemForm(BaseForm):
    class Meta:
        model = QuotationItem
        fields = ['product', 'quantity', 'cost_price', 'unit_price']


QuotationItemFormSet = forms.inlineformset_factory(
    Quotation, QuotationItem,
    form=QuotationItemForm,
    extra=3,
    can_delete=True,
)


class ShippingCarrierForm(BaseForm):
    class Meta:
        model = ShippingCarrier
        fields = [
            'code', 'name', 'tracking_url_template',
            'api_endpoint', 'api_key', 'is_default', 'notes',
        ]
