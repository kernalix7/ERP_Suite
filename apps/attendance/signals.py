import math
from decimal import Decimal

from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AnnualLeaveBalance, AttendanceRecord, LeaveRequest


@receiver(post_save, sender=LeaveRequest)
def update_leave_balance(sender, instance, created, **kwargs):
    """
    휴가 신청 상태 변경 시 연차 잔여일수 자동 갱신.
    - APPROVED: used_days 증가
    - CANCELLED: 기존에 APPROVED였던 경우 used_days 복원
    """
    # ANNUAL, HALF_AM, HALF_PM 유형만 연차 잔액에 영향
    annual_types = {
        LeaveRequest.LeaveType.ANNUAL,
        LeaveRequest.LeaveType.HALF_AM,
        LeaveRequest.LeaveType.HALF_PM,
    }
    if instance.leave_type not in annual_types:
        return

    year = instance.start_date.year

    if instance.status == LeaveRequest.LeaveStatus.APPROVED:
        # 새 레코드이거나 이전 상태가 APPROVED가 아닐 때만 차감 (이중 차감 방지)
        if not created:
            try:
                prev = instance.history.order_by('-history_date')[1]
                already_approved = prev.status == LeaveRequest.LeaveStatus.APPROVED
            except IndexError:
                already_approved = False
            if already_approved:
                return

        with transaction.atomic():
            balance, _ = AnnualLeaveBalance.objects.get_or_create(
                user=instance.user,
                year=year,
                defaults={
                    'total_days': Decimal('15'),
                    'created_by': instance.user,
                },
            )
            AnnualLeaveBalance.objects.filter(pk=balance.pk).update(
                used_days=F('used_days') + instance.days,
            )

    elif instance.status == LeaveRequest.LeaveStatus.CANCELLED:
        # 이전에 승인된 적 있는 경우에만 복원
        # simple_history를 통해 이전 상태 확인
        try:
            prev = instance.history.order_by('-history_date')[1]
            was_approved = prev.status == LeaveRequest.LeaveStatus.APPROVED
        except IndexError:
            was_approved = False

        if was_approved:
            with transaction.atomic():
                updated = AnnualLeaveBalance.objects.filter(
                    user=instance.user,
                    year=year,
                    used_days__gte=instance.days,
                ).update(
                    used_days=F('used_days') - instance.days,
                )
                if not updated:
                    # used_days가 days보다 작은 경우 0으로 클램핑
                    AnnualLeaveBalance.objects.filter(
                        user=instance.user,
                        year=year,
                    ).update(used_days=Decimal('0'))


@receiver(post_save, sender=AttendanceRecord)
def update_attendance_duration(sender, instance, **kwargs):
    """
    check_in + check_out 이 모두 있으면 overtime_hours 자동계산.
    기본 근무시간(8시간) 초과분을 0.5h 단위로 기록.
    """
    if not (instance.check_in and instance.check_out):
        return

    delta = instance.check_out - instance.check_in
    total_hours = delta.total_seconds() / 3600
    standard_hours = 8.0
    overtime = max(total_hours - standard_hours, 0)
    # 0.5시간 단위 올림 (예: 1.25h → 1.5h)
    overtime_rounded = Decimal(str(math.ceil(overtime * 2) / 2))

    if instance.overtime_hours != overtime_rounded:
        AttendanceRecord.objects.filter(pk=instance.pk).update(
            overtime_hours=overtime_rounded,
        )
