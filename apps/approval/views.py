from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from apps.core.mixins import ManagerRequiredMixin
from apps.approval.models import (
    ApprovalRequest, ApprovalStep, ApprovalAttachment,
)
from apps.approval.forms import (
    ApprovalRequestForm, ApprovalActionForm, ApprovalStepFormSet,
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
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        step_formset = ctx['step_formset']
        form.instance.requester = self.request.user
        form.instance.created_by = self.request.user
        if step_formset.is_valid():
            self.object = form.save()
            step_formset.instance = self.object
            step_formset.save()
            _save_attachments(self.request, self.object)
            return redirect(self.get_success_url())
        return self.form_invalid(form)


class ApprovalUpdateView(ManagerRequiredMixin, UpdateView):
    model = ApprovalRequest
    form_class = ApprovalRequestForm
    template_name = 'approval/approval_form.html'
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
        ctx = self.get_context_data()
        step_formset = ctx['step_formset']
        if step_formset.is_valid():
            self.object = form.save()
            step_formset.instance = self.object
            step_formset.save()
            # 삭제 요청된 첨부파일 처리
            del_ids = self.request.POST.getlist(
                'delete_attachments'
            )
            if del_ids:
                self.object.attachments.filter(
                    pk__in=del_ids,
                ).delete()
            _save_attachments(self.request, self.object)
            return redirect(self.get_success_url())
        return self.form_invalid(form)


class ApprovalDetailView(ManagerRequiredMixin, DetailView):
    model = ApprovalRequest
    template_name = 'approval/approval_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'requester', 'approver', 'cooperator',
            'department',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action_form'] = ApprovalActionForm()
        ctx['steps'] = (
            self.object.steps
            .select_related('approver')
            .order_by('step_order')
        )
        ctx['attachments'] = self.object.attachments.all()
        current_step_obj = self.object.steps.filter(
            step_order=self.object.current_step,
            status='PENDING',
        ).first()
        ctx['current_step_obj'] = current_step_obj
        ctx['can_approve_step'] = (
            current_step_obj is not None
            and current_step_obj.approver == self.request.user
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
    def post(self, request, pk):
        from django.utils import timezone
        obj = get_object_or_404(
            ApprovalRequest, pk=pk, requester=request.user,
        )
        if obj.status == 'DRAFT':
            obj.status = 'SUBMITTED'
            obj.submitted_at = timezone.now()
            obj.save(update_fields=[
                'status', 'submitted_at', 'updated_at',
            ])
        return HttpResponseRedirect(
            reverse_lazy('approval:approval_detail', args=[pk])
        )


class ApprovalActionView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        from django.utils import timezone
        obj = get_object_or_404(
            ApprovalRequest, pk=pk, approver=request.user,
        )
        if obj.status != 'SUBMITTED':
            return HttpResponseRedirect(
                reverse_lazy(
                    'approval:approval_detail', args=[pk],
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
            reverse_lazy('approval:approval_detail', args=[pk])
        )


# === 다단계 결재 처리 ===
class ApprovalStepActionView(ManagerRequiredMixin, View):
    """결재 단계별 승인/반려 처리"""
    def post(self, request, pk, step_pk):
        from django.utils import timezone

        approval = get_object_or_404(ApprovalRequest, pk=pk)
        step = get_object_or_404(
            ApprovalStep,
            pk=step_pk,
            request=approval,
            approver=request.user,
        )

        if (approval.status != 'SUBMITTED'
                or step.status != 'PENDING'):
            return HttpResponseRedirect(
                reverse_lazy(
                    'approval:approval_detail', args=[pk],
                )
            )

        if step.step_order != approval.current_step:
            return HttpResponseRedirect(
                reverse_lazy(
                    'approval:approval_detail', args=[pk],
                )
            )

        action = request.POST.get('action')
        comment = request.POST.get('comment', '')

        step.comment = comment
        step.acted_at = timezone.now()

        if action == 'approve':
            step.status = 'APPROVED'
            step.save()
            next_step = (
                approval.steps
                .filter(step_order__gt=step.step_order)
                .order_by('step_order')
                .first()
            )
            if next_step:
                approval.current_step = next_step.step_order
                approval.save(update_fields=[
                    'current_step', 'updated_at',
                ])
            else:
                approval.status = 'APPROVED'
                approval.approved_at = timezone.now()
                approval.save(update_fields=[
                    'status', 'approved_at', 'updated_at',
                ])
        elif action == 'reject':
            step.status = 'REJECTED'
            step.save()
            approval.status = 'REJECTED'
            approval.reject_reason = comment
            approval.save(update_fields=[
                'status', 'reject_reason', 'updated_at',
            ])

        return HttpResponseRedirect(
            reverse_lazy('approval:approval_detail', args=[pk])
        )
