from django import forms
from apps.core.forms import BaseForm
from .models import (
    Partner, Customer, CustomerPurchase,
    Order, OrderItem, Quotation, QuotationItem,
    ShippingCarrier, PriceRule,
    CustomerTier, SalesTarget,
    SalesLead, LeadActivity, CustomerSatisfaction,
)


class PartnerForm(BaseForm):
    class Meta:
        model = Partner
        fields = [
            'code', 'name', 'partner_type', 'business_number',
            'representative', 'contact_name', 'phone', 'email',
            'address', 'address_road', 'address_detail',
            'bank_name', 'bank_account', 'bank_holder',
            'default_bank_account', 'commission_bank_account',
            'credit_limit', 'credit_used', 'tier',
            'approval_status', 'store_module', 'notes',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].required = False
        self.fields['code'].help_text = '비워두면 유형에 따라 자동 생성됩니다 (예: CUS-001)'
        # store_module 드롭다운
        from apps.store_modules.registry import registry
        self.fields['store_module'].widget = forms.Select(
            choices=registry.choices(),
            attrs={'class': 'form-select'},
        )
        # 기존 계좌 선택 드롭다운
        from apps.accounting.models import BankAccount
        active_accounts = BankAccount.objects.filter(is_active=True)
        self.fields['default_bank_account'].queryset = active_accounts
        self.fields['commission_bank_account'].queryset = active_accounts
        # 거래처 유형에 따라 라벨 변경
        partner_type = (
            self.instance.partner_type if self.instance.pk
            else self.data.get('partner_type', 'CUSTOMER') if self.is_bound
            else 'CUSTOMER'
        )
        if partner_type == 'SUPPLIER':
            self.fields['default_bank_account'].label = '거래처 출금계좌'
            self.fields['default_bank_account'].help_text = '이 공급처에 대금 지급 시 사용할 계좌'
        else:
            self.fields['default_bank_account'].label = '거래처 입금계좌'
            self.fields['default_bank_account'].help_text = '이 고객의 주문 입금을 받을 계좌'

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip()
        if not code:
            partner_type = self.data.get('partner_type', 'CUSTOMER')
            code = Partner.generate_next_code(partner_type)
        return code


class CustomerForm(BaseForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'email', 'address', 'address_road', 'address_detail', 'notes']


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
            'assigned_to', 'order_date', 'accounting_date', 'delivery_date',
            'sales_channel', 'payment_method', 'tax_type',
            'vat_included', 'bank_account', 'shipping_charged', 'shipping_cost',
            'shipping_address', 'shipping_address_road', 'shipping_address_detail',
            'notes',
        ]
        widgets = {
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'accounting_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 신규 주문 + 거래처 지정 시 → 거래처 기본 계좌 자동 설정
        if not self.instance.pk and not self.initial.get('bank_account'):
            partner_id = self.data.get('partner') if self.is_bound else None
            if partner_id:
                try:
                    partner = Partner.objects.get(pk=partner_id)
                    if partner.default_bank_account_id:
                        self.initial['bank_account'] = partner.default_bank_account_id
                except Partner.DoesNotExist:
                    pass


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


class ReturnOrderForm(BaseForm):
    class Meta:
        model = Order
        fields = ['return_reason', 'notes']
        widgets = {
            'return_reason': forms.Textarea(attrs={'rows': 3}),
        }


class PriceRuleForm(BaseForm):
    class Meta:
        model = PriceRule
        fields = [
            'product', 'partner', 'customer', 'min_quantity',
            'unit_price', 'discount_rate', 'valid_from', 'valid_to',
            'priority', 'notes',
        ]
        widgets = {
            'valid_from': forms.DateInput(attrs={'type': 'date'}),
            'valid_to': forms.DateInput(attrs={'type': 'date'}),
        }


class CustomerTierForm(BaseForm):
    class Meta:
        model = CustomerTier
        fields = [
            'name', 'code', 'discount_rate', 'min_annual_purchase',
            'benefits', 'sort_order', 'color',
        ]


class SalesTargetForm(BaseForm):
    class Meta:
        model = SalesTarget
        fields = ['salesperson', 'year', 'quarter', 'target_amount']


class SalesLeadForm(BaseForm):
    class Meta:
        model = SalesLead
        fields = [
            'company_name', 'contact_name', 'contact_email', 'contact_phone',
            'source', 'status', 'assigned_to',
            'expected_amount', 'expected_close_date', 'lost_reason',
        ]
        widgets = {
            'expected_close_date': forms.DateInput(attrs={'type': 'date'}),
            'lost_reason': forms.Textarea(attrs={'rows': 3}),
        }


class LeadActivityForm(BaseForm):
    class Meta:
        model = LeadActivity
        fields = ['activity_type', 'description', 'activity_date']
        widgets = {
            'activity_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
            ),
        }


class CustomerSatisfactionForm(BaseForm):
    class Meta:
        model = CustomerSatisfaction
        fields = [
            'order', 'partner', 'score', 'nps_score',
            'feedback', 'survey_date', 'category',
        ]
        widgets = {
            'survey_date': forms.DateInput(attrs={'type': 'date'}),
            'feedback': forms.Textarea(attrs={'rows': 3}),
        }
