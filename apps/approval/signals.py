import logging

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.approval.models import ApprovalStep

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ApprovalStep)
def handle_approval_step_change(sender, instance, **kwargs):
    """
    결재 단계 상태 변경 시 자동 처리:
    - APPROVED: 다음 Step 자동활성화, 최종이면 ApprovalRequest APPROVED
    - REJECTED: ApprovalRequest REJECTED 자동전환
    """
    if instance.status == 'PENDING':
        return

    approval = instance.request

    # 이미 완료된 결재는 무시
    if approval.status in ('APPROVED', 'REJECTED', 'CANCELLED'):
        return

    with transaction.atomic():
        if instance.status == 'APPROVED':
            # 다음 단계 확인
            next_step = (
                approval.steps
                .filter(
                    step_order__gt=instance.step_order,
                    status='PENDING',
                )
                .order_by('step_order')
                .first()
            )
            if next_step:
                # 다음 단계로 이동
                approval.current_step = next_step.step_order
                approval.save(update_fields=['current_step', 'updated_at'])
            else:
                # 최종 단계 승인 — 전체 승인
                approval.status = 'APPROVED'
                approval.approved_at = timezone.now()
                approval.save(update_fields=[
                    'status', 'approved_at', 'updated_at',
                ])
                # 권한 신청 승인 시 User.role 자동 업데이트
                _handle_permission_approval(approval)

        elif instance.status == 'REJECTED':
            # 하나라도 반려면 전체 반려
            approval.status = 'REJECTED'
            approval.reject_reason = instance.comment or ''
            approval.save(update_fields=[
                'status', 'reject_reason', 'updated_at',
            ])


def _handle_permission_approval(approval):
    """권한 신청 승인 시 User.role 자동 업데이트"""
    if not approval.content_type or not approval.object_id:
        return

    from apps.accounts.models import User
    user_ct = ContentType.objects.get_for_model(User)

    if approval.content_type_id != user_ct.id:
        return

    try:
        user = User.objects.get(pk=approval.object_id)
    except User.DoesNotExist:
        return

    # content에서 신청 역할 추출 ("신청 역할: 매니저" 형식)
    role_map = {'관리자': 'admin', '매니저': 'manager', '직원': 'staff'}
    new_role = None
    for line in approval.content.splitlines():
        if line.startswith('신청 역할:'):
            role_name = line.split(':', 1)[1].strip()
            new_role = role_map.get(role_name)
            break

    if new_role and new_role != user.role:
        old_role = user.get_role_display()
        user.role = new_role
        user.save(update_fields=['role'])
        logger.info(
            '권한 변경: %s (%s → %s) [결재 %s]',
            user.username, old_role, user.get_role_display(),
            approval.request_number,
        )
