from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q, Max, Subquery, OuterRef
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, DetailView, FormView

from apps.accounts.models import User
from .forms import GroupChatForm
from .models import ChatRoom, ChatParticipant, Message


class ChatListView(LoginRequiredMixin, ListView):
    template_name = 'messenger/chat_list.html'
    context_object_name = 'rooms'

    def get_queryset(self):
        return (
            ChatRoom.objects.filter(
                chatparticipant__user=self.request.user,
                is_active=True,
            )
            .annotate(
                last_message_time=Max('messages__sent_at'),
            )
            .order_by('-last_message_time', '-updated_at')
            .distinct()
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        rooms_data = []
        for room in ctx['rooms']:
            last_msg = room.get_last_message()
            rooms_data.append({
                'room': room,
                'display_name': room.get_display_name(user),
                'last_message': last_msg,
                'unread_count': room.get_unread_count(user),
            })
        ctx['rooms_data'] = rooms_data
        ctx['users'] = User.objects.filter(is_active=True).exclude(pk=user.pk)
        return ctx


class ChatRoomView(LoginRequiredMixin, DetailView):
    template_name = 'messenger/chat_room.html'
    context_object_name = 'room'

    def get_queryset(self):
        return ChatRoom.objects.filter(
            chatparticipant__user=self.request.user,
            is_active=True,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        room = self.object
        user = self.request.user

        # 최근 메시지 100건
        ctx['messages'] = room.messages.select_related('sender').order_by('-sent_at')[:100][::-1]
        ctx['display_name'] = room.get_display_name(user)
        ctx['participants'] = room.participants.all()

        # 읽음 시간 갱신
        ChatParticipant.objects.filter(
            room=room, user=user
        ).update(last_read_at=timezone.now())

        # 사이드바용 대화방 목록
        ctx['rooms'] = ChatRoom.objects.filter(
            chatparticipant__user=user,
            is_active=True,
        ).annotate(
            last_message_time=Max('messages__sent_at'),
        ).order_by('-last_message_time', '-updated_at').distinct()
        ctx['rooms_data'] = []
        for r in ctx['rooms']:
            last_msg = r.get_last_message()
            ctx['rooms_data'].append({
                'room': r,
                'display_name': r.get_display_name(user),
                'last_message': last_msg,
                'unread_count': r.get_unread_count(user),
            })
        ctx['users'] = User.objects.filter(is_active=True).exclude(pk=user.pk)

        return ctx


class CreateDirectChatView(LoginRequiredMixin, View):
    """1:1 대화 생성 (이미 존재하면 해당 대화방으로 이동)"""

    def post(self, request, user_id):
        other_user = get_object_or_404(User, pk=user_id, is_active=True)
        if other_user == request.user:
            return redirect('messenger:chat_list')

        # 기존 1:1 대화방 찾기
        existing = ChatRoom.objects.filter(
            room_type=ChatRoom.RoomType.DIRECT,
            is_active=True,
            chatparticipant__user=request.user,
        ).filter(
            chatparticipant__user=other_user,
        ).first()

        if existing:
            return redirect('messenger:chat_room', pk=existing.pk)

        # 새 대화방 생성
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=request.user,
        )
        ChatParticipant.objects.create(room=room, user=request.user)
        ChatParticipant.objects.create(room=room, user=other_user)

        return redirect('messenger:chat_room', pk=room.pk)


class CreateGroupChatView(LoginRequiredMixin, FormView):
    template_name = 'messenger/create_group.html'
    form_class = GroupChatForm

    def form_valid(self, form):
        room = ChatRoom.objects.create(
            name=form.cleaned_data['name'],
            room_type=ChatRoom.RoomType.GROUP,
            created_by=self.request.user,
        )
        # 자기 자신 추가
        ChatParticipant.objects.create(room=room, user=self.request.user)
        # 선택된 참여자 추가
        for user in form.cleaned_data['participants']:
            if user != self.request.user:
                ChatParticipant.objects.create(room=room, user=user)

        return redirect('messenger:chat_room', pk=room.pk)
