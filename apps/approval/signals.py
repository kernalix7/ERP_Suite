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
    결재 단계 상태 변경 시 자동 처리.

    SEQUENTIAL 또는 같은 step_order에 Step 1개 — 기존 직렬 동작.
    PARALLEL ALL — 같은 order 전원 APPROVED 필요.
    PARALLEL ANY — 같은 order 1인 APPROVED 시 나머지 SKIPPED + 다음 이동.
    REJECTED — 즉시 Request REJECTED, 이후 order는 손대지 않음.
    """
    if instance.status in (ApprovalStep.Status.PENDING, ApprovalStep.Status.SKIPPED):
        return

    approval = instance.request

    if approval.status in ('APPROVED', 'REJECTED', 'CANCELLED'):
        return

    with transaction.atomic():
        # 반려: 즉시 전체 반려
        if instance.status == ApprovalStep.Status.REJECTED:
            approval.status = 'REJECTED'
            approval.reject_reason = instance.comment or ''
            approval.save(update_fields=[
                'status', 'reject_reason', 'updated_at',
            ])
            return

        # 승인 처리
        if instance.status != ApprovalStep.Status.APPROVED:
            return

        current_order = instance.step_order
        sibling_qs = approval.steps.filter(step_order=current_order)
        mode = instance.parallel_mode or ApprovalStep.ParallelMode.SEQUENTIAL

        if mode == ApprovalStep.ParallelMode.ANY:
            # 나머지 PENDING을 SKIPPED로
            (
                sibling_qs
                .filter(status=ApprovalStep.Status.PENDING)
                .exclude(pk=instance.pk)
                .update(
                    status=ApprovalStep.Status.SKIPPED,
                    acted_at=timezone.now(),
                    updated_at=timezone.now(),
                )
            )
            _advance_to_next_order(approval, current_order)
            return

        if mode == ApprovalStep.ParallelMode.ALL:
            remaining_pending = sibling_qs.filter(
                status=ApprovalStep.Status.PENDING,
            ).exists()
            if remaining_pending:
                # 아직 대기중인 병렬 결재자 있음 — 유지
                return
            _advance_to_next_order(approval, current_order)
            return

        # SEQUENTIAL (기존 직렬 동작)
        _advance_to_next_order(approval, current_order)


def _advance_to_next_order(approval, current_order):
    """현재 order 통과 처리 — 다음 order 활성 or 최종 승인."""
    next_step = (
        approval.steps
        .filter(
            step_order__gt=current_order,
            status=ApprovalStep.Status.PENDING,
        )
        .order_by('step_order')
        .first()
    )
    if next_step:
        approval.current_step = next_step.step_order
        approval.save(update_fields=['current_step', 'updated_at'])
        _notify_next_approvers(approval, next_step.step_order)
    else:
        approval.status = 'APPROVED'
        approval.approved_at = timezone.now()
        approval.save(update_fields=[
            'status', 'approved_at', 'updated_at',
        ])
        _handle_permission_approval(approval)


def _notify_next_approvers(approval, step_order):
    """다음 order의 PENDING 결재자들에게 알림."""
    try:
        from apps.core.notification import create_notification
    except ImportError:
        return
    approvers = list(
        approval.steps
        .filter(step_order=step_order, status=ApprovalStep.Status.PENDING)
        .select_related('approver')
        .values_list('approver', flat=True)
    )
    if not approvers:
        return
    from apps.accounts.models import User
    users = User.objects.filter(pk__in=approvers)
    create_notification(
        list(users),
        '결재 차례 도착',
        f'[{approval.title}] 결재가 귀하의 차례입니다.',
        noti_type='SYSTEM',
        link=f'/approval/{approval.request_number}/',
    )


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
