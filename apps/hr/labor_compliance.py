"""근로기준법 준수 체크 유틸리티"""
from datetime import date, timedelta
from decimal import Decimal


def _get_labor_config(year):
    from .models import LaborConfig
    return LaborConfig.objects.filter(year=year, is_active=True).first()


def check_weekly_hours(employee, week_start_date):
    """주간 근로시간이 법정 최대(기본 52시간)를 초과하는지 확인"""
    from apps.attendance.models import AttendanceRecord

    week_end_date = week_start_date + timedelta(days=6)
    config = _get_labor_config(week_start_date.year)
    max_hours = config.max_weekly_hours if config else 52

    records = AttendanceRecord.objects.filter(
        user=employee.user,
        date__gte=week_start_date,
        date__lte=week_end_date,
        is_active=True,
    )
    total_hours = Decimal('0')
    for record in records:
        total_hours += Decimal(str(record.work_hours or 0))

    return {
        'is_compliant': total_hours <= max_hours,
        'total_hours': float(total_hours),
        'limit': max_hours,
        'week_start': week_start_date,
        'week_end': week_end_date,
    }


def check_minimum_wage(employee, year):
    """월 급여 ÷ 월 근로시간이 최저시급 이상인지 확인"""
    from apps.hr.models import Payroll
    from apps.attendance.models import AttendanceRecord

    config = _get_labor_config(year)
    min_wage = config.min_hourly_wage if config else Decimal('0')

    payrolls = Payroll.objects.filter(
        employee=employee,
        year=year,
        is_active=True,
    )
    if not payrolls.exists():
        return {
            'is_compliant': True,
            'hourly_wage': 0,
            'min_wage': float(min_wage),
            'message': '급여 데이터 없음',
        }

    total_gross = sum(p.gross_pay for p in payrolls)
    avg_monthly = total_gross / payrolls.count()

    # 월 근로시간: 해당 연도 출근 기록 기반 평균
    attendance_qs = AttendanceRecord.objects.filter(
        user=employee.user,
        date__year=year,
        is_active=True,
    )
    total_att_hours = sum(
        Decimal(str(r.work_hours or 0)) for r in attendance_qs
    )
    month_count = payrolls.count()
    avg_monthly_hours = total_att_hours / month_count if month_count else Decimal('160')

    hourly_wage = avg_monthly / avg_monthly_hours if avg_monthly_hours else Decimal('0')
    return {
        'is_compliant': hourly_wage >= min_wage,
        'hourly_wage': float(hourly_wage),
        'min_wage': float(min_wage),
    }


def check_annual_leave(employee):
    """법정 연차 부여 여부 확인"""
    from apps.attendance.models import AnnualLeaveBalance

    years = employee.years_of_service
    if years < 1:
        entitled = int(years * 12)  # 1년 미만: 월 1일
    elif years < 3:
        entitled = 15
    else:
        entitled = 15 + int((years - 1) // 2)

    balance = AnnualLeaveBalance.objects.filter(
        user=employee.user,
        year=date.today().year,
        is_active=True,
    ).first()

    used_days = float(balance.used_days) if balance else 0
    remaining = entitled - used_days

    return {
        'is_compliant': remaining >= 0,
        'entitled_days': entitled,
        'used_days': used_days,
        'remaining': remaining,
        'years_of_service': float(years),
    }


def check_all(employee):
    """모든 컴플라이언스 항목 종합 점검"""
    today = date.today()
    # 이번 주 월요일
    week_start = today - timedelta(days=today.weekday())

    weekly = check_weekly_hours(employee, week_start)
    wage = check_minimum_wage(employee, today.year)
    leave = check_annual_leave(employee)

    is_all_compliant = weekly['is_compliant'] and wage['is_compliant'] and leave['is_compliant']

    return {
        'is_compliant': is_all_compliant,
        'weekly_hours': weekly,
        'minimum_wage': wage,
        'annual_leave': leave,
    }
