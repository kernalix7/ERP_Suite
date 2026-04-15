from django import forms

from apps.core.forms import BaseForm

from .models import PortalDocument, PortalUser


class PortalLoginForm(forms.Form):
    username = forms.CharField(
        label='사용자명',
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': '사용자명'}),
    )
    password = forms.CharField(
        label='비밀번호',
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': '비밀번호'}),
    )


class PortalUserForm(BaseForm):
    class Meta:
        model = PortalUser
        fields = ['user', 'partner', 'portal_type', 'is_verified', 'notes']


class PortalDocumentForm(BaseForm):
    class Meta:
        model = PortalDocument
        fields = ['document_type', 'title', 'file', 'notes']
