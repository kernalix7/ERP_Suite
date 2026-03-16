from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView, TemplateView

from apps.accounts.models import User
from apps.core.mixins import ManagerRequiredMixin
from .models import AttendanceRecord, LeaveRequest, AnnualLeaveBalance
from .forms import LeaveRequestForm


class AttendanceDashboardView(LoginRequiredMixin, TemplateView):
    """출근 대시보드 - 오늘 출근 현황, 부재자, 이번 달 통계"""
    template_name = 'attendance/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        now = timezone.localtime()
        user = self.request.user

        # 내 오늘 출퇴근 기록
        my_record = AttendanceRecord.objects.filter(
            user=user, date=today
        ).first()
        context['my_record'] = my_record
        context['current_time'] = now

        # 오늘 출근 현황
        today_records = AttendanceRecord.objects.filter(date=today)
        context['today_checked_in'] = today_records.filter(
            check_in__isnull=False
        ).count()
        context['today_checked_out'] = today_records.filter(
            check_out__isnull=False
        ).count()

        # 전체 직원 수
        total_staff = User.objects.filter(is_active=True).count()
        context['total_staff'] = total_staff
        context['today_absent'] = total_staff - today_records.filter(
            check_in__isnull=False
        ).count()

        # 이번 달 내 통계
        month_start = today.replace(day=1)
        my_month_records = AttendanceRecord.objects.filter(
            user=user,
            date__gte=month_start,
            date__lte=today,
        )
        context['month_work_days'] = my_month_records.filter(
            check_in__isnull=False
        ).count()
        context['month_late'] = my_month_records.filter(
            status=AttendanceRecord.Status.LATE
        ).count()
        context['month_overtime'] = my_month_records.aggregate(
            total=Sum('overtime_hours')
        )['total'] or Decimal('0')

        return context


class CheckInView(LoginRequiredMixin, View):
    """출근 기록"""

    def post(self, request):
        today = timezone.localdate()
        now = timezone.localtime()

        record, created = AttendanceRecord.objects.get_or_create(
            user=request.user,
            date=today,
            defaults={
                'check_in': now,
                'created_by': request.user,
            }
        )

        if not created:
            if record.check_in:
                messages.warning(request, '이미 출근 기록이 있습니다.')
            else:
                record.check_in = now
                record.save(update_fields=['check_in', 'updated_at'])
                messages.success(request, f'출근 완료 ({now.strftime("%H:%M")})')
        else:
            # 09:00 이후 출근 시 지각 처리
            if record.is_late:
                record.status = AttendanceRecord.Status.LATE
                record.save(update_fields=['status'])
            messages.success(request, f'출근 완료 ({now.strftime("%H:%M")})')

        return redirect('attendance:dashboard')


class CheckOutView(LoginRequiredMixin, View):
    """퇴근 기록"""

    def post(self, request):
        today = timezone.localdate()
        now = timezone.localtime()

        record = AttendanceRecord.objects.filter(
            user=request.user, date=today
        ).first()

        if not record or not record.check_in:
            messages.warning(request, '출근 기록이 없습니다.')
            return redirect('attendance:dashboard')

        if record.check_out:
            messages.warning(request, '이미 퇴근 기록이 있습니다.')
            return redirect('attendance:dashboard')

        record.check_out = now
        # 8시간 초과 시 초과근무 계산
        work_hours = record.work_hours
        if work_hours and work_hours > 8:
            record.overtime_hours = Decimal(str(round(work_hours - 8, 1)))
        record.save(update_fields=['check_out', 'overtime_hours', 'updated_at'])

        messages.success(request, f'퇴근 완료 ({now.strftime("%H:%M")})')
        return redirect('attendance:dashboard')


class AttendanceListView(LoginRequiredMixin, ListView):
    """내 출퇴근 이력 (월별)"""
    model = AttendanceRecord
    template_name = 'attendance/record_list.html'
    context_object_name = 'records'
    paginate_by = 31

    def get_queryset(self):
        today = timezone.localdate()
        year = int(self.request.GET.get('year', today.year))
        month = int(self.request.GET.get('month', today.month))
        return AttendanceRecord.objects.filter(
            user=self.request.user,
            date__year=year,
            date__month=month,
        ).order_by('-date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        context['selected_year'] = int(self.request.GET.get('year', today.year))
        context['selected_month'] = int(self.request.GET.get('month', today.month))
        context['years'] = range(today.year - 2, today.year + 1)
        context['months'] = range(1, 13)
        return context


class AttendanceAdminView(ManagerRequiredMixin, ListView):
    """전체 직원 출퇴근 관리"""
    model = AttendanceRecord
    template_name = 'attendance/admin_list.html'
    context_object_name = 'records'

    def get_queryset(self):
        today = timezone.localdate()
        date = self.request.GET.get('date', str(today))
        return AttendanceRecord.objects.filter(
            date=date
        ).select_related('user').order_by('user__name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        context['selected_date'] = self.request.GET.get('date', str(today))

        # 출근하지 않은 직원
        checked_in_users = AttendanceRecord.objects.filter(
            date=context['selected_date'],
            check_in__isnull=False,
        ).values_list('user_id', flat=True)
        context['absent_users'] = User.objects.filter(
            is_active=True
        ).exclude(id__in=checked_in_users)

        return context


class LeaveRequestListView(LoginRequiredMixin, ListView):
    """내 휴가 신청 목록"""
    model = LeaveRequest
    template_name = 'attendance/leave_list.html'
    context_object_name = 'leaves'
    paginate_by = 20

    def get_queryset(self):
        return LeaveRequest.objects.filter(
            user=self.request.user
        ).order_by('-created_at')


class LeaveRequestCreateView(LoginRequiredMixin, CreateView):
    """휴가 신청"""
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'attendance/leave_form.html'
    success_url = reverse_lazy('attendance:leave_list')

    def form_valid(self, form):
        leave = form.save(commit=False)
        leave.user = self.request.user
        leave.created_by = self.request.user

        # 일수 자동 계산
        if leave.leave_type in ('HALF_AM', 'HALF_PM'):
            leave.days = Decimal('0.5')
        else:
            delta = (leave.end_date - leave.start_date).days + 1
            leave.days = Decimal(str(delta))

        leave.save()
        messages.success(self.request, '휴가 신청이 완료되었습니다.')
        return redirect(self.success_url)


class LeaveApproveView(ManagerRequiredMixin, View):
    """휴가 승인/반려"""

    def post(self, request, pk):
        leave = get_object_or_404(LeaveRequest, pk=pk)
        action = request.POST.get('action')

        if action == 'approve':
            leave.status = LeaveRequest.LeaveStatus.APPROVED
            leave.approved_by = request.user
            leave.approved_at = timezone.now()
            leave.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

            # 연차 사용일수 업데이트
            if leave.leave_type in ('ANNUAL', 'HALF_AM', 'HALF_PM'):
                balance, _ = AnnualLeaveBalance.objects.get_or_create(
                    user=leave.user,
                    year=leave.start_date.year,
                    defaults={'created_by': request.user},
                )
                balance.used_days += leave.days
                balance.save(update_fields=['used_days', 'updated_at'])

            messages.success(request, '휴가가 승인되었습니다.')

        elif action == 'reject':
            leave.status = LeaveRequest.LeaveStatus.REJECTED
            leave.approved_by = request.user
            leave.approved_at = timezone.now()
            leave.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])
            messages.success(request, '휴가가 반려되었습니다.')

        return redirect('attendance:leave_list')


class LeaveBalanceView(LoginRequiredMixin, TemplateView):
    """내 연차 잔여 조회"""
    template_name = 'attendance/leave_balance.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        balance, _ = AnnualLeaveBalance.objects.get_or_create(
            user=self.request.user,
            year=today.year,
            defaults={'created_by': self.request.user},
        )
        context['balance'] = balance

        # 올해 휴가 사용 내역
        context['used_leaves'] = LeaveRequest.objects.filter(
            user=self.request.user,
            status=LeaveRequest.LeaveStatus.APPROVED,
            start_date__year=today.year,
        ).order_by('-start_date')

        return context
