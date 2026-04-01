from django import forms

from apps.accounts.models import User
from apps.core.forms import BaseForm

from .models import ChatParticipant, ChatRoom


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


class ChatRoomForm(BaseForm):
    """대화방 생성/수정 폼"""

    participants = forms.ModelMultipleChoiceField(
        label='참여자',
        queryset=User.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = ChatRoom
        fields = ['name', 'room_type']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': '대화방 이름 (선택)'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        room_type = cleaned_data.get('room_type')
        participants = cleaned_data.get('participants')
        if room_type == ChatRoom.RoomType.GROUP and not cleaned_data.get('name'):
            raise forms.ValidationError('그룹 대화방에는 이름이 필요합니다.')
        if participants and room_type == ChatRoom.RoomType.DIRECT and participants.count() > 1:
            raise forms.ValidationError('1:1 대화는 참여자를 1명만 선택할 수 있습니다.')
        return cleaned_data


class ChatParticipantForm(BaseForm):
    """대화방 참여자 추가 폼"""

    class Meta:
        model = ChatParticipant
        fields = ['room', 'user']
        widgets = {
            'room': forms.HiddenInput(),
        }
