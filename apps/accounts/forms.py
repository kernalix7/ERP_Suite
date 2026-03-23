from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm, UserCreationForm, UserChangeForm,
    PasswordChangeForm, SetPasswordForm,
)

from .models import User

INPUT_CLASS = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='아이디',
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '아이디를 입력하세요',
        }),
    )
    password = forms.CharField(
        label='비밀번호',
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '비밀번호를 입력하세요',
        }),
    )


class UserCreateForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'name', 'email', 'phone', 'role', 'is_auditor', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input'}),
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'role': forms.Select(attrs={'class': 'form-input'}),
            'is_auditor': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }


class UserUpdateForm(UserChangeForm):
    password = None

    class Meta:
        model = User
        fields = ('username', 'name', 'email', 'phone', 'role', 'is_auditor', 'is_active')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input'}),
            'name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'phone': forms.TextInput(attrs={'class': 'form-input'}),
            'role': forms.Select(attrs={'class': 'form-input'}),
        }


class ProfileForm(forms.ModelForm):
    """본인 프로필 수정 (역할/권한 변경 불가)"""

    class Meta:
        model = User
        fields = ('name', 'phone', 'email')
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'phone': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'email': forms.EmailInput(attrs={'class': INPUT_CLASS}),
        }
        labels = {
            'name': '이름',
            'phone': '연락처',
            'email': '이메일',
        }


class PasswordChangeCustomForm(PasswordChangeForm):
    old_password = forms.CharField(
        label='현재 비밀번호',
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '현재 비밀번호',
        }),
    )
    new_password1 = forms.CharField(
        label='새 비밀번호',
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '새 비밀번호',
        }),
    )
    new_password2 = forms.CharField(
        label='새 비밀번호 확인',
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '새 비밀번호 확인',
        }),
    )


class AdminSetPasswordForm(SetPasswordForm):
    """관리자가 다른 사용자 비밀번호를 재설정"""
    new_password1 = forms.CharField(
        label='새 비밀번호',
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '새 비밀번호',
        }),
    )
    new_password2 = forms.CharField(
        label='새 비밀번호 확인',
        widget=forms.PasswordInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '새 비밀번호 확인',
        }),
    )
