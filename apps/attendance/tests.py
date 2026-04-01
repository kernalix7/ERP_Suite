from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

from apps.attendance.models import (
    AttendanceRecord, LeaveRequest, AnnualLeaveBalance,
)

User = get_user_model()


class AttendanceRecordModelTest(TestCase):
    """출퇴근 기록 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='attuser', password='testpass123',
            role='staff', name='출퇴근유저',
        )

    def test_record_creation(self):
        """출퇴근 기록 생성"""
        now = timezone.now()
        record = AttendanceRecord.objects.create(
            user=self.user,
            date=date.today(),
            check_in=now,
            created_by=self.user,
        )
        self.assertEqual(record.user, self.user)
        self.assertEqual(record.date, date.today())
        self.assertIsNotNone(record.check_in)

    def test_record_str(self):
        """출퇴근 기록 문자열 표현"""
        record = AttendanceRecord.objects.create(
            user=self.user,
            date=date(2026, 3, 17),
            created_by=self.user,
        )
        self.assertIn('출퇴근유저', str(record))
        self.assertIn('2026-03-17', str(record))

    def test_unique_together_user_date(self):
        """같은 사용자/날짜 중복 불가"""
        AttendanceRecord.objects.create(
            user=self.user,
            date=date.today(),
            created_by=self.user,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            AttendanceRecord.objects.create(
                user=self.user,
                date=date.today(),
                created_by=self.user,
            )

    def test_work_hours_calculation(self):
        """근무 시간 계산"""
        check_in = timezone.now().replace(hour=9, minute=0, second=0)
        check_out = check_in + timedelta(hours=8, minutes=30)
        record = AttendanceRecord.objects.create(
            user=self.user,
            date=date.today(),
            check_in=check_in,
            check_out=check_out,
            created_by=self.user,
        )
        self.assertEqual(record.work_hours, 8.5)

    def test_work_hours_no_checkout(self):
        """퇴근 기록이 없으면 근무시간 0"""
        record = AttendanceRecord.objects.create(
            user=self.user,
            date=date.today(),
            check_in=timezone.now(),
            created_by=self.user,
        )
        self.assertEqual(record.work_hours, 0)

    def test_work_hours_no_checkin(self):
        """출근 기록이 없으면 근무시간 0"""
        record = AttendanceRecord.objects.create(
            user=self.user,
            date=date.today(),
            created_by=self.user,
        )
        self.assertEqual(record.work_hours, 0)

    def test_is_late_true(self):
        """09시 이후 출근 시 지각"""
        late_time = timezone.now().replace(hour=9, minute=30, second=0)
        record = AttendanceRecord(
            user=self.user,
            date=date.today(),
            check_in=late_time,
        )
        self.assertTrue(record.is_late)

    def test_is_late_false(self):
        """09시 이전 출근 시 정상"""
        early_time = timezone.now().replace(hour=8, minute=30, second=0)
        record = AttendanceRecord(
            user=self.user,
            date=date.today(),
            check_in=early_time,
        )
        self.assertFalse(record.is_late)

    def test_is_late_exactly_nine(self):
        """정각 09:00 출근은 정상"""
        on_time = timezone.now().replace(hour=9, minute=0, second=0)
        record = AttendanceRecord(
            user=self.user,
            date=date.today(),
            check_in=on_time,
        )
        self.assertFalse(record.is_late)

    def test_is_late_no_checkin(self):
        """출근 기록 없으면 지각 아님"""
        record = AttendanceRecord(
            user=self.user,
            date=date.today(),
        )
        self.assertFalse(record.is_late)

    def test_status_choices(self):
        """출퇴근 상태 선택지"""
        choices = dict(AttendanceRecord.Status.choices)
        self.assertIn('NORMAL', choices)
        self.assertIn('LATE', choices)
        self.assertIn('EARLY_LEAVE', choices)
        self.assertIn('ABSENT', choices)

    def test_default_status_normal(self):
        """기본 상태는 정상"""
        record = AttendanceRecord.objects.create(
            user=self.user,
            date=date.today(),
            created_by=self.user,
        )
        self.assertEqual(record.status, AttendanceRecord.Status.NORMAL)


class LeaveRequestModelTest(TestCase):
    """휴가 신청 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='leaveuser', password='testpass123',
            role='staff', name='휴가유저',
        )
        self.manager = User.objects.create_user(
            username='leavemanager', password='testpass123',
            role='manager', name='관리매니저',
        )

    def test_leave_request_creation(self):
        """휴가 신청 생성"""
        leave = LeaveRequest.objects.create(
            user=self.user,
            leave_type=LeaveRequest.LeaveType.ANNUAL,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 3),
            days=Decimal('3'),
            reason='개인 사유',
            created_by=self.user,
        )
        self.assertEqual(leave.user, self.user)
        self.assertEqual(leave.leave_type, 'ANNUAL')
        self.assertEqual(leave.status, LeaveRequest.LeaveStatus.PENDING)

    def test_leave_request_str(self):
        """휴가 신청 문자열 표현"""
        leave = LeaveRequest.objects.create(
            user=self.user,
            leave_type=LeaveRequest.LeaveType.ANNUAL,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 3),
            days=Decimal('3'),
            reason='테스트',
            created_by=self.user,
        )
        self.assertIn('휴가유저', str(leave))
        self.assertIn('연차', str(leave))

    def test_leave_approval_flow(self):
        """휴가 승인 워크플로우: PENDING -> APPROVED"""
        leave = LeaveRequest.objects.create(
            user=self.user,
            leave_type=LeaveRequest.LeaveType.ANNUAL,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 1),
            days=Decimal('1'),
            reason='테스트',
            created_by=self.user,
        )
        self.assertEqual(leave.status, 'PENDING')

        leave.status = LeaveRequest.LeaveStatus.APPROVED
        leave.approved_by = self.manager
        leave.approved_at = timezone.now()
        leave.save()
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'APPROVED')
        self.assertEqual(leave.approved_by, self.manager)
        self.assertIsNotNone(leave.approved_at)

    def test_leave_rejection_flow(self):
        """휴가 반려 워크플로우: PENDING -> REJECTED"""
        leave = LeaveRequest.objects.create(
            user=self.user,
            leave_type=LeaveRequest.LeaveType.SICK,
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 5),
            days=Decimal('5'),
            reason='테스트',
            created_by=self.user,
        )
        leave.status = LeaveRequest.LeaveStatus.REJECTED
        leave.approved_by = self.manager
        leave.approved_at = timezone.now()
        leave.save()
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'REJECTED')

    def test_leave_type_choices(self):
        """휴가 유형 선택지"""
        choices = dict(LeaveRequest.LeaveType.choices)
        self.assertIn('ANNUAL', choices)
        self.assertIn('HALF_AM', choices)
        self.assertIn('HALF_PM', choices)
        self.assertIn('SICK', choices)
        self.assertIn('SPECIAL', choices)


class AnnualLeaveBalanceModelTest(TestCase):
    """연차 잔여 모델 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='balanceuser', password='testpass123',
            role='staff', name='연차유저',
        )

    def test_balance_creation(self):
        """연차 잔여 생성"""
        balance = AnnualLeaveBalance.objects.create(
            user=self.user,
            year=2026,
            total_days=Decimal('15'),
            created_by=self.user,
        )
        self.assertEqual(balance.total_days, Decimal('15'))
        self.assertEqual(balance.used_days, Decimal('0'))

    def test_remaining_days(self):
        """잔여 연차 계산"""
        balance = AnnualLeaveBalance.objects.create(
            user=self.user,
            year=2026,
            total_days=Decimal('15'),
            used_days=Decimal('5'),
            created_by=self.user,
        )
        self.assertEqual(balance.remaining_days, Decimal('10'))

    def test_str(self):
        """연차 잔여 문자열 표현"""
        balance = AnnualLeaveBalance.objects.create(
            user=self.user,
            year=2026,
            total_days=Decimal('15'),
            created_by=self.user,
        )
        self.assertIn('2026', str(balance))
        self.assertIn('연차유저', str(balance))

    def test_unique_together_user_year(self):
        """같은 사용자/연도 중복 불가"""
        AnnualLeaveBalance.objects.create(
            user=self.user,
            year=2026,
            total_days=Decimal('15'),
            created_by=self.user,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            AnnualLeaveBalance.objects.create(
                user=self.user,
                year=2026,
                total_days=Decimal('15'),
                created_by=self.user,
            )

    def test_default_total_days(self):
        """기본 총 연차는 15일"""
        balance = AnnualLeaveBalance.objects.create(
            user=self.user,
            year=2026,
            created_by=self.user,
        )
        self.assertEqual(balance.total_days, Decimal('15'))

    def test_used_days_update(self):
        """사용일수 업데이트 후 잔여 연차 재계산"""
        balance = AnnualLeaveBalance.objects.create(
            user=self.user,
            year=2026,
            total_days=Decimal('15'),
            created_by=self.user,
        )
        balance.used_days += Decimal('3')
        balance.save()
        balance.refresh_from_db()
        self.assertEqual(balance.remaining_days, Decimal('12'))

        balance.used_days += Decimal('0.5')
        balance.save()
        balance.refresh_from_db()
        self.assertEqual(balance.remaining_days, Decimal('11.5'))


class AttendanceViewTest(TestCase):
    """출퇴근 뷰 테스트"""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='attviewuser', password='testpass123',
            role='staff', name='뷰유저',
        )
        self.manager = User.objects.create_user(
            username='attviewmgr', password='testpass123',
            role='manager', name='매니저',
        )

    def test_dashboard_requires_login(self):
        """대시보드 비로그인 접근 불가"""
        response = self.client.get(reverse('attendance:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_accessible(self):
        """대시보드 로그인 후 접근 가능"""
        self.client.force_login(User.objects.get(username='attviewuser'))
        response = self.client.get(reverse('attendance:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_check_in(self):
        """출근 기록 생성"""
        self.client.force_login(User.objects.get(username='attviewuser'))
        response = self.client.post(reverse('attendance:check_in'))
        self.assertEqual(response.status_code, 302)
        record = AttendanceRecord.objects.filter(
            user=self.user, date=timezone.localdate(),
        ).first()
        self.assertIsNotNone(record)
        self.assertIsNotNone(record.check_in)

    def test_check_in_duplicate(self):
        """이중 출근 방지"""
        self.client.force_login(User.objects.get(username='attviewuser'))
        self.client.post(reverse('attendance:check_in'))
        self.client.post(reverse('attendance:check_in'))
        records = AttendanceRecord.objects.filter(
            user=self.user, date=timezone.localdate(),
        )
        self.assertEqual(records.count(), 1)

    def test_check_out_without_check_in(self):
        """출근 없이 퇴근 시도"""
        self.client.force_login(User.objects.get(username='attviewuser'))
        response = self.client.post(reverse('attendance:check_out'))
        self.assertEqual(response.status_code, 302)

    def test_check_out_after_check_in(self):
        """출근 후 퇴근"""
        self.client.force_login(User.objects.get(username='attviewuser'))
        self.client.post(reverse('attendance:check_in'))
        self.client.post(reverse('attendance:check_out'))
        record = AttendanceRecord.objects.get(
            user=self.user, date=timezone.localdate(),
        )
        self.assertIsNotNone(record.check_out)

    def test_admin_view_requires_manager(self):
        """관리자 출퇴근 뷰는 manager 이상 필요"""
        self.client.force_login(User.objects.get(username='attviewuser'))
        response = self.client.get(reverse('attendance:admin_list'))
        self.assertEqual(response.status_code, 403)

    def test_admin_view_accessible_for_manager(self):
        """관리자 출퇴근 뷰 매니저 접근 가능"""
        self.client.force_login(User.objects.get(username='attviewmgr'))
        response = self.client.get(reverse('attendance:admin_list'))
        self.assertEqual(response.status_code, 200)

    def test_leave_approve_requires_manager(self):
        """휴가 승인은 manager 이상 필요"""
        leave = LeaveRequest.objects.create(
            user=self.user,
            leave_type='ANNUAL',
            start_date=date.today(),
            end_date=date.today(),
            days=Decimal('1'),
            reason='테스트',
            created_by=self.user,
        )
        self.client.force_login(User.objects.get(username='attviewuser'))
        response = self.client.post(
            reverse('attendance:leave_approve', kwargs={'pk': leave.pk}),
            {'action': 'approve'},
        )
        self.assertEqual(response.status_code, 403)

    def test_leave_approve_by_manager(self):
        """매니저가 휴가 승인"""
        leave = LeaveRequest.objects.create(
            user=self.user,
            leave_type='ANNUAL',
            start_date=date.today(),
            end_date=date.today(),
            days=Decimal('1'),
            reason='테스트',
            created_by=self.user,
        )
        self.client.force_login(User.objects.get(username='attviewmgr'))
        response = self.client.post(
            reverse('attendance:leave_approve', kwargs={'pk': leave.pk}),
            {'action': 'approve'},
        )
        self.assertEqual(response.status_code, 302)
        leave.refresh_from_db()
        self.assertEqual(leave.status, 'APPROVED')

    def test_leave_approve_updates_balance(self):
        """휴가 승인 시 연차 사용일수 업데이트"""
        leave = LeaveRequest.objects.create(
            user=self.user,
            leave_type='ANNUAL',
            start_date=date.today(),
            end_date=date.today(),
            days=Decimal('1'),
            reason='테스트',
            created_by=self.user,
        )
        self.client.force_login(User.objects.get(username='attviewmgr'))
        self.client.post(
            reverse('attendance:leave_approve', kwargs={'pk': leave.pk}),
            {'action': 'approve'},
        )
        balance = AnnualLeaveBalance.objects.get(
            user=self.user, year=date.today().year,
        )
        self.assertEqual(balance.used_days, Decimal('1'))


class LeaveSignalTest(TestCase):
    """LeaveRequest 시그널 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='signaluser', password='testpass123',
            role='staff', name='시그널유저',
        )
        self.balance = AnnualLeaveBalance.objects.create(
            user=self.user,
            year=date.today().year,
            total_days=Decimal('15'),
            used_days=Decimal('0'),
            created_by=self.user,
        )

    def _make_leave(self, days=Decimal('2'), leave_type='ANNUAL', status='PENDING'):
        return LeaveRequest.objects.create(
            user=self.user,
            leave_type=leave_type,
            start_date=date.today(),
            end_date=date.today(),
            days=days,
            reason='테스트',
            status=status,
            created_by=self.user,
        )

    def test_approval_increases_used_days(self):
        """APPROVED 시 used_days F() 증가"""
        leave = self._make_leave(days=Decimal('3'))
        leave.status = LeaveRequest.LeaveStatus.APPROVED
        leave.save()
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal('3'))

    def test_approval_half_day(self):
        """반차(HALF_AM) 승인 시 0.5일 증가"""
        leave = self._make_leave(days=Decimal('0.5'), leave_type='HALF_AM')
        leave.status = LeaveRequest.LeaveStatus.APPROVED
        leave.save()
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal('0.5'))

    def test_cancelled_after_approved_restores_balance(self):
        """APPROVED 후 CANCELLED 시 used_days 복원"""
        leave = self._make_leave(days=Decimal('2'))
        leave.status = LeaveRequest.LeaveStatus.APPROVED
        leave.save()
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal('2'))

        leave.status = LeaveRequest.LeaveStatus.CANCELLED
        leave.save()
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal('0'))

    def test_rejected_does_not_change_balance(self):
        """REJECTED 상태는 연차 잔액 영향 없음"""
        leave = self._make_leave(days=Decimal('2'))
        leave.status = LeaveRequest.LeaveStatus.REJECTED
        leave.save()
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal('0'))

    def test_sick_leave_does_not_affect_annual_balance(self):
        """병가(SICK)는 연차 잔액 영향 없음"""
        leave = self._make_leave(days=Decimal('5'), leave_type='SICK')
        leave.status = LeaveRequest.LeaveStatus.APPROVED
        leave.save()
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal('0'))

    def test_multiple_approvals_accumulate(self):
        """여러 번 승인 시 누적 계산"""
        leave1 = self._make_leave(days=Decimal('1'))
        leave1.status = LeaveRequest.LeaveStatus.APPROVED
        leave1.save()
        leave2 = self._make_leave(days=Decimal('2'))
        leave2.status = LeaveRequest.LeaveStatus.APPROVED
        leave2.save()
        self.balance.refresh_from_db()
        self.assertEqual(self.balance.used_days, Decimal('3'))

    def test_balance_auto_created_if_missing(self):
        """잔액 레코드 없어도 자동 생성"""
        self.balance.delete()
        other_year_date = date(date.today().year, 1, 15)
        leave = LeaveRequest.objects.create(
            user=self.user,
            leave_type='ANNUAL',
            start_date=other_year_date,
            end_date=other_year_date,
            days=Decimal('1'),
            reason='테스트',
            status='PENDING',
            created_by=self.user,
        )
        leave.status = LeaveRequest.LeaveStatus.APPROVED
        leave.save()
        balance = AnnualLeaveBalance.objects.get(
            user=self.user, year=other_year_date.year,
        )
        self.assertEqual(balance.used_days, Decimal('1'))


class AttendanceSignalTest(TestCase):
    """AttendanceRecord 시그널 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='attrsignaluser', password='testpass123',
            role='staff', name='출퇴근시그널유저',
        )

    def test_overtime_calculated_on_checkin_checkout(self):
        """출퇴근 모두 기록 시 overtime_hours 자동 계산 (8h 초과분)"""
        check_in = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        check_out = check_in + timedelta(hours=10)  # 10h → 2h overtime
        record = AttendanceRecord.objects.create(
            user=self.user,
            date=date.today(),
            check_in=check_in,
            check_out=check_out,
            created_by=self.user,
        )
        record.refresh_from_db()
        self.assertEqual(record.overtime_hours, Decimal('2.0'))

    def test_no_overtime_for_exactly_8_hours(self):
        """정확히 8시간 근무 시 overtime 0"""
        check_in = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        check_out = check_in + timedelta(hours=8)
        record = AttendanceRecord.objects.create(
            user=self.user,
            date=date.today(),
            check_in=check_in,
            check_out=check_out,
            created_by=self.user,
        )
        record.refresh_from_db()
        self.assertEqual(record.overtime_hours, Decimal('0'))

    def test_no_overtime_update_without_checkout(self):
        """퇴근 없으면 overtime 계산 안 함"""
        record = AttendanceRecord.objects.create(
            user=self.user,
            date=date.today(),
            check_in=timezone.now(),
            created_by=self.user,
        )
        record.refresh_from_db()
        self.assertEqual(record.overtime_hours, Decimal('0'))

    def test_overtime_half_hour_rounding(self):
        """초과근무 0.5h 단위 반올림"""
        check_in = timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
        check_out = check_in + timedelta(hours=9, minutes=15)  # 1.25h → rounds to 1.5h
        record = AttendanceRecord.objects.create(
            user=self.user,
            date=date.today(),
            check_in=check_in,
            check_out=check_out,
            created_by=self.user,
        )
        record.refresh_from_db()
        self.assertEqual(record.overtime_hours, Decimal('1.5'))


class LeaveRequestFormTest(TestCase):
    """LeaveRequestForm 폼 테스트"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='formuser', password='testpass123',
            role='staff', name='폼유저',
        )

    def test_valid_form(self):
        """유효한 폼 데이터"""
        from apps.attendance.forms import LeaveRequestForm
        data = {
            'leave_type': 'ANNUAL',
            'start_date': '2026-05-01',
            'end_date': '2026-05-03',
            'reason': '개인 사유',
        }
        form = LeaveRequestForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_end_before_start_invalid(self):
        """종료일이 시작일보다 이른 경우 유효하지 않음"""
        from apps.attendance.forms import LeaveRequestForm
        data = {
            'leave_type': 'ANNUAL',
            'start_date': '2026-05-05',
            'end_date': '2026-05-01',
            'reason': '테스트',
        }
        form = LeaveRequestForm(data=data)
        self.assertFalse(form.is_valid())

    def test_missing_reason_invalid(self):
        """사유 없으면 유효하지 않음"""
        from apps.attendance.forms import LeaveRequestForm
        data = {
            'leave_type': 'ANNUAL',
            'start_date': '2026-05-01',
            'end_date': '2026-05-03',
            'reason': '',
        }
        form = LeaveRequestForm(data=data)
        self.assertFalse(form.is_valid())
