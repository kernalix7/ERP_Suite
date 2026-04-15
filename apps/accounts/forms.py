from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm, UserCreationForm, UserChangeForm,
    PasswordChangeForm, SetPasswordForm,
)

from .models import IPWhitelist, PermissionGroup, User

INPUT_CLASS = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500'


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='이메일 / 사번',
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '이메일 또는 사번을 입력하세요',
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


class PermissionRequestForm(forms.Form):
    """권한 신청 폼"""
    ROLE_CHOICES = [
        ('manager', '매니저'),
        ('admin', '관리자'),
    ]
    requested_role = forms.ChoiceField(
        label='신청 역할',
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={'class': INPUT_CLASS}),
    )
    reason = forms.CharField(
        label='사유',
        widget=forms.Textarea(attrs={
            'class': INPUT_CLASS,
            'rows': 4,
            'placeholder': '권한 신청 사유를 입력하세요',
        }),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            # 현재 역할보다 높은 역할만 선택 가능
            if user.role == 'manager':
                self.fields['requested_role'].choices = [('admin', '관리자')]
            elif user.role == 'admin':
                self.fields['requested_role'].choices = []


class PermissionGroupForm(forms.ModelForm):
    """권한 그룹 생성/수정 폼"""

    class Meta:
        model = PermissionGroup
        fields = ('name', 'description', 'priority')
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASS}),
            'description': forms.Textarea(attrs={'class': INPUT_CLASS, 'rows': 3}),
            'priority': forms.NumberInput(attrs={'class': INPUT_CLASS, 'min': 0}),
        }


class TwoFactorSetupForm(forms.Form):
    """2FA 설정 검증 폼"""
    code = forms.CharField(
        label='인증 코드',
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '6자리 코드 입력',
            'autocomplete': 'off',
            'inputmode': 'numeric',
            'pattern': '[0-9]{6}',
        }),
    )

    def clean_code(self):
        code = self.cleaned_data['code']
        if not code.isdigit():
            raise forms.ValidationError('숫자만 입력하세요.')
        return code


class TwoFactorVerifyForm(forms.Form):
    """2FA 검증 폼 (로그인 후)"""
    code = forms.CharField(
        label='인증 코드',
        max_length=16,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASS,
            'placeholder': '6자리 코드 또는 백업코드',
            'autocomplete': 'off',
        }),
    )


class IPWhitelistForm(forms.ModelForm):
    """IP 화이트리스트 추가 폼"""

    class Meta:
        model = IPWhitelist
        fields = ('ip_address', 'description', 'scope')
        widgets = {
            'ip_address': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': '192.168.1.1'}),
            'description': forms.TextInput(attrs={'class': INPUT_CLASS, 'placeholder': '사무실 IP'}),
            'scope': forms.Select(attrs={'class': INPUT_CLASS}),
        }
