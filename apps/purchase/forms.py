from django import forms
from apps.inventory.forms import BaseForm
from .models import PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem


class PurchaseOrderForm(BaseForm):
    class Meta:
        model = PurchaseOrder
        fields = [
            'po_number', 'partner', 'order_date',
            'expected_date', 'notes',
        ]
        widgets = {
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'expected_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class PurchaseOrderItemForm(BaseForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ['product', 'quantity', 'unit_price']


PurchaseOrderItemFormSet = forms.inlineformset_factory(
    PurchaseOrder, PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=3,
    can_delete=True,
)


class GoodsReceiptForm(BaseForm):
    class Meta:
        model = GoodsReceipt
        fields = ['receipt_number', 'receipt_date', 'notes']
        widgets = {
            'receipt_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class GoodsReceiptItemForm(BaseForm):
    class Meta:
        model = GoodsReceiptItem
        fields = ['po_item', 'received_quantity', 'is_inspected']
