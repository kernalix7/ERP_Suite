from django import forms
from apps.core.forms import BaseForm
from apps.approval.models import ApprovalRequest, ApprovalStep, ApprovalLineTemplate, ApprovalDelegation


class ApprovalRequestForm(BaseForm):
    amount = forms.CharField(
        label='금액', required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input money-input',
            'inputmode': 'numeric', 'placeholder': '0',
        }),
    )
    attachments = forms.FileField(
        label='첨부파일',
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-input',
            'allow_multiple_selected': True,
        }),
    )

    class Meta:
        model = ApprovalRequest
        fields = [
            'request_number', 'category', 'urgency', 'department',
            'title', 'purpose', 'content', 'amount', 'expected_date',
            'approver', 'cooperator', 'notes',
        ]
        widgets = {
            'purpose': forms.Textarea(attrs={
                'class': 'form-input', 'rows': 3,
                'placeholder': '품의를 올리는 목적 또는 사유를 입력하세요',
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-input', 'rows': 6,
                'placeholder': '세부 내용을 입력하세요'
                ' (품목, 수량, 규격, 업체 등)',
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-input', 'rows': 2,
                'placeholder': '기타 참고사항',
            }),
            'expected_date': forms.DateInput(attrs={
                'type': 'date', 'class': 'form-input',
            }),
        }

    def clean_amount(self):
        val = self.cleaned_data.get('amount', '0')
        val = str(val).replace(',', '').strip() or '0'
        return int(val)


ApprovalStepFormSet = forms.inlineformset_factory(
    ApprovalRequest, ApprovalStep,
    fields=['step_order', 'approver'],
    extra=1,
    can_delete=True,
    widgets={
        'step_order': forms.NumberInput(attrs={
            'class': 'form-input w-20 text-center',
            'min': '1',
        }),
    },
)


class ApprovalActionForm(forms.Form):
    """결재 승인/반려 폼"""
    action = forms.ChoiceField(
        choices=[('approve', '승인'), ('reject', '반려')],
    )
    reject_reason = forms.CharField(
        label='반려사유', required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input h-24', 'rows': 3,
        }),
    )


class ApprovalLineTemplateForm(BaseForm):
    class Meta:
        model = ApprovalLineTemplate
        fields = ['name', 'description', 'steps', 'is_default']
        widgets = {
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'steps': forms.Textarea(attrs={
                'class': 'form-input font-mono', 'rows': 6,
                'placeholder': '[{"approver_id": 1, "role": "팀장", "order": 1}]',
            }),
        }


class ApprovalDelegationForm(BaseForm):
    class Meta:
        model = ApprovalDelegation
        fields = ['delegate', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'reason': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('종료일은 시작일 이후여야 합니다.')
        return cleaned
