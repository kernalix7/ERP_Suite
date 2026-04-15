"""Excel 다운로드 감사 로그 모델"""
import logging

from django.conf import settings
from django.db import models
from django.utils import timezone

logger = logging.getLogger(__name__)


class ExcelDownloadLog(models.Model):
    """Excel 다운로드 감사 추적"""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='사용자',
        related_name='excel_downloads',
    )
    view_name = models.CharField('뷰 이름', max_length=200)
    row_count = models.PositiveIntegerField('행 수', default=0)
    downloaded_at = models.DateTimeField('다운로드 시각', auto_now_add=True)
    ip_address = models.GenericIPAddressField('IP 주소', null=True, blank=True)

    class Meta:
        verbose_name = 'Excel 다운로드 로그'
        verbose_name_plural = 'Excel 다운로드 로그'
        ordering = ['-downloaded_at']
        indexes = [
            models.Index(fields=['user', '-downloaded_at'], name='idx_excel_dl_user_date'),
        ]

    def __str__(self):
        return f'{self.user} - {self.view_name} ({self.downloaded_at:%Y-%m-%d %H:%M})'

    @classmethod
    def log_download(cls, user, view_name, row_count, ip_address=None):
        """다운로드 기록 + 1일 50건 초과 시 관리자 알림"""
        cls.objects.create(
            user=user,
            view_name=view_name,
            row_count=row_count,
            ip_address=ip_address,
        )

        # 1일 50건 초과 시 관리자 알림
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = cls.objects.filter(
            user=user,
            downloaded_at__gte=today_start,
        ).count()

        if today_count >= 50:
            try:
                from apps.core.notification import create_notification
                create_notification(
                    users='admin',
                    title='Excel 대량 다운로드 경고',
                    message=(
                        f'{user.name or user.username}이(가) 오늘 Excel 파일을 '
                        f'{today_count}건 다운로드했습니다. 확인이 필요합니다.'
                    ),
                    noti_type='SYSTEM',
                )
            except Exception:
                logger.warning(
                    'Excel download alert failed: user=%s count=%d',
                    user.username, today_count,
                )
