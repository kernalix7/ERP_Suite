"""HR 앱 Celery 태스크"""
from celery import shared_task


@shared_task
def check_labor_compliance_weekly():
    """매주 월요일 실행 — 근로기준법 위반 시 관리자에게 Notification"""
    from datetime import date, timedelta
    from apps.hr.models import EmployeeProfile
    from apps.hr.labor_compliance import check_all

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    violations = []
    employees = EmployeeProfile.objects.filter(
        is_active=True, status=EmployeeProfile.Status.ACTIVE,
    ).select_related('user')

    for emp in employees:
        result = check_all(emp)
        if not result['is_compliant']:
            violation_details = []
            if not result['weekly_hours']['is_compliant']:
                violation_details.append(
                    f"주간근로 {result['weekly_hours']['total_hours']}h "
                    f"(한도 {result['weekly_hours']['limit']}h 초과)"
                )
            if not result['minimum_wage']['is_compliant']:
                violation_details.append(
                    f"최저시급 미달 {result['minimum_wage']['hourly_wage']:.0f}원 "
                    f"(기준 {result['minimum_wage']['min_wage']:.0f}원)"
                )
            if not result['annual_leave']['is_compliant']:
                violation_details.append(
                    f"연차 초과 사용 {result['annual_leave']['used_days']}일 "
                    f"(법정 {result['annual_leave']['entitled_days']}일)"
                )
            violations.append({'employee': emp, 'details': violation_details})

    if violations:
        from apps.core.notification import create_notification
        lines = [f"- {v['employee']}: {', '.join(v['details'])}" for v in violations]
        message = f"[근로기준법 준수 점검 {week_start}]\n위반 {len(violations)}건:\n" + "\n".join(lines)
        create_notification(
            users='manager',
            title='근로기준법 준수 위반 감지',
            message=message,
        )

    return f'점검 완료: {len(violations)}건 위반'
