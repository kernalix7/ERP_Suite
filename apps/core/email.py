"""
이메일 알림 유틸리티

사용법:
    from apps.core.email import send_notification_email
    send_notification_email(
        user=user_instance,
        subject='새 주문 접수',
        message='주문 ORD-2026-0001이 접수되었습니다.',
    )
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_notification_email(user, subject, message, html_template=None,
                            context=None):
    """
    사용자에게 알림 이메일을 발송합니다.

    Args:
        user: User instance (email 필드 필요)
        subject: 제목
        message: 본문 (plain text)
        html_template: HTML 템플릿 경로 (optional)
        context: 템플릿 컨텍스트 (optional)
    """
    if not user.email:
        logger.warning('이메일 주소 없음: %s', user.username)
        return False

    from_email = getattr(
        settings, 'DEFAULT_FROM_EMAIL', 'noreply@erp.local'
    )

    html_message = None
    if html_template and context:
        try:
            html_message = render_to_string(html_template, context)
        except Exception as e:
            logger.error('이메일 템플릿 렌더링 실패: %s', e)

    try:
        send_mail(
            subject=f'[ERP Suite] {subject}',
            message=message,
            from_email=from_email,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info('이메일 발송 성공: %s → %s', subject, user.email)
        return True
    except Exception as e:
        logger.error('이메일 발송 실패: %s → %s: %s', subject, user.email, e)
        return False


def send_bulk_notification_email(users, subject, message):
    """여러 사용자에게 알림 이메일을 일괄 발송합니다."""
    results = []
    for user in users:
        result = send_notification_email(user, subject, message)
        results.append((user, result))
    return results
