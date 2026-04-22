"""전자결재 서비스 레이어.

- 조건부 결재 매칭 (find_matching_template)
- 위임 자동 치환 (resolve_delegate)
- 템플릿 기반 결재선 자동 생성 (build_steps_from_template)
"""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.approval.models import (
    ApprovalDelegation,
    ApprovalLineTemplate,
    ApprovalStep,
)


# --- 조건부 매칭 ---------------------------------------------------------

def _match_condition(cond: dict, *, category: str, amount, department_id,
                     urgency: str = None) -> bool:
    """단일 템플릿 condition이 기안 입력과 매칭되는지 판정.

    condition 키(모두 선택):
    - category: list[str] — OR 매칭
    - amount_min: int — amount >= amount_min
    - amount_max: int — amount <= amount_max
    - amount_gte / amount_lt: 별칭
    - department_ids: list[int] — OR
    - urgency: list[str] — OR
    조건이 비어있으면 모두 True.
    """
    if not cond:
        return True

    cats = cond.get('category') or []
    if cats and category not in cats:
        return False

    amount_min = cond.get('amount_min', cond.get('amount_gte'))
    if amount_min is not None and amount is not None:
        try:
            if int(amount) < int(amount_min):
                return False
        except (TypeError, ValueError):
            return False

    amount_max = cond.get('amount_max')
    if amount_max is not None and amount is not None:
        try:
            if int(amount) > int(amount_max):
                return False
        except (TypeError, ValueError):
            return False

    amount_lt = cond.get('amount_lt')
    if amount_lt is not None and amount is not None:
        try:
            if int(amount) >= int(amount_lt):
                return False
        except (TypeError, ValueError):
            return False

    dept_ids = cond.get('department_ids') or []
    if dept_ids:
        if department_id is None or int(department_id) not in [int(d) for d in dept_ids]:
            return False

    urgencies = cond.get('urgency') or []
    if urgencies and urgency not in urgencies:
        return False

    return True


def find_matching_template(*, category, amount, department_id, urgency=None):
    """auto_apply=True 템플릿 중 condition 매칭되는 첫 번째(우선순위순) 반환.

    없으면 is_default 템플릿 폴백. 그것도 없으면 None.
    """
    candidates = ApprovalLineTemplate.objects.filter(
        is_active=True, auto_apply=True,
    ).order_by('-priority', '-is_default', 'pk')
    for tpl in candidates:
        if _match_condition(
            tpl.condition or {},
            category=category,
            amount=amount,
            department_id=department_id,
            urgency=urgency,
        ):
            return tpl
    # 폴백: 기본 템플릿
    return ApprovalLineTemplate.objects.filter(
        is_active=True, is_default=True,
    ).order_by('pk').first()


# --- 위임 치환 -----------------------------------------------------------

def resolve_delegate(approver, on_date=None):
    """원 결재자 → 활성 위임이 있으면 대리자로 치환.

    반환: (actual_approver, delegated_from_or_None, delegation_or_None)
    """
    if approver is None:
        return None, None, None
    if on_date is None:
        on_date = timezone.localdate()
    delegation = ApprovalDelegation.objects.filter(
        delegator=approver,
        is_active=True,
        start_date__lte=on_date,
        end_date__gte=on_date,
    ).order_by('-start_date').first()
    if delegation:
        return delegation.delegate, approver, delegation
    return approver, None, None


# 호환성 별칭 — 팀 설계 문서의 네이밍 유지
resolve_approver = resolve_delegate


# --- 결재선 자동 생성 ----------------------------------------------------

@transaction.atomic
def build_steps_from_template(approval, template, actor=None, apply_delegation=False):
    """템플릿 steps JSON → ApprovalStep 생성.

    위임 치환 정책 (스냅샷):
    - 기본값(apply_delegation=False): 원 결재자 그대로 저장. DRAFT 단계에서는
      위임을 적용하지 않는다. 실제 치환은 제출 시점(apply_delegation_on_submit)에
      일괄 수행된다.
    - apply_delegation=True: 즉시 치환. 테스트/제출 직전 재빌드 등 명시적 용도.

    기존 Step이 있으면 모두 삭제 후 재생성.
    """
    from apps.accounts.models import User

    approval.steps.all().delete()

    on_date = timezone.localdate()
    steps_spec = template.steps or []
    created = []
    for entry in steps_spec:
        approver_id = entry.get('approver_id')
        if not approver_id:
            continue
        order = int(entry.get('order', 1))
        mode = entry.get('mode') or ApprovalStep.ParallelMode.SEQUENTIAL
        if mode not in dict(ApprovalStep.ParallelMode.choices):
            mode = ApprovalStep.ParallelMode.SEQUENTIAL
        try:
            user = User.objects.get(pk=approver_id)
        except User.DoesNotExist:
            continue
        if apply_delegation:
            actual, delegated_from, delegation = resolve_delegate(user, on_date)
        else:
            actual, delegated_from, delegation = user, None, None
        step = ApprovalStep.objects.create(
            request=approval,
            step_order=order,
            approver=actual,
            parallel_mode=mode,
            delegated_from=delegated_from,
            delegation=delegation,
            created_by=actor,
        )
        created.append(step)

    # current_step을 가장 작은 order로
    if created:
        min_order = min(s.step_order for s in created)
        if approval.current_step != min_order:
            approval.current_step = min_order
            approval.save(update_fields=['current_step', 'updated_at'])

    return created


@transaction.atomic
def apply_delegation_to_existing_steps(approval, actor=None):
    """이미 입력된 Step에 대해 위임 치환 적용.

    PENDING 상태이고 delegated_from이 비어있는 Step에 대해서만 치환.
    제출 시점(apply_delegation_on_submit)의 내부 구현으로도 사용된다.
    """
    on_date = timezone.localdate()
    pending_steps = approval.steps.filter(
        status=ApprovalStep.Status.PENDING,
        delegated_from__isnull=True,
    ).select_related('approver')
    updated = 0
    for step in pending_steps:
        actual, delegated_from, delegation = resolve_delegate(
            step.approver, on_date,
        )
        if delegated_from is not None:
            step.approver = actual
            step.delegated_from = delegated_from
            step.delegation = delegation
            step.save(update_fields=[
                'approver', 'delegated_from', 'delegation', 'updated_at',
            ])
            updated += 1
    return updated


@transaction.atomic
def apply_delegation_on_submit(approval, actor=None):
    """제출 시점(SUBMITTED 전환) 위임 스냅샷.

    설계 문서 §4.2 규칙에 따라, 기안 제출 순간에 각 Step의 approver를
    활성 위임자로 치환하고 delegated_from/delegation을 기록한다.
    이후 위임 변동은 해당 기안에 영향을 주지 않는다.

    반환: 치환된 Step 개수.
    """
    return apply_delegation_to_existing_steps(approval, actor=actor)
