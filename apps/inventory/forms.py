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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['code'].required = False
        self.fields['code'].help_text = '비워두면 유형에 따라 자동 생성됩니다 (예: FIN-0001)'

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip()
        if not code:
            product_type = self.data.get('product_type', 'FINISHED')
            code = Product.generate_next_code(product_type)
        return code

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and hasattr(image, 'size'):
            if image.size > MAX_UPLOAD_SIZE:
                raise forms.ValidationError('파일 크기가 5MB를 초과합니다.')
        return image


class CategoryForm(BaseForm):
    class Meta:
        model = Category
        fields = ['code', 'name', 'parent', 'notes']


class WarehouseForm(BaseForm):
    class Meta:
        model = Warehouse
        fields = ['code', 'name', 'address', 'location', 'notes']


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
        # 제품 select에 data-unit 속성 추가 (단일 쿼리로 통합)
        active_products = list(Product.objects.filter(is_active=True).order_by('name'))
        choices = [('', '---------')]
        for p in active_products:
            choices.append((p.pk, p.name))
        self.fields['product'].widget = forms.Select(
            attrs={'class': 'form-input', 'id': 'id_product'},
        )
        self.fields['product'].widget.choices = choices
        # 단위 매핑 (template에서 json_script로 출력)
        self.product_units_json = {
            str(p.pk): p.unit or ''
            for p in active_products
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


class StockInForm(BaseForm):
    """입고 전용 폼 — IN, ADJ_PLUS, PROD_IN, RETURN 유형만 허용"""
    INBOUND_TYPES = [
        ('IN', '입고'),
        ('ADJ_PLUS', '재고조정(+)'),
        ('PROD_IN', '생산입고'),
        ('RETURN', '반품'),
    ]

    class Meta:
        model = StockMovement
        fields = [
            'movement_type', 'product', 'warehouse',
            'quantity', 'unit_price', 'movement_date', 'reference', 'notes',
        ]
        widgets = {
            'movement_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['movement_type'].choices = self.INBOUND_TYPES
        self.fields['movement_type'].initial = 'IN'
        self.product_units_json = {
            str(p.pk): p.unit or ''
            for p in Product.objects.filter(is_active=True)
        }


class StockOutForm(BaseForm):
    """출고 전용 폼 — OUT, ADJ_MINUS, PROD_OUT 유형만 허용"""
    OUTBOUND_TYPES = [
        ('OUT', '출고'),
        ('ADJ_MINUS', '재고조정(-)'),
        ('PROD_OUT', '생산출고'),
    ]

    class Meta:
        model = StockMovement
        fields = [
            'movement_type', 'product', 'warehouse',
            'quantity', 'unit_price', 'movement_date', 'reference', 'notes',
        ]
        widgets = {
            'movement_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['movement_type'].choices = self.OUTBOUND_TYPES
        self.fields['movement_type'].initial = 'OUT'
        self.product_units_json = {
            str(p.pk): p.unit or ''
            for p in Product.objects.filter(is_active=True)
        }
