from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords

from apps.core.models import BaseModel


class AttendanceRecord(BaseModel):
    """출퇴근 기록"""

    class Status(models.TextChoices):
        NORMAL = 'NORMAL', '정상'
        LATE = 'LATE', '지각'
        EARLY_LEAVE = 'EARLY_LEAVE', '조퇴'
        ABSENT = 'ABSENT', '결근'
        HOLIDAY = 'HOLIDAY', '휴일'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='사용자',
        on_delete=models.PROTECT,
        related_name='attendance_records',
    )
    date = models.DateField('날짜')
    check_in = models.DateTimeField('출근 시간', null=True, blank=True)
    check_out = models.DateTimeField('퇴근 시간', null=True, blank=True)
    status = models.CharField(
        '상태',
        max_length=20,
        choices=Status.choices,
        default=Status.NORMAL,
    )
    overtime_hours = models.DecimalField(
        '초과근무(시간)',
        max_digits=4,
        decimal_places=1,
        default=Decimal('0'),
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '출퇴근 기록'
        verbose_name_plural = '출퇴근 기록'
        unique_together = ['user', 'date']
        ordering = ['-date']

    def __str__(self):
        return f'{self.user} - {self.date}'

    @property
    def work_hours(self):
        """근무 시간 (시간 단위)"""
        if self.check_in and self.check_out:
            delta = self.check_out - self.check_in
            return round(delta.total_seconds() / 3600, 1)
        return 0

    @property
    def is_late(self):
        """09:00 이후 출근 여부"""
        if self.check_in:
            return self.check_in.hour >= 9 and (
                self.check_in.hour > 9 or self.check_in.minute > 0
            )
        return False


class LeaveRequest(BaseModel):
    """휴가 신청"""

    class LeaveType(models.TextChoices):
        ANNUAL = 'ANNUAL', '연차'
        HALF_AM = 'HALF_AM', '오전반차'
        HALF_PM = 'HALF_PM', '오후반차'
        SICK = 'SICK', '병가'
        SPECIAL = 'SPECIAL', '특별휴가'

    class LeaveStatus(models.TextChoices):
        PENDING = 'PENDING', '대기'
        APPROVED = 'APPROVED', '승인'
        REJECTED = 'REJECTED', '반려'
        CANCELLED = 'CANCELLED', '취소'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='신청자',
        on_delete=models.PROTECT,
        related_name='leave_requests',
    )
    leave_type = models.CharField(
        '휴가 유형',
        max_length=20,
        choices=LeaveType.choices,
    )
    start_date = models.DateField('시작일')
    end_date = models.DateField('종료일')
    days = models.DecimalField(
        '사용 일수',
        max_digits=3,
        decimal_places=1,
    )
    reason = models.TextField('사유')
    status = models.CharField(
        '상태',
        max_length=20,
        choices=LeaveStatus.choices,
        default=LeaveStatus.PENDING,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='승인자',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_leaves',
    )
    approved_at = models.DateTimeField('승인일시', null=True, blank=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = '휴가 신청'
        verbose_name_plural = '휴가 신청'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user} - {self.get_leave_type_display()} ({self.start_date}~{self.end_date})'


class AnnualLeaveBalance(BaseModel):
    """연차 잔여"""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name='사용자',
        on_delete=models.PROTECT,
        related_name='leave_balances',
    )
    year = models.PositiveIntegerField('연도')
    total_days = models.DecimalField(
        '총 연차',
        max_digits=4,
        decimal_places=1,
        default=Decimal('15'),
    )
    used_days = models.DecimalField(
        '사용 연차',
        max_digits=4,
        decimal_places=1,
        default=Decimal('0'),
    )

    history = HistoricalRecords()

    class Meta:
        verbose_name = '연차 잔여'
        verbose_name_plural = '연차 잔여'
        unique_together = ['user', 'year']

    def __str__(self):
        return f'{self.user} - {self.year}년 연차'

    @property
    def remaining_days(self):
        """잔여 연차"""
        return self.total_days - self.used_days
