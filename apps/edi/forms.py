from django import forms

from apps.core.forms import BaseForm

from .models import (
    EDIDocumentType,
    EDIMapping,
    EDIPartner,
    EDISchedule,
    EDITransaction,
)


class EDIPartnerForm(BaseForm):
    class Meta:
        model = EDIPartner
        fields = ['partner', 'edi_id', 'protocol', 'connection_settings', 'notes']
        widgets = {
            'connection_settings': forms.Textarea(attrs={'rows': 4,
                                                         'placeholder': '{"host": "", "port": 22, "username": ""}'}),
        }


class EDIDocumentTypeForm(BaseForm):
    class Meta:
        model = EDIDocumentType
        fields = ['code', 'name', 'direction', 'format', 'mapping_template', 'notes']
        widgets = {
            'mapping_template': forms.Textarea(attrs={'rows': 4}),
        }


class EDITransactionFilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[('', '전체 상태')] + list(EDITransaction.Status.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-input w-auto'}),
    )
    direction = forms.ChoiceField(
        choices=[('', '전체 방향')] + list(EDITransaction.Direction.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-input w-auto'}),
    )


class EDIMappingForm(BaseForm):
    class Meta:
        model = EDIMapping
        fields = ['document_type', 'source_field', 'target_model', 'target_field',
                  'transformation', 'notes']


class EDIScheduleForm(BaseForm):
    class Meta:
        model = EDISchedule
        fields = ['partner', 'document_type', 'frequency', 'next_run', 'notes']
        widgets = {
            'next_run': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
