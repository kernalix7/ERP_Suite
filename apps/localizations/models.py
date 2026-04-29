"""Country 마스터 모델 — 국가 코드·통화·로케일·활성 여부."""
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class Country(BaseModel):
    """국가 마스터 (ISO-3166 alpha-2 기준)."""

    BUSINESS_KEY_FIELD = 'code'

    code = models.CharField(
        '국가코드 (ISO-3166)', max_length=2, unique=True,
        help_text='2자리 알파벳 (KR, US, JP, ...)',
    )
    name = models.CharField('국가명', max_length=100)
    currency_code = models.CharField(
        '기본통화 (ISO-4217)', max_length=3,
        help_text='KRW, USD, JPY, ...',
    )
    locale = models.CharField(
        '로케일', max_length=10,
        help_text='ko_KR, en_US, ja_JP, ...',
    )
    is_default = models.BooleanField(
        '기본 국가', default=False,
        help_text='시스템 default 국가 (단일 행만 True)',
    )
    is_supported = models.BooleanField(
        '어댑터 구현됨', default=False,
        help_text='LocalizationAdapter 구현 여부 (False면 기능 제한)',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '국가'
        verbose_name_plural = '국가'
        ordering = ['code']

    def __str__(self):
        return f'[{self.code}] {self.name}'

    def save(self, *args, **kwargs):
        # is_default=True 단일 행 보장
        if self.is_default:
            type(self).objects.filter(is_default=True).exclude(pk=self.pk).update(
                is_default=False,
            )
        super().save(*args, **kwargs)
