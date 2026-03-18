import json
from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.calendar_app.models import Event

User = get_user_model()


class EventModelTest(TestCase):
    """일정 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='caluser', password='testpass123',
            role='staff', name='일정유저',
        )
        self.now = timezone.now()

    def test_event_creation(self):
        """일정 생성"""
        event = Event.objects.create(
            title='팀 미팅',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            event_type=Event.EventType.MEETING,
            creator=self.user,
            created_by=self.user,
        )
        self.assertEqual(event.title, '팀 미팅')
        self.assertEqual(event.event_type, 'meeting')
        self.assertEqual(event.creator, self.user)

    def test_event_str(self):
        """일정 문자열 표현"""
        event = Event.objects.create(
            title='문자열 테스트',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            creator=self.user,
            created_by=self.user,
        )
        self.assertEqual(str(event), '문자열 테스트')

    def test_event_type_choices(self):
        """일정 유형 선택지"""
        choices = dict(Event.EventType.choices)
        self.assertIn('personal', choices)
        self.assertIn('team', choices)
        self.assertIn('company', choices)
        self.assertIn('meeting', choices)

    def test_default_event_type(self):
        """기본 일정 유형은 개인"""
        event = Event.objects.create(
            title='기본유형',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            creator=self.user,
            created_by=self.user,
        )
        self.assertEqual(event.event_type, Event.EventType.PERSONAL)

    def test_default_color(self):
        """기본 색상"""
        event = Event.objects.create(
            title='기본색상',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            creator=self.user,
            created_by=self.user,
        )
        self.assertEqual(event.color, '#3B82F6')

    def test_all_day_event(self):
        """종일 이벤트"""
        event = Event.objects.create(
            title='종일 일정',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(days=1),
            all_day=True,
            creator=self.user,
            created_by=self.user,
        )
        self.assertTrue(event.all_day)

    def test_event_attendees(self):
        """참석자 M2M 관계"""
        user2 = User.objects.create_user(
            username='attendee', password='testpass123', name='참석자',
        )
        event = Event.objects.create(
            title='참석자 테스트',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            creator=self.user,
            created_by=self.user,
        )
        event.attendees.add(self.user, user2)
        self.assertEqual(event.attendees.count(), 2)

    def test_event_location(self):
        """일정 장소"""
        event = Event.objects.create(
            title='장소 테스트',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            location='회의실 A',
            creator=self.user,
            created_by=self.user,
        )
        self.assertEqual(event.location, '회의실 A')

    def test_event_ordering(self):
        """일정은 시작일시순 정렬"""
        e1 = Event.objects.create(
            title='나중일정',
            start_datetime=self.now + timedelta(days=1),
            end_datetime=self.now + timedelta(days=1, hours=1),
            creator=self.user, created_by=self.user,
        )
        e2 = Event.objects.create(
            title='먼저일정',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            creator=self.user, created_by=self.user,
        )
        events = list(Event.objects.all())
        self.assertEqual(events[0], e2)
        self.assertEqual(events[1], e1)

    def test_event_soft_delete(self):
        """일정 soft delete"""
        event = Event.objects.create(
            title='삭제테스트',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            creator=self.user, created_by=self.user,
        )
        event.soft_delete()
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())
        self.assertTrue(Event.all_objects.filter(pk=event.pk).exists())


class EventViewTest(TestCase):
    """일정 뷰 테스트"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='calviewuser', password='testpass123',
            role='staff', name='뷰유저',
        )
        self.now = timezone.now()

    def test_calendar_view_requires_login(self):
        """캘린더 비로그인 접근 불가"""
        response = self.client.get(reverse('calendar_app:calendar_view'))
        self.assertEqual(response.status_code, 302)

    def test_calendar_view_accessible(self):
        """캘린더 로그인 후 접근"""
        self.client.force_login(User.objects.get(username='calviewuser'))
        response = self.client.get(reverse('calendar_app:calendar_view'))
        self.assertEqual(response.status_code, 200)

    def test_event_list_accessible(self):
        """일정 목록 접근"""
        self.client.force_login(User.objects.get(username='calviewuser'))
        response = self.client.get(reverse('calendar_app:event_list'))
        self.assertEqual(response.status_code, 200)

    def test_event_api_returns_json(self):
        """일정 API가 JSON 반환"""
        self.client.force_login(User.objects.get(username='calviewuser'))
        Event.objects.create(
            title='API 테스트 이벤트',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            creator=self.user, created_by=self.user,
        )
        response = self.client.get(reverse('calendar_app:event_api'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        data = json.loads(response.content)
        self.assertIsInstance(data, list)
        self.assertTrue(len(data) >= 1)

    def test_event_api_with_date_range(self):
        """날짜 범위로 일정 API 필터링"""
        self.client.force_login(User.objects.get(username='calviewuser'))
        Event.objects.create(
            title='범위 내 이벤트',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            creator=self.user, created_by=self.user,
        )
        start = (self.now - timedelta(days=1)).strftime('%Y-%m-%d')
        end = (self.now + timedelta(days=1)).strftime('%Y-%m-%d')
        response = self.client.get(
            reverse('calendar_app:event_api'),
            {'start': start, 'end': end},
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(len(data) >= 1)

    def test_event_api_json_structure(self):
        """일정 API 응답 구조 확인"""
        self.client.force_login(User.objects.get(username='calviewuser'))
        Event.objects.create(
            title='구조 확인',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            event_type=Event.EventType.MEETING,
            location='회의실',
            creator=self.user, created_by=self.user,
        )
        response = self.client.get(reverse('calendar_app:event_api'))
        data = json.loads(response.content)
        event_data = data[0]
        self.assertIn('id', event_data)
        self.assertIn('title', event_data)
        self.assertIn('start', event_data)
        self.assertIn('end', event_data)
        self.assertIn('allDay', event_data)
        self.assertIn('color', event_data)
        self.assertIn('extendedProps', event_data)
        props = event_data['extendedProps']
        self.assertIn('event_type', props)
        self.assertIn('location', props)
        self.assertIn('creator', props)

    def test_event_create_form(self):
        """일정 생성 폼 접근"""
        self.client.force_login(User.objects.get(username='calviewuser'))
        response = self.client.get(reverse('calendar_app:event_create'))
        self.assertEqual(response.status_code, 200)

    def test_event_delete_soft_deletes(self):
        """일정 삭제는 soft delete"""
        self.client.force_login(User.objects.get(username='calviewuser'))
        event = Event.objects.create(
            title='삭제 테스트',
            start_datetime=self.now,
            end_datetime=self.now + timedelta(hours=1),
            creator=self.user, created_by=self.user,
        )
        response = self.client.post(
            reverse('calendar_app:event_delete', kwargs={'pk': event.pk}),
        )
        self.assertEqual(response.status_code, 302)
        # ActiveManager로는 찾을 수 없지만 all_objects로는 존재
        self.assertFalse(Event.objects.filter(pk=event.pk).exists())
        self.assertTrue(Event.all_objects.filter(pk=event.pk).exists())
