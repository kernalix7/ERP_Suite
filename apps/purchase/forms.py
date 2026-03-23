from django import forms
from apps.core.forms import BaseForm
from .models import PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem


class PurchaseOrderForm(BaseForm):
    class Meta:
        model = PurchaseOrder
        fields = [
            'po_number', 'partner', 'order_date',
            'expected_date', 'vat_included',
            'approval_request', 'attachment', 'notes',
        ]
        widgets = {
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'expected_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class PurchaseOrderItemForm(BaseForm):
    class Meta:
        model = PurchaseOrderItem
        fields = ['product', 'quantity', 'amount', 'unit_price', 'receipt_file']
        widgets = {
            'amount': forms.TextInput(attrs={
                'class': 'form-input w-full money-input',
                'inputmode': 'numeric',
                'placeholder': '금액',
            }),
            'unit_price': forms.TextInput(attrs={
                'class': 'form-input w-full money-input',
                'inputmode': 'numeric',
                'placeholder': '단가',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # VAT 포함 모드 수정 시: 공급가액 → 합계금액(VAT포함)으로 복원
        if (self.instance.pk
                and hasattr(self.instance, 'purchase_order')
                and self.instance.purchase_order.vat_included):
            self.initial['amount'] = int(
                self.instance.amount + self.instance.tax_amount
            )

    def clean_amount(self):
        val = self.data.get(self.add_prefix('amount'), '0')
        return int(str(val).replace(',', '').strip() or '0')

    def clean_unit_price(self):
        val = self.data.get(self.add_prefix('unit_price'), '0')
        return int(str(val).replace(',', '').strip() or '0')


PurchaseOrderItemFormSet = forms.inlineformset_factory(
    PurchaseOrder, PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=3,
    can_delete=True,
)


class GoodsReceiptForm(BaseForm):
    class Meta:
        model = GoodsReceipt
        fields = ['receipt_number', 'warehouse', 'receipt_date', 'notes']
        widgets = {
            'receipt_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class GoodsReceiptItemForm(BaseForm):
    class Meta:
        model = GoodsReceiptItem
        fields = ['po_item', 'received_quantity', 'is_inspected']
