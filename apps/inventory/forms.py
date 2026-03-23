from django import forms
from django.core.validators import FileExtensionValidator
from apps.core.forms import BaseForm
from .models import Category, Product, Warehouse, StockMovement, StockTransfer

MAX_UPLOAD_SIZE = 5 * 1024 * 1024  # 5MB


class ProductForm(BaseForm):
    image = forms.ImageField(
        label='이미지', required=False,
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png', 'gif', 'webp'])],
        help_text='최대 5MB, JPG/PNG/GIF/WebP만 허용',
    )

    class Meta:
        model = Product
        fields = [
            'code', 'name', 'product_type', 'category', 'unit',
            'unit_price', 'cost_price', 'valuation_method',
            'safety_stock', 'specification', 'image', 'notes',
        ]

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size'):
            if image.size > MAX_UPLOAD_SIZE:
                raise forms.ValidationError('파일 크기가 5MB를 초과합니다.')
        return image


class CategoryForm(BaseForm):
    class Meta:
        model = Category
        fields = ['name', 'parent', 'notes']


class WarehouseForm(BaseForm):
    class Meta:
        model = Warehouse
        fields = ['code', 'name', 'location', 'notes']


class StockMovementForm(BaseForm):
    class Meta:
        model = StockMovement
        fields = [
            'movement_number', 'movement_type', 'product', 'warehouse',
            'quantity', 'unit_price', 'movement_date', 'reference', 'notes',
        ]
        widgets = {
            'movement_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 제품 select에 data-unit 속성 추가
        choices = [('', '---------')]
        for p in Product.objects.filter(is_active=True).order_by('name'):
            choices.append((p.pk, p.name))
        self.fields['product'].widget = forms.Select(
            attrs={'class': 'form-input', 'id': 'id_product'},
        )
        self.fields['product'].widget.choices = choices
        # 단위 매핑 (template에서 json_script로 출력)
        self.product_units_json = {
            str(p.pk): p.unit or ''
            for p in Product.objects.filter(is_active=True)
        }


class StockTransferForm(BaseForm):
    class Meta:
        model = StockTransfer
        fields = ['transfer_number', 'from_warehouse', 'to_warehouse', 'product', 'quantity', 'transfer_date', 'notes']
        widgets = {
            'transfer_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.product_units_json = {
            str(p.pk): p.unit or ''
            for p in Product.objects.filter(is_active=True)
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('from_warehouse') and cleaned.get('to_warehouse'):
            if cleaned['from_warehouse'] == cleaned['to_warehouse']:
                raise forms.ValidationError('출발창고와 도착창고가 같을 수 없습니다.')
        return cleaned
