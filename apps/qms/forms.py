from django import forms

from apps.core.forms import BaseForm
from .models import AuditFinding, CAPA, InternalAudit, ISODocument, NonConformance


class NonConformanceForm(BaseForm):
    class Meta:
        model = NonConformance
        fields = ['title', 'description', 'source', 'severity', 'product', 'notes']


class NonConformanceResolveForm(BaseForm):
    class Meta:
        model = NonConformance
        fields = ['root_cause', 'corrective_action']


class CAPAForm(BaseForm):
    class Meta:
        model = CAPA
        fields = ['nc', 'type', 'description', 'assigned_to', 'due_date', 'notes']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }


class CAPAVerifyForm(BaseForm):
    class Meta:
        model = CAPA
        fields = ['effectiveness_check']


class InternalAuditForm(BaseForm):
    class Meta:
        model = InternalAudit
        fields = ['title', 'audit_type', 'scope', 'auditor', 'audit_date', 'notes']
        widgets = {
            'audit_date': forms.DateInput(attrs={'type': 'date'}),
        }


class AuditFindingForm(BaseForm):
    class Meta:
        model = AuditFinding
        fields = ['finding_type', 'description', 'capa']


class ISODocumentForm(BaseForm):
    class Meta:
        model = ISODocument
        fields = [
            'document_number', 'title', 'category', 'revision',
            'effective_date', 'review_date', 'content', 'status', 'notes',
        ]
        widgets = {
            'effective_date': forms.DateInput(attrs={'type': 'date'}),
            'review_date': forms.DateInput(attrs={'type': 'date'}),
        }
