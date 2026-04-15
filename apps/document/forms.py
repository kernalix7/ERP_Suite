from django import forms

from apps.core.forms import BaseForm
from .models import (
    Contract, ContractMilestone, Document, DocumentApproval,
    DocumentCategory, DocumentVersion,
)


class DocumentCategoryForm(BaseForm):
    class Meta:
        model = DocumentCategory
        fields = ['name', 'code', 'description', 'retention_years', 'parent', 'notes']


class DocumentForm(BaseForm):
    class Meta:
        model = Document
        fields = [
            'title', 'category', 'content_file', 'file_type',
            'status', 'department', 'access_level', 'tags',
            'expiry_date', 'notes',
        ]
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'tags': forms.TextInput(attrs={'placeholder': '태그를 JSON 배열로 입력 (예: ["계약","법률"])'}),
        }


class DocumentVersionForm(BaseForm):
    class Meta:
        model = DocumentVersion
        fields = ['file', 'change_summary']


class DocumentApprovalForm(BaseForm):
    class Meta:
        model = DocumentApproval
        fields = ['approver', 'comment']


class DocumentApprovalActionForm(forms.Form):
    """결재 승인/반려 액션 폼"""
    comment = forms.CharField(
        label='의견', widget=forms.Textarea(attrs={'class': 'form-input h-24', 'rows': 3}),
        required=False,
    )


class ContractForm(BaseForm):
    class Meta:
        model = Contract
        fields = [
            'title', 'contract_type', 'partner', 'start_date', 'end_date',
            'value', 'status', 'auto_renew', 'renewal_notice_days',
            'signed_file', 'signed_date', 'signed_by', 'notes',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'signed_date': forms.DateInput(attrs={'type': 'date'}),
        }


class ContractMilestoneForm(BaseForm):
    class Meta:
        model = ContractMilestone
        fields = ['title', 'due_date', 'amount', 'status', 'notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }
