from django import forms
from apps.core.forms import BaseForm
from .models import PurchaseOrder, PurchaseOrderItem, GoodsReceipt, GoodsReceiptItem, RFQ, RFQItem, RFQResponse, VendorScore


class PurchaseOrderForm(BaseForm):
    class Meta:
        model = PurchaseOrder
        fields = [
            'po_number', 'partner', 'order_date',
            'expected_date', 'is_taxable', 'vat_included',
            'vat_deduction_type',
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
        val = self.data.get(self.add_prefix('amount'), '')
        cleaned = str(val).replace(',', '').strip()
        return int(cleaned) if cleaned else 0

    def clean_unit_price(self):
        val = self.data.get(self.add_prefix('unit_price'), '')
        cleaned = str(val).replace(',', '').strip()
        return int(cleaned) if cleaned else 0

    def has_changed(self):
        """제품 미선택 시 빈 행으로 간주 — 유효성 검사 건너뛰기"""
        product = self.data.get(self.add_prefix('product'), '')
        if not product:
            return False
        return super().has_changed()


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


class RFQForm(BaseForm):
    class Meta:
        model = RFQ
        fields = ['rfq_number', 'title', 'status', 'due_date', 'notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }


class RFQItemForm(BaseForm):
    class Meta:
        model = RFQItem
        fields = ['product', 'quantity', 'specifications']


RFQItemFormSet = forms.inlineformset_factory(
    RFQ, RFQItem,
    form=RFQItemForm,
    extra=3,
    can_delete=True,
)


class RFQResponseForm(BaseForm):
    class Meta:
        model = RFQResponse
        fields = ['partner', 'response_date', 'total_amount', 'delivery_days', 'notes']
        widgets = {
            'response_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'total_amount': forms.TextInput(attrs={
                'class': 'form-input w-full money-input',
                'inputmode': 'numeric',
            }),
        }

    def clean_total_amount(self):
        val = self.data.get(self.add_prefix('total_amount'), '')
        cleaned = str(val).replace(',', '').strip()
        return int(cleaned) if cleaned else 0


class VendorScoreForm(BaseForm):
    class Meta:
        model = VendorScore
        fields = [
            'partner', 'evaluation_date',
            'delivery_score', 'quality_score', 'price_score', 'service_score',
            'notes',
        ]
        widgets = {
            'evaluation_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }
