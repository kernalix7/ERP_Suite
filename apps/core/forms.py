from django import forms


class BaseForm(forms.ModelForm):
    """공통 BaseForm - Tailwind CSS 클래스 자동 적용"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault('class', 'form-input h-24')
                field.widget.attrs.setdefault('rows', 3)
            elif isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs.setdefault('class', 'form-input')
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-checkbox')
            else:
                field.widget.attrs.setdefault('class', 'form-input')


class SystemConfigForm(BaseForm):
    """시스템 설정 폼"""

    class Meta:
        from apps.core.system_config import SystemConfig
        model = SystemConfig
        fields = ['category', 'key', 'value', 'display_name', 'description',
                  'is_secret', 'value_type']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 민감정보 수정 시 기존값은 비워서 표시 (placeholder로 안내)
        if self.instance and self.instance.pk and self.instance.is_secret:
            self.fields['value'].required = False
            self.fields['value'].widget.attrs['placeholder'] = '변경하려면 새 값을 입력하세요'

    def clean_value(self):
        value = self.cleaned_data.get('value')
        # is_secret이고 value가 비어있으면 기존값 유지
        if not value and self.instance and self.instance.pk and self.instance.is_secret:
            return self.instance.value
        return value
