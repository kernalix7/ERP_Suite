from django import forms

from apps.accounts.models import User


class GroupChatForm(forms.Form):
    name = forms.CharField(
        label='그룹명',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': '그룹 대화방 이름',
        }),
    )
    participants = forms.ModelMultipleChoiceField(
        label='참여자',
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
    )
