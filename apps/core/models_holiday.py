"""공휴일/휴무일 마스터 — 근태·생산스케줄·납기계산에서 영업일 차감용."""
from django.db import models
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class Holiday(BaseModel):
    """공휴일 / 회사 휴무일.

    근태(attendance), 생산일정(production), 납기계산(sales/purchase)에서
    영업일(business day) 차감 시 참조한다.
    """

    class HolidayType(models.TextChoices):
        PUBLIC = 'PUBLIC', '법정공휴일'
        SUBSTITUTE = 'SUBSTITUTE', '대체공휴일'
        COMPANY = 'COMPANY', '회사 휴무일'
        TEMPORARY = 'TEMPORARY', '임시공휴일'

    date = models.DateField('일자', unique=True)
    name = models.CharField('명칭', max_length=50)
    holiday_type = models.CharField(
        '구분', max_length=16,
        choices=HolidayType.choices, default=HolidayType.PUBLIC,
    )
    is_recurring_lunar = models.BooleanField(
        '음력 반복', default=False,
        help_text='설날/추석처럼 음력 기반 매년 재계산 필요한 경우',
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = '공휴일'
        verbose_name_plural = '공휴일'
        ordering = ['date']
        indexes = [
            models.Index(fields=['date'], name='idx_holiday_date'),
            models.Index(fields=['holiday_type'], name='idx_holiday_type'),
        ]

    def __str__(self):
        return f'{self.date} {self.name}'

    @classmethod
    def is_holiday(cls, target_date):
        """특정 일자가 공휴일/휴무일인지"""
        return cls.objects.filter(date=target_date, is_active=True).exists()

    @classmethod
    def is_business_day(cls, target_date):
        """영업일 여부 — 주말도 아니고 공휴일도 아닌 평일"""
        if target_date.weekday() >= 5:  # 토(5), 일(6)
            return False
        return not cls.is_holiday(target_date)

    @classmethod
    def add_business_days(cls, start_date, days):
        """start_date 로부터 days 영업일 후 일자 반환 (주말+공휴일 차감)"""
        from datetime import timedelta
        current = start_date
        added = 0
        while added < days:
            current += timedelta(days=1)
            if cls.is_business_day(current):
                added += 1
        return current
