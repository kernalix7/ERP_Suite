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
