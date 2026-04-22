from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from apps.core.mixins import ManagerRequiredMixin
from apps.approval.models import (
    ApprovalRequest, ApprovalStep, ApprovalAttachment,
    ApprovalLineTemplate, ApprovalDelegation,
)
from apps.approval.forms import (
    ApprovalRequestForm, ApprovalActionForm, ApprovalStepFormSet,
    ApprovalLineTemplateForm, ApprovalDelegationForm,
)


# === 결재/품의 ===
class ApprovalListView(ManagerRequiredMixin, ListView):
    model = ApprovalRequest
    template_name = 'approval/approval_list.html'
    context_object_name = 'approvals'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'requester', 'approver',
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        tab = self.request.GET.get('tab', 'all')
        if tab == 'my':
            qs = qs.filter(requester=self.request.user)
        elif tab == 'pending':
            qs = qs.filter(
                approver=self.request.user,
                status='SUBMITTED',
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pending_count'] = ApprovalRequest.objects.filter(
            approver=self.request.user, status='SUBMITTED'
        ).count()
        return ctx


def _save_attachments(request, approval):
    """첨부파일 다건 저장"""
    files = request.FILES.getlist('attachments')
    for f in files:
        ApprovalAttachment.objects.create(
            request=approval,
            file=f,
            original_name=f.name,
            created_by=request.user,
        )


class ApprovalCreateView(ManagerRequiredMixin, CreateView):
    model = ApprovalRequest
    form_class = ApprovalRequestForm
    template_name = 'approval/approval_form.html'
    success_url = reverse_lazy('approval:approval_list')

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['request_number'] = generate_document_number(
            ApprovalRequest, 'request_number', 'AR'
        )
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['step_formset'] = ApprovalStepFormSet(
                self.request.POST,
            )
        else:
            ctx['step_formset'] = ApprovalStepFormSet()
        ctx['line_templates'] = ApprovalLineTemplate.objects.filter(
            is_active=True,
        ).order_by('-priority', '-is_default', 'name')
        return ctx

    def form_valid(self, form):
        from django.db import transaction as _tx
        from apps.approval.services import (
            apply_delegation_to_existing_steps,
            build_steps_from_template,
            find_matching_template,
        )

        ctx = self.get_context_data()
        step_formset = ctx['step_formset']
        form.instance.requester = self.request.user
        form.instance.created_by = self.request.user
        if not step_formset.is_valid():
            return self.form_invalid(form)

        with _tx.atomic():
            self.object = form.save()
            step_formset.instance = self.object
            saved_steps = step_formset.save()
            _save_attachments(self.request, self.object)

            line_template_id = self.request.POST.get('line_template_id')
            use_auto = self.request.POST.get('use_auto_template') == 'on'
            applied_template = None

            if line_template_id:
                try:
                    tpl = ApprovalLineTemplate.objects.get(
                        pk=line_template_id, is_active=True,
                    )
                    applied_template = tpl
                except ApprovalLineTemplate.DoesNotExist:
                    applied_template = None

            if applied_template is None and use_auto:
                applied_template = find_matching_template(
                    category=self.object.category,
                    amount=self.object.amount,
                    department_id=(
                        self.object.department_id
                        if self.object.department_id else None
                    ),
                    urgency=self.object.urgency,
                )

            if applied_template is not None:
                build_steps_from_template(
                    self.object, applied_template, actor=self.request.user,
                )
            else:
                # 수동 입력된 Step에 위임 치환 적용
                apply_delegation_to_existing_steps(
                    self.object, actor=self.request.user,
                )

        return redirect(self.get_success_url())


class ApprovalUpdateView(ManagerRequiredMixin, UpdateView):
    model = ApprovalRequest
    form_class = ApprovalRequestForm
    template_name = 'approval/approval_form.html'
    slug_field = 'request_number'
    slug_url_kwarg = 'slug'
    success_url = reverse_lazy('approval:approval_list')

    def get_queryset(self):
        return super().get_queryset().filter(
            requester=self.request.user, status='DRAFT',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['step_formset'] = ApprovalStepFormSet(
                self.request.POST, instance=self.object,
            )
        else:
            ctx['step_formset'] = ApprovalStepFormSet(
                instance=self.object,
            )
        ctx['existing_attachments'] = (
            self.object.attachments.all()
        )
        return ctx

    def form_valid(self, form):
        from django.db import transaction as _tx
        from apps.approval.services import (
            apply_delegation_to_existing_steps,
            build_steps_from_template,
            find_matching_template,
        )
        ctx = self.get_context_data()
        step_formset = ctx['step_formset']
        if not step_formset.is_valid():
            return self.form_invalid(form)

        with _tx.atomic():
            self.object = form.save()
            step_formset.instance = self.object
            step_formset.save()
            del_ids = self.request.POST.getlist('delete_attachments')
            if del_ids:
                self.object.attachments.filter(pk__in=del_ids).delete()
            _save_attachments(self.request, self.object)

            line_template_id = self.request.POST.get('line_template_id')
            use_auto = self.request.POST.get('use_auto_template') == 'on'
            applied_template = None
            if line_template_id:
                try:
                    applied_template = ApprovalLineTemplate.objects.get(
                        pk=line_template_id, is_active=True,
                    )
                except ApprovalLineTemplate.DoesNotExist:
                    applied_template = None
            if applied_template is None and use_auto:
                applied_template = find_matching_template(
                    category=self.object.category,
                    amount=self.object.amount,
                    department_id=self.object.department_id,
                    urgency=self.object.urgency,
                )
            if applied_template is not None:
                build_steps_from_template(
                    self.object, applied_template, actor=self.request.user,
                )
            else:
                apply_delegation_to_existing_steps(
                    self.object, actor=self.request.user,
                )
        return redirect(self.get_success_url())


class ApprovalDetailView(ManagerRequiredMixin, DetailView):
    model = ApprovalRequest
    template_name = 'approval/approval_detail.html'
    slug_field = 'request_number'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'requester', 'approver', 'cooperator',
            'department',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action_form'] = ApprovalActionForm()
        all_steps = list(
            self.object.steps
            .select_related('approver', 'delegated_from')
            .order_by('step_order', 'pk')
        )
        ctx['steps'] = all_steps
        # 같은 step_order끼리 그룹핑 (템플릿 렌더링용)
        grouped = []
        for step in all_steps:
            if grouped and grouped[-1]['order'] == step.step_order:
                grouped[-1]['items'].append(step)
            else:
                grouped.append({'order': step.step_order, 'items': [step]})
        ctx['steps_grouped'] = grouped
        ctx['attachments'] = self.object.attachments.all()
        # 현재 유저가 승인 가능한 Step (현재 order 내 본인 PENDING Step)
        my_step_obj = self.object.steps.filter(
            step_order=self.object.current_step,
            status='PENDING',
            approver=self.request.user,
        ).first()
        # 대표 표시용 current step (첫 번째 PENDING)
        current_step_obj = self.object.steps.filter(
            step_order=self.object.current_step,
            status='PENDING',
        ).order_by('pk').first()
        ctx['current_step_obj'] = current_step_obj
        ctx['my_step_obj'] = my_step_obj
        ctx['can_approve_step'] = (
            my_step_obj is not None
            and self.object.status == 'SUBMITTED'
        )
        ctx['can_approve'] = (
            not self.object.steps.exists()
            and self.object.approver == self.request.user
            and self.object.status == 'SUBMITTED'
        )
        ctx['can_submit'] = (
            self.object.requester == self.request.user
            and self.object.status == 'DRAFT'
        )
        return ctx


class ApprovalSubmitView(ManagerRequiredMixin, View):
    def post(self, request, slug):
        from django.db import transaction as _tx
        from django.utils import timezone
        obj = get_object_or_404(
            ApprovalRequest, request_number=slug, requester=request.user,
        )
        if obj.status != 'DRAFT':
            return HttpResponseRedirect(
                reverse_lazy('approval:approval_detail', args=[slug])
            )
        from apps.approval.services import apply_delegation_on_submit
        with _tx.atomic():
            # 위임 스냅샷: 제출 시점에 각 Step의 approver를 활성 위임자로 치환
            apply_delegation_on_submit(obj, actor=request.user)
            obj.status = 'SUBMITTED'
            obj.submitted_at = timezone.now()
            # 최초 Step이 있으면 current_step을 맞춘다
            first_step = obj.steps.order_by('step_order', 'pk').first()
            if first_step:
                obj.current_step = first_step.step_order
                obj.save(update_fields=[
                    'status', 'submitted_at', 'current_step', 'updated_at',
                ])
            else:
                obj.save(update_fields=[
                    'status', 'submitted_at', 'updated_at',
                ])
        # Notification: 첫 단계의 모든 결재자(병렬 포함)에게 알림
        if first_step:
            from apps.core.notification import create_notification
            first_order_approvers = list(
                obj.steps.filter(
                    step_order=first_step.step_order,
                    status=ApprovalStep.Status.PENDING,
                ).select_related('approver').values_list('approver', flat=True)
            )
            if first_order_approvers:
                from apps.accounts.models import User
                users = User.objects.filter(pk__in=first_order_approvers)
                create_notification(
                    list(users),
                    '결재 요청',
                    f'{request.user.name or request.user.username}님이 '
                    f'[{obj.title}] 결재를 요청했습니다.',
                    noti_type='SYSTEM',
                    link=f'/approval/{obj.request_number}/',
                )
        return HttpResponseRedirect(
            reverse_lazy('approval:approval_detail', args=[slug])
        )


class ApprovalActionView(ManagerRequiredMixin, View):
    def post(self, request, slug):
        from django.utils import timezone
        obj = get_object_or_404(
            ApprovalRequest, request_number=slug, approver=request.user,
        )
        if obj.status != 'SUBMITTED':
            return HttpResponseRedirect(
                reverse_lazy(
                    'approval:approval_detail', args=[slug],
                )
            )
        action = request.POST.get('action')
        if action == 'approve':
            obj.status = 'APPROVED'
            obj.approved_at = timezone.now()
        elif action == 'reject':
            obj.status = 'REJECTED'
            obj.reject_reason = request.POST.get(
                'reject_reason', '',
            )
        obj.save()
        return HttpResponseRedirect(
            reverse_lazy('approval:approval_detail', args=[slug])
        )


# === 다단계 결재 처리 ===
class ApprovalStepActionView(ManagerRequiredMixin, View):
    """결재 단계별 승인/반려 처리"""
    def post(self, request, slug, step_pk):
        from django.db import transaction
        from django.utils import timezone

        approval = get_object_or_404(ApprovalRequest, request_number=slug)

        with transaction.atomic():
            step = get_object_or_404(
                ApprovalStep.objects.select_for_update(),
                pk=step_pk,
                request=approval,
                approver=request.user,
            )

            if (approval.status != 'SUBMITTED'
                    or step.status != ApprovalStep.Status.PENDING):
                return HttpResponseRedirect(
                    reverse_lazy(
                        'approval:approval_detail', args=[slug],
                    )
                )

            # 현재 활성 단계에서만 처리 허용 (병렬 포함)
            if step.step_order != approval.current_step:
                return HttpResponseRedirect(
                    reverse_lazy(
                        'approval:approval_detail', args=[slug],
                    )
                )

            action = request.POST.get('action')
            comment = request.POST.get('comment', '')

            step.comment = comment
            step.acted_at = timezone.now()

            if action == 'approve':
                step.status = 'APPROVED'
                step.save()
            elif action == 'reject':
                step.status = 'REJECTED'
                step.save()

        # Notification: 결재 완료/반려 시 기안자에게 알림
        from apps.core.notification import create_notification
        if action == 'approve':
            # 시그널이 최종 승인 처리했는지 확인
            approval.refresh_from_db()
            if approval.status == 'APPROVED':
                create_notification(
                    [approval.requester],
                    '결재 최종 승인',
                    f'결재 [{approval.title}]이(가) 최종 승인되었습니다.',
                    noti_type='SYSTEM',
                    link=f'/approval/{approval.request_number}/',
                )
        elif action == 'reject':
            create_notification(
                [approval.requester],
                '결재 반려',
                f'결재 [{approval.title}]이(가) 반려되었습니다. 사유: {comment}',
                noti_type='SYSTEM',
                link=f'/approval/{approval.request_number}/',
            )

        return HttpResponseRedirect(
            reverse_lazy('approval:approval_detail', args=[slug])
        )


# === 결재선 템플릿 ===
class ApprovalLineTemplateListView(ManagerRequiredMixin, ListView):
    model = ApprovalLineTemplate
    template_name = 'approval/line_template_list.html'
    context_object_name = 'templates'

    def get_queryset(self):
        return ApprovalLineTemplate.objects.filter(is_active=True).order_by('-is_default', 'name')


class ApprovalLineTemplateCreateView(ManagerRequiredMixin, CreateView):
    model = ApprovalLineTemplate
    form_class = ApprovalLineTemplateForm
    template_name = 'approval/line_template_form.html'
    success_url = reverse_lazy('approval:line_template_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


# === 결재 위임 ===
class ApprovalDelegationListView(ManagerRequiredMixin, ListView):
    model = ApprovalDelegation
    template_name = 'approval/delegation_list.html'
    context_object_name = 'delegations'

    def get_queryset(self):
        return ApprovalDelegation.objects.filter(
            is_active=True,
            delegator=self.request.user,
        ).select_related('delegate').order_by('-start_date')


class ApprovalDelegationCreateView(ManagerRequiredMixin, CreateView):
    model = ApprovalDelegation
    form_class = ApprovalDelegationForm
    template_name = 'approval/delegation_form.html'
    success_url = reverse_lazy('approval:delegation_list')

    def form_valid(self, form):
        form.instance.delegator = self.request.user
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ApprovalDelegationDeleteView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        delegation = get_object_or_404(
            ApprovalDelegation, pk=pk, delegator=request.user, is_active=True,
        )
        delegation.is_active = False
        delegation.save(update_fields=['is_active', 'updated_at'])
        return HttpResponseRedirect(reverse_lazy('approval:delegation_list'))
