from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.messenger.models import ChatRoom, ChatParticipant, Message

User = get_user_model()


class ChatRoomModelTest(TestCase):
    """대화방 모델 테스트"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='chatuser1', password='testpass123',
            role='staff', name='유저1',
        )
        self.user2 = User.objects.create_user(
            username='chatuser2', password='testpass123',
            role='staff', name='유저2',
        )

    def test_room_creation(self):
        """대화방 생성"""
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=self.user1,
        )
        self.assertEqual(room.room_type, 'direct')
        self.assertTrue(room.is_active)

    def test_room_str_with_name(self):
        """이름 있는 대화방 문자열 표현"""
        room = ChatRoom.objects.create(
            name='개발팀 채팅방',
            room_type=ChatRoom.RoomType.GROUP,
            created_by=self.user1,
        )
        self.assertEqual(str(room), '개발팀 채팅방')

    def test_room_str_without_name(self):
        """이름 없는 대화방 - 참여자 이름 표시"""
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=self.user1,
        )
        ChatParticipant.objects.create(room=room, user=self.user1)
        ChatParticipant.objects.create(room=room, user=self.user2)
        result = str(room)
        # 참여자 이름 포함
        self.assertTrue('유저1' in result or '유저2' in result)

    def test_room_type_choices(self):
        """대화방 유형 선택지"""
        choices = dict(ChatRoom.RoomType.choices)
        self.assertIn('direct', choices)
        self.assertIn('group', choices)

    def test_get_display_name_direct(self):
        """1:1 대화방 표시 이름 - 상대방 이름"""
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=self.user1,
        )
        ChatParticipant.objects.create(room=room, user=self.user1)
        ChatParticipant.objects.create(room=room, user=self.user2)
        display = room.get_display_name(self.user1)
        self.assertEqual(display, str(self.user2))

    def test_get_display_name_group_with_name(self):
        """이름 있는 그룹 대화방 표시 이름"""
        room = ChatRoom.objects.create(
            name='프로젝트팀',
            room_type=ChatRoom.RoomType.GROUP,
            created_by=self.user1,
        )
        self.assertEqual(room.get_display_name(self.user1), '프로젝트팀')

    def test_get_last_message(self):
        """마지막 메시지 조회"""
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=self.user1,
        )
        ChatParticipant.objects.create(room=room, user=self.user1)
        Message.objects.create(
            room=room, sender=self.user1, content='첫번째',
        )
        msg2 = Message.objects.create(
            room=room, sender=self.user1, content='두번째',
        )
        last = room.get_last_message()
        self.assertEqual(last, msg2)

    def test_get_last_message_empty(self):
        """메시지 없는 대화방의 마지막 메시지"""
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=self.user1,
        )
        self.assertIsNone(room.get_last_message())

    def test_get_unread_count_no_last_read(self):
        """last_read_at이 없으면 전체 메시지가 안읽음"""
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=self.user1,
        )
        ChatParticipant.objects.create(room=room, user=self.user1)
        Message.objects.create(room=room, sender=self.user2, content='메시지1')
        Message.objects.create(room=room, sender=self.user2, content='메시지2')
        self.assertEqual(room.get_unread_count(self.user1), 2)

    def test_get_unread_count_with_last_read(self):
        """last_read_at 이후 메시지만 안읽음으로 카운트"""
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=self.user1,
        )
        participant = ChatParticipant.objects.create(
            room=room, user=self.user1,
        )
        Message.objects.create(room=room, sender=self.user2, content='이전 메시지')
        participant.last_read_at = timezone.now()
        participant.save()
        Message.objects.create(room=room, sender=self.user2, content='새 메시지')
        self.assertEqual(room.get_unread_count(self.user1), 1)

    def test_room_soft_delete(self):
        """대화방 soft delete"""
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.GROUP,
            name='삭제테스트',
            created_by=self.user1,
        )
        room.soft_delete()
        self.assertFalse(ChatRoom.objects.filter(pk=room.pk).exists())
        self.assertTrue(ChatRoom.all_objects.filter(pk=room.pk).exists())


class ChatParticipantModelTest(TestCase):
    """대화 참여자 모델 테스트"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='partuser1', password='testpass123', name='참여자1',
        )
        self.user2 = User.objects.create_user(
            username='partuser2', password='testpass123', name='참여자2',
        )
        self.room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=self.user1,
        )

    def test_participant_creation(self):
        """참여자 생성"""
        participant = ChatParticipant.objects.create(
            room=self.room, user=self.user1,
        )
        self.assertEqual(participant.room, self.room)
        self.assertEqual(participant.user, self.user1)
        self.assertIsNotNone(participant.joined_at)

    def test_participant_str(self):
        """참여자 문자열 표현"""
        participant = ChatParticipant.objects.create(
            room=self.room, user=self.user1,
        )
        result = str(participant)
        self.assertIn('참여자1', result)

    def test_unique_together(self):
        """같은 대화방에 같은 사용자 중복 참여 불가"""
        ChatParticipant.objects.create(room=self.room, user=self.user1)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ChatParticipant.objects.create(room=self.room, user=self.user1)

    def test_last_read_at_update(self):
        """마지막 읽은 시간 업데이트"""
        participant = ChatParticipant.objects.create(
            room=self.room, user=self.user1,
        )
        self.assertIsNone(participant.last_read_at)
        participant.last_read_at = timezone.now()
        participant.save()
        participant.refresh_from_db()
        self.assertIsNotNone(participant.last_read_at)


class MessageModelTest(TestCase):
    """메시지 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='msguser', password='testpass123', name='메시지유저',
        )
        self.room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=self.user,
        )

    def test_message_creation(self):
        """메시지 생성"""
        msg = Message.objects.create(
            room=self.room,
            sender=self.user,
            content='안녕하세요',
        )
        self.assertEqual(msg.content, '안녕하세요')
        self.assertEqual(msg.sender, self.user)
        self.assertEqual(msg.message_type, Message.MessageType.TEXT)

    def test_message_str(self):
        """메시지 문자열 표현"""
        msg = Message.objects.create(
            room=self.room, sender=self.user,
            content='긴 메시지 내용 테스트 문자열',
        )
        result = str(msg)
        self.assertIn('메시지유저', result)

    def test_message_type_choices(self):
        """메시지 유형 선택지"""
        choices = dict(Message.MessageType.choices)
        self.assertIn('text', choices)
        self.assertIn('file', choices)
        self.assertIn('image', choices)

    def test_message_ordering(self):
        """메시지는 전송 시간순 정렬"""
        m1 = Message.objects.create(
            room=self.room, sender=self.user, content='첫번째',
        )
        m2 = Message.objects.create(
            room=self.room, sender=self.user, content='두번째',
        )
        messages = list(Message.objects.all())
        self.assertEqual(messages[0], m1)
        self.assertEqual(messages[1], m2)

    def test_sent_at_auto_set(self):
        """sent_at 자동 설정"""
        msg = Message.objects.create(
            room=self.room, sender=self.user, content='자동시간',
        )
        self.assertIsNotNone(msg.sent_at)


class MessengerViewTest(TestCase):
    """메신저 뷰 테스트"""

    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(
            username='msgviewuser1', password='testpass123',
            role='staff', name='뷰유저1',
        )
        self.user2 = User.objects.create_user(
            username='msgviewuser2', password='testpass123',
            role='staff', name='뷰유저2',
        )

    def test_chat_list_requires_login(self):
        """대화 목록 비로그인 접근 불가"""
        response = self.client.get(reverse('messenger:chat_list'))
        self.assertEqual(response.status_code, 302)

    def test_chat_list_accessible(self):
        """대화 목록 로그인 후 접근"""
        self.client.force_login(User.objects.get(username='msgviewuser1'))
        response = self.client.get(reverse('messenger:chat_list'))
        self.assertEqual(response.status_code, 200)

    def test_create_direct_chat(self):
        """1:1 대화 생성"""
        self.client.force_login(User.objects.get(username='msgviewuser1'))
        url = reverse(
            'messenger:create_direct',
            kwargs={'user_id': self.user2.pk},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        room = ChatRoom.objects.filter(room_type='direct').first()
        self.assertIsNotNone(room)
        self.assertEqual(room.chatparticipant_set.count(), 2)

    def test_create_direct_chat_with_self_redirects(self):
        """자기 자신과 대화 생성 시도 시 리다이렉트"""
        self.client.force_login(User.objects.get(username='msgviewuser1'))
        url = reverse(
            'messenger:create_direct',
            kwargs={'user_id': self.user1.pk},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ChatRoom.objects.count(), 0)

    def test_create_direct_chat_reuses_existing(self):
        """기존 1:1 대화방이 있으면 재사용"""
        self.client.force_login(User.objects.get(username='msgviewuser1'))
        url = reverse(
            'messenger:create_direct',
            kwargs={'user_id': self.user2.pk},
        )
        self.client.post(url)
        first_room_count = ChatRoom.objects.count()
        self.client.post(url)
        self.assertEqual(
            ChatRoom.objects.count(), first_room_count,
        )

    def test_chat_room_view(self):
        """대화방 상세 접근"""
        self.client.force_login(User.objects.get(username='msgviewuser1'))
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=self.user1,
        )
        ChatParticipant.objects.create(room=room, user=self.user1)
        ChatParticipant.objects.create(room=room, user=self.user2)
        response = self.client.get(
            reverse('messenger:chat_room', kwargs={'pk': room.pk}),
        )
        self.assertEqual(response.status_code, 200)

    def test_chat_room_updates_last_read(self):
        """대화방 접근 시 last_read_at 업데이트"""
        self.client.force_login(User.objects.get(username='msgviewuser1'))
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.DIRECT,
            created_by=self.user1,
        )
        ChatParticipant.objects.create(room=room, user=self.user1)
        ChatParticipant.objects.create(room=room, user=self.user2)
        self.client.get(
            reverse('messenger:chat_room', kwargs={'pk': room.pk}),
        )
        participant = ChatParticipant.objects.get(room=room, user=self.user1)
        self.assertIsNotNone(participant.last_read_at)


class ChatRoomFormTest(TestCase):
    """ChatRoomForm / ChatParticipantForm 폼 테스트"""

    def setUp(self):
        self.user1 = User.objects.create_user(
            username='formchat1', password='testpass123',
            role='staff', name='폼채팅유저1',
        )
        self.user2 = User.objects.create_user(
            username='formchat2', password='testpass123',
            role='staff', name='폼채팅유저2',
        )

    def test_chat_room_form_group_valid(self):
        """그룹 대화방 폼 유효"""
        from apps.messenger.forms import ChatRoomForm
        form = ChatRoomForm(data={
            'name': '개발팀',
            'room_type': ChatRoom.RoomType.GROUP,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_chat_room_form_group_no_name_invalid(self):
        """그룹 대화방에 이름 없으면 유효하지 않음"""
        from apps.messenger.forms import ChatRoomForm
        form = ChatRoomForm(data={
            'name': '',
            'room_type': ChatRoom.RoomType.GROUP,
        })
        self.assertFalse(form.is_valid())

    def test_chat_room_form_direct_valid(self):
        """1:1 대화방 폼 유효 (이름 없어도 됨)"""
        from apps.messenger.forms import ChatRoomForm
        form = ChatRoomForm(data={
            'name': '',
            'room_type': ChatRoom.RoomType.DIRECT,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_chat_participant_form_valid(self):
        """참여자 폼 유효"""
        from apps.messenger.forms import ChatParticipantForm
        room = ChatRoom.objects.create(
            room_type=ChatRoom.RoomType.GROUP,
            name='테스트방',
            created_by=self.user1,
        )
        form = ChatParticipantForm(data={
            'room': room.pk,
            'user': self.user2.pk,
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_group_chat_form_valid(self):
        """GroupChatForm 유효 (레거시 폼 호환)"""
        from apps.messenger.forms import GroupChatForm
        form = GroupChatForm(data={
            'name': '그룹채팅',
            'participants': [self.user1.pk, self.user2.pk],
        })
        self.assertTrue(form.is_valid(), form.errors)

    def test_group_chat_form_no_name_invalid(self):
        """GroupChatForm - 이름 없으면 유효하지 않음"""
        from apps.messenger.forms import GroupChatForm
        form = GroupChatForm(data={
            'name': '',
            'participants': [self.user1.pk],
        })
        self.assertFalse(form.is_valid())
