from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.inquiry.models import (
    InquiryChannel, Inquiry, InquiryReply, ReplyTemplate,
)

User = get_user_model()


class InquiryChannelModelTest(TestCase):
    """문의 채널 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='channeluser', password='testpass123', role='manager',
        )

    def test_channel_creation(self):
        """문의 채널 생성"""
        channel = InquiryChannel.objects.create(
            name='이메일', icon='email', created_by=self.user,
        )
        self.assertEqual(channel.name, '이메일')

    def test_channel_str(self):
        """문의 채널 문자열 표현"""
        channel = InquiryChannel.objects.create(
            name='전화', created_by=self.user,
        )
        self.assertEqual(str(channel), '전화')

    def test_channel_soft_delete(self):
        """문의 채널 soft delete"""
        channel = InquiryChannel.objects.create(
            name='삭제테스트', created_by=self.user,
        )
        channel.soft_delete()
        self.assertFalse(InquiryChannel.objects.filter(pk=channel.pk).exists())


class InquiryModelTest(TestCase):
    """문의 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='inquiryuser', password='testpass123',
            role='manager', name='문의담당',
        )
        self.channel = InquiryChannel.objects.create(
            name='이메일', created_by=self.user,
        )

    def test_inquiry_creation(self):
        """문의 생성"""
        inquiry = Inquiry.objects.create(
            channel=self.channel,
            customer_name='김고객',
            customer_contact='010-1234-5678',
            subject='제품 문의',
            content='제품 A에 대한 문의입니다.',
            received_date=timezone.now(),
            created_by=self.user,
        )
        self.assertEqual(inquiry.customer_name, '김고객')
        self.assertEqual(inquiry.status, Inquiry.Status.RECEIVED)
        self.assertEqual(inquiry.priority, Inquiry.Priority.NORMAL)

    def test_inquiry_str(self):
        """문의 문자열 표현"""
        inquiry = Inquiry.objects.create(
            channel=self.channel,
            customer_name='홍길동',
            subject='배송 문의',
            content='내용',
            received_date=timezone.now(),
            created_by=self.user,
        )
        result = str(inquiry)
        self.assertIn('접수', result)
        self.assertIn('배송 문의', result)

    def test_inquiry_status_choices(self):
        """문의 상태 선택지"""
        choices = dict(Inquiry.Status.choices)
        self.assertIn('RECEIVED', choices)
        self.assertIn('WAITING', choices)
        self.assertIn('REPLIED', choices)
        self.assertIn('CLOSED', choices)

    def test_inquiry_priority_choices(self):
        """문의 우선순위 선택지"""
        choices = dict(Inquiry.Priority.choices)
        self.assertIn('LOW', choices)
        self.assertIn('NORMAL', choices)
        self.assertIn('HIGH', choices)
        self.assertIn('URGENT', choices)

    def test_inquiry_status_transition(self):
        """문의 상태 전환: RECEIVED -> WAITING -> REPLIED -> CLOSED"""
        inquiry = Inquiry.objects.create(
            channel=self.channel,
            customer_name='전환테스트',
            subject='상태전환',
            content='내용',
            received_date=timezone.now(),
            created_by=self.user,
        )
        self.assertEqual(inquiry.status, 'RECEIVED')

        inquiry.status = Inquiry.Status.WAITING
        inquiry.save()
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, 'WAITING')

        inquiry.status = Inquiry.Status.REPLIED
        inquiry.save()
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, 'REPLIED')

        inquiry.status = Inquiry.Status.CLOSED
        inquiry.save()
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.status, 'CLOSED')

    def test_inquiry_assigned_to(self):
        """담당자 배정"""
        inquiry = Inquiry.objects.create(
            channel=self.channel,
            customer_name='담당배정',
            subject='담당자 테스트',
            content='내용',
            received_date=timezone.now(),
            created_by=self.user,
        )
        inquiry.assigned_to = self.user
        inquiry.save()
        inquiry.refresh_from_db()
        self.assertEqual(inquiry.assigned_to, self.user)

    def test_inquiry_ordering(self):
        """문의는 최신 접수일시순"""
        Inquiry.objects.create(
            channel=self.channel, customer_name='첫번째',
            subject='문의1', content='내용',
            received_date=timezone.now() - timedelta(hours=1),
            created_by=self.user,
        )
        Inquiry.objects.create(
            channel=self.channel, customer_name='두번째',
            subject='문의2', content='내용',
            received_date=timezone.now(),
            created_by=self.user,
        )
        inquiries = list(Inquiry.objects.all())
        self.assertEqual(inquiries[0].customer_name, '두번째')

    def test_inquiry_soft_delete(self):
        """문의 soft delete"""
        inquiry = Inquiry.objects.create(
            channel=self.channel, customer_name='삭제',
            subject='삭제 테스트', content='내용',
            received_date=timezone.now(),
            created_by=self.user,
        )
        inquiry.soft_delete()
        self.assertFalse(Inquiry.objects.filter(pk=inquiry.pk).exists())
        self.assertTrue(Inquiry.all_objects.filter(pk=inquiry.pk).exists())


class InquiryReplyModelTest(TestCase):
    """문의 답변 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='replyuser', password='testpass123',
            role='manager', name='답변자',
        )
        self.channel = InquiryChannel.objects.create(
            name='이메일', created_by=self.user,
        )
        self.inquiry = Inquiry.objects.create(
            channel=self.channel,
            customer_name='고객',
            subject='답변 테스트',
            content='문의내용',
            received_date=timezone.now(),
            created_by=self.user,
        )

    def test_reply_creation(self):
        """답변 생성"""
        reply = InquiryReply.objects.create(
            inquiry=self.inquiry,
            content='답변 내용입니다.',
            replied_by=self.user,
            created_by=self.user,
        )
        self.assertEqual(reply.content, '답변 내용입니다.')
        self.assertFalse(reply.is_llm_generated)

    def test_reply_str(self):
        """답변 문자열 표현"""
        reply = InquiryReply.objects.create(
            inquiry=self.inquiry,
            content='답변',
            replied_by=self.user,
            created_by=self.user,
        )
        self.assertIn('답변 테스트', str(reply))

    def test_ai_generated_reply(self):
        """AI 생성 답변 표시"""
        reply = InquiryReply.objects.create(
            inquiry=self.inquiry,
            content='AI가 생성한 답변입니다.',
            is_llm_generated=True,
            replied_by=self.user,
            created_by=self.user,
        )
        self.assertTrue(reply.is_llm_generated)

    def test_multiple_replies(self):
        """하나의 문의에 여러 답변"""
        InquiryReply.objects.create(
            inquiry=self.inquiry, content='첫번째 답변',
            replied_by=self.user, created_by=self.user,
        )
        InquiryReply.objects.create(
            inquiry=self.inquiry, content='두번째 답변',
            replied_by=self.user, created_by=self.user,
        )
        self.assertEqual(self.inquiry.replies.count(), 2)


class ReplyTemplateModelTest(TestCase):
    """답변 템플릿 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='tmpluser', password='testpass123', role='manager',
        )

    def test_template_creation(self):
        """답변 템플릿 생성"""
        tmpl = ReplyTemplate.objects.create(
            category='배송',
            title='배송 지연 안내',
            content='배송이 지연되어 안내 드립니다.',
            created_by=self.user,
        )
        self.assertEqual(tmpl.category, '배송')
        self.assertEqual(tmpl.use_count, 0)

    def test_template_str(self):
        """답변 템플릿 문자열 표현"""
        tmpl = ReplyTemplate.objects.create(
            category='교환',
            title='교환 절차 안내',
            content='내용',
            created_by=self.user,
        )
        self.assertEqual(str(tmpl), '[교환] 교환 절차 안내')

    def test_template_use_count_increment(self):
        """사용횟수 증가"""
        tmpl = ReplyTemplate.objects.create(
            category='반품',
            title='반품 안내',
            content='내용',
            created_by=self.user,
        )
        tmpl.use_count += 1
        tmpl.save()
        tmpl.refresh_from_db()
        self.assertEqual(tmpl.use_count, 1)

    def test_template_ordering(self):
        """템플릿은 사용횟수 내림차순"""
        t1 = ReplyTemplate.objects.create(
            category='A', title='적은사용', content='내용',
            use_count=5, created_by=self.user,
        )
        t2 = ReplyTemplate.objects.create(
            category='B', title='많은사용', content='내용',
            use_count=20, created_by=self.user,
        )
        templates = list(ReplyTemplate.objects.all())
        self.assertEqual(templates[0], t2)
        self.assertEqual(templates[1], t1)
