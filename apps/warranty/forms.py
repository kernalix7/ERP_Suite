from django import forms
from apps.core.forms import BaseForm
from .models import ProductRegistration


class ProductRegistrationForm(BaseForm):
    class Meta:
        model = ProductRegistration
        fields = [
            'serial_number', 'product', 'customer',
            'custom_info', 'customer_name', 'phone', 'email',
            'purchase_date', 'purchase_channel',
            'warranty_start', 'warranty_end',
            'warranty_days', 'verified_warranty_days',
            'photo', 'is_verified', 'notes',
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'warranty_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'warranty_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-input', 'readonly': 'readonly'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # warranty_end는 자동 계산되므로 필수 아님 (save()에서 계산)
        self.fields['warranty_end'].required = False
        self.fields['warranty_end'].help_text = '보증시작일 + AS기간에서 자동 계산됩니다.'
        # 신규 등록 시 SystemConfig에서 기본값 로드
        if not self.instance.pk:
            try:
                from apps.core.system_config import SystemConfig
                days = SystemConfig.get_value('WARRANTY', 'default_warranty_days')
                if days:
                    self.initial.setdefault('warranty_days', int(days))
                v_days = SystemConfig.get_value('WARRANTY', 'default_verified_warranty_days')
                if v_days:
                    self.initial.setdefault('verified_warranty_days', int(v_days))
            except Exception:
                pass

    def clean(self):
        cleaned = super().clean()
        customer = cleaned.get('customer')
        custom_info = cleaned.get('custom_info', False)
        # custom_info=False (고객 정보 그대로 사용) -> 고객 정보에서 복사
        if customer and not custom_info:
            cleaned['customer_name'] = customer.name
            cleaned['phone'] = customer.phone or ''
            cleaned['email'] = customer.email or ''
        return cleaned
