from django import forms

from apps.core.forms import BaseForm
from .models import InquiryChannel, Inquiry, InquiryReply, ReplyTemplate


class InquiryChannelForm(BaseForm):
    class Meta:
        model = InquiryChannel
        fields = ['name', 'icon', 'notes']


class InquiryForm(BaseForm):
    class Meta:
        model = Inquiry
        fields = [
            'channel', 'customer_name', 'customer_contact', 'subject',
            'content', 'status', 'priority', 'received_date', 'assigned_to', 'notes',
        ]
        widgets = {
            'received_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-input'}
            ),
        }


class InquiryReplyForm(BaseForm):
    class Meta:
        model = InquiryReply
        fields = ['content']


class ReplyTemplateForm(BaseForm):
    class Meta:
        model = ReplyTemplate
        fields = ['category', 'title', 'content', 'notes']
