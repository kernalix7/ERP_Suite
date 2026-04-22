import json

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
            'approver', 'cooperator', 'approval_type', 'notes',
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
    fields=['step_order', 'approver', 'parallel_mode'],
    extra=1,
    can_delete=True,
    widgets={
        'step_order': forms.NumberInput(attrs={
            'class': 'form-input w-20 text-center',
            'min': '1',
        }),
        'parallel_mode': forms.Select(attrs={
            'class': 'form-input',
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
        fields = [
            'name', 'description', 'steps', 'is_default',
            'condition', 'auto_apply', 'priority',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'steps': forms.Textarea(attrs={
                'class': 'form-input font-mono', 'rows': 6,
                'placeholder': (
                    '[{"approver_id": 1, "role": "팀장", "order": 1, "mode": "SEQUENTIAL"},\n'
                    ' {"approver_id": 5, "order": 2, "mode": "ALL"}]'
                ),
            }),
            'condition': forms.Textarea(attrs={
                'class': 'form-input font-mono', 'rows': 4,
                'placeholder': (
                    '{"category": ["PURCHASE","EXPENSE"], '
                    '"amount_min": 0, "amount_max": 10000000, '
                    '"department_ids": [1,2]}'
                ),
            }),
            'priority': forms.NumberInput(attrs={
                'class': 'form-input w-24', 'min': '0',
            }),
        }

    def clean_steps(self):
        val = self.cleaned_data.get('steps')
        if val is None or val == '':
            return []
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError(f'JSON 파싱 실패: {exc}')
            if not isinstance(parsed, list):
                raise forms.ValidationError('steps는 JSON 배열이어야 합니다.')
            return parsed
        raise forms.ValidationError('steps 형식 오류')

    def clean_condition(self):
        val = self.cleaned_data.get('condition')
        if val is None or val == '':
            return {}
        if isinstance(val, dict):
            return val
        if isinstance(val, str):
            try:
                parsed = json.loads(val)
            except (TypeError, ValueError) as exc:
                raise forms.ValidationError(f'JSON 파싱 실패: {exc}')
            if not isinstance(parsed, dict):
                raise forms.ValidationError('condition은 JSON 객체여야 합니다.')
            return parsed
        raise forms.ValidationError('condition 형식 오류')


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
