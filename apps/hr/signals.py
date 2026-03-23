from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PersonnelAction


@receiver(post_save, sender=PersonnelAction)
def apply_personnel_action(sender, instance, **kwargs):
    """인사발령 저장 시 직원 프로필에 부서/직급/상태 자동 반영"""
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
        elif instance.action_type == 'LEAVE':
            emp.status = 'ON_LEAVE'
            updated_fields.append('status')
        elif instance.action_type in ('RETURN', 'HIRE'):
            emp.status = 'ACTIVE'
            updated_fields.append('status')

        if updated_fields:
            emp.save(update_fields=updated_fields + ['updated_at'])
