import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import EmployeeProfile, PersonnelAction

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=PersonnelAction)
def apply_personnel_action(sender, instance, created, **kwargs):
    """인사발령 저장 시 직원 프로필에 부서/직급/상태 자동 반영 + User 계정 처리"""
    # 수정 시 update_fields에 status가 없으면 재진입으로 간주하고 건너뜀
    update_fields = kwargs.get('update_fields')
    if not created and update_fields is not None and 'status' not in update_fields:
        return

    # 미래 발령은 즉시 적용하지 않음
    from datetime import date as _date
    if instance.effective_date > _date.today():
        return

    with transaction.atomic():
        emp = instance.employee
        updated_fields = []

        if instance.to_department:
            emp.department = instance.to_department
            updated_fields.append('department')

        if instance.to_position:
            emp.position = instance.to_position
            updated_fields.append('position')

        if instance.action_type == 'RESIGNATION':
            emp.status = 'RESIGNED'
            emp.resignation_date = instance.effective_date
            updated_fields.extend(['status', 'resignation_date'])
            # 퇴사 시 User 계정 비활성화
            emp.user.is_active = False
            emp.user.save(update_fields=['is_active'])
        elif instance.action_type == 'LEAVE':
            emp.status = 'ON_LEAVE'
            updated_fields.append('status')
        elif instance.action_type == 'HIRE':
            emp.status = 'ACTIVE'
            updated_fields.append('status')
            # 입사 시 User 계정 생성 또는 재활성화
            existing_user = getattr(emp, 'user', None)
            if existing_user and existing_user.pk:
                # 이미 연결된 User가 있으면 재활성화
                existing_user.is_active = True
                existing_user.save(update_fields=['is_active'])
            else:
                # 새 User 생성 (사번=username)
                password = emp.employee_number + '!'
                new_user = User.objects.create_user(
                    username=emp.employee_number,
                    password=password,
                    name=emp.user.name if hasattr(emp, 'user') and emp.user_id else '',
                    role='staff',
                    is_active=True,
                )
                emp.user = new_user
                updated_fields.append('user')
        elif instance.action_type == 'RETURN':
            emp.status = 'ACTIVE'
            updated_fields.append('status')
            # 복직 시 User 계정 재활성화
            emp.user.is_active = True
            emp.user.save(update_fields=['is_active'])
        elif instance.action_type == 'MANAGER_APPOINT':
            # 부서장 임명: to_department의 manager를 해당 직원으로 설정
            if instance.to_department:
                # 기존에 다른 부서의 부서장이었으면 해제
                from .models import Department
                Department.objects.filter(
                    manager=emp.user, is_active=True,
                ).exclude(pk=instance.to_department.pk).update(manager=None)
                # 대상 부서의 부서장 설정
                instance.to_department.manager = emp.user
                instance.to_department.save(update_fields=['manager', 'updated_at'])
                # 부서 이동도 겸하는 경우
                if emp.department != instance.to_department:
                    emp.department = instance.to_department
                    updated_fields.append('department')

        if updated_fields:
            emp.save(update_fields=updated_fields + ['updated_at'])


@receiver(post_save, sender=EmployeeProfile)
def sync_employee_bank_account(sender, instance, **kwargs):
    """직원 계좌정보 변경 시 회계 BankAccount(PERSONAL) 자동 생성/갱신"""
    if not instance.bank_name or not instance.bank_account:
        return

    try:
        from apps.accounting.models import BankAccount, AccountCode
    except ImportError:
        return

    user_name = instance.user.name or instance.user.username

    # 보통예금(1110) 계정과목 자동 매핑
    deposit_account = AccountCode.objects.filter(
        code='1110', is_active=True,
    ).first()

    with transaction.atomic():
        acct, created = BankAccount.objects.update_or_create(
            employee=instance,
            defaults={
                'name': f'{user_name} 급여계좌',
                'account_type': BankAccount.AccountType.PERSONAL,
                'owner': user_name,
                'bank': instance.bank_name,
                'account_number': instance.bank_account,
                'account_code': deposit_account,
                'is_active': instance.is_active,
            },
        )
        if created:
            logger.info('BankAccount created for employee %s', instance.employee_number)
