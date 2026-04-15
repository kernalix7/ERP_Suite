from django import forms

from apps.core.forms import BaseForm

from .models import (
    EscalationRule,
    SLA,
    Ticket,
    TicketAttachment,
    TicketCategory,
    TicketComment,
)


class SLAForm(BaseForm):
    class Meta:
        model = SLA
        fields = ['name', 'response_time_hours', 'resolution_time_hours',
                  'escalation_time_hours', 'notes']


class TicketCategoryForm(BaseForm):
    class Meta:
        model = TicketCategory
        fields = ['name', 'description', 'parent', 'default_priority',
                  'default_sla', 'notes']


class TicketForm(BaseForm):
    class Meta:
        model = Ticket
        fields = ['title', 'description', 'category', 'priority', 'channel',
                  'assigned_to', 'related_service', 'related_order', 'notes']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
        }


class TicketAssignForm(BaseForm):
    class Meta:
        model = Ticket
        fields = ['assigned_to']


class TicketCommentForm(BaseForm):
    class Meta:
        model = TicketComment
        fields = ['content', 'is_internal']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3}),
        }


class TicketAttachmentForm(BaseForm):
    class Meta:
        model = TicketAttachment
        fields = ['file']


class EscalationRuleForm(BaseForm):
    class Meta:
        model = EscalationRule
        fields = ['category', 'condition_type', 'escalate_to', 'notify_method',
                  'notes']
