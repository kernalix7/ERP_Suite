from django import forms

from apps.core.forms import BaseForm
from .models import BOMRevision, Drawing, ECNItem, EngineeringChangeNotice, ProductVersion


class ProductVersionForm(BaseForm):
    class Meta:
        model = ProductVersion
        fields = ['product', 'version_number', 'status', 'effective_date', 'description', 'notes']
        widgets = {
            'effective_date': forms.DateInput(attrs={'type': 'date'}),
        }


class BOMRevisionForm(BaseForm):
    class Meta:
        model = BOMRevision
        fields = ['bom', 'revision_number', 'status', 'change_reason', 'notes']


class EngineeringChangeNoticeForm(BaseForm):
    class Meta:
        model = EngineeringChangeNotice
        fields = ['title', 'description', 'priority', 'affected_products', 'target_date', 'notes']
        widgets = {
            'target_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ECNItemForm(BaseForm):
    class Meta:
        model = ECNItem
        fields = ['change_type', 'product', 'description', 'before_spec', 'after_spec']


class DrawingForm(BaseForm):
    class Meta:
        model = Drawing
        fields = ['product', 'version', 'file', 'drawing_number', 'revision', 'description', 'format', 'notes']
