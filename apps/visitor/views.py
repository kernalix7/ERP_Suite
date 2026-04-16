from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from apps.core.mixins import ManagerRequiredMixin
from apps.module_manager.decorators import ModuleRequiredMixin
from .models import Visitor, VisitorPurpose, VisitRequest, VisitLog, VisitorNDA
from .forms import VisitorForm, VisitorPurposeForm, VisitRequestForm, VisitCheckInForm, VisitCheckOutForm


class VisitRequestListView(ModuleRequiredMixin, ListView):
    required_module = 'visitor'
    model = VisitRequest
    template_name = 'visitor/visit_request_list.html'
    context_object_name = 'visit_requests'
    paginate_by = 20

    def get_queryset(self):
        qs = VisitRequest.objects.filter(is_active=True).select_related(
            'visitor', 'host', 'purpose', 'department',
        ).order_by('-scheduled_at')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(visitor__name__icontains=q) |
                Q(visitor__company__icontains=q) |
                Q(visit_number__icontains=q)
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class VisitRequestDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'visitor'
    model = VisitRequest
    template_name = 'visitor/visit_request_detail.html'
    context_object_name = 'visit_request'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['visit_log'] = getattr(self.object, 'visit_log', None)
        return ctx


class VisitRequestCreateView(ModuleRequiredMixin, CreateView):
    required_module = 'visitor'
    model = VisitRequest
    form_class = VisitRequestForm
    template_name = 'visitor/visit_request_form.html'
    success_url = reverse_lazy('visitor:visit_request_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '방문 예약이 신청되었습니다.')
        return super().form_valid(form)


class VisitRequestApproveView(ModuleRequiredMixin, ManagerRequiredMixin, DetailView):
    required_module = 'visitor'
    model = VisitRequest

    def post(self, request, *args, **kwargs):
        visit_req = self.get_object()
        action = request.POST.get('action')
        if action == 'approve':
            visit_req.status = VisitRequest.Status.APPROVED
            visit_req.approved_by = request.user
            visit_req.approved_at = timezone.now()
            visit_req.save()
            messages.success(request, '방문 예약이 승인되었습니다.')
        elif action == 'reject':
            visit_req.status = VisitRequest.Status.REJECTED
            visit_req.rejection_reason = request.POST.get('rejection_reason', '')
            visit_req.save()
            messages.warning(request, '방문 예약이 거부되었습니다.')
        return redirect('visitor:visit_request_detail', pk=visit_req.pk)


class VisitCheckInView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    """방문자 체크인"""
    required_module = 'visitor'
    model = VisitLog
    form_class = VisitCheckInForm
    template_name = 'visitor/check_in.html'
    success_url = reverse_lazy('visitor:visit_log_list')

    def form_valid(self, form):
        form.instance.receptionist = self.request.user
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        # 예약 상태 업데이트
        if form.instance.visit_request:
            VisitRequest.objects.filter(pk=form.instance.visit_request.pk).update(
                status=VisitRequest.Status.VISITED,
            )
        messages.success(self.request, '체크인이 완료되었습니다.')
        return response


class VisitCheckOutView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    """방문자 체크아웃"""
    required_module = 'visitor'
    model = VisitLog
    form_class = VisitCheckOutForm
    template_name = 'visitor/check_out.html'
    success_url = reverse_lazy('visitor:visit_log_list')

    def form_valid(self, form):
        form.instance.check_out_at = timezone.now()
        messages.success(self.request, '체크아웃이 완료되었습니다.')
        return super().form_valid(form)


class VisitLogListView(ModuleRequiredMixin, ManagerRequiredMixin, ListView):
    required_module = 'visitor'
    model = VisitLog
    template_name = 'visitor/visit_log_list.html'
    context_object_name = 'visit_logs'
    paginate_by = 30

    def get_queryset(self):
        qs = VisitLog.objects.filter(is_active=True).select_related(
            'visitor', 'receptionist',
        ).order_by('-check_in_at')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(visitor__name__icontains=q) | Q(badge_number__icontains=q))
        date = self.request.GET.get('date')
        if date:
            qs = qs.filter(check_in_at__date=date)
        return qs


class VisitorListView(ModuleRequiredMixin, ManagerRequiredMixin, ListView):
    required_module = 'visitor'
    model = Visitor
    template_name = 'visitor/visitor_list.html'
    context_object_name = 'visitors'
    paginate_by = 20

    def get_queryset(self):
        qs = Visitor.objects.filter(is_active=True).order_by('name')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(company__icontains=q))
        return qs


class VisitorCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'visitor'
    model = Visitor
    form_class = VisitorForm
    template_name = 'visitor/visitor_form.html'
    success_url = reverse_lazy('visitor:visitor_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '방문자가 등록되었습니다.')
        return super().form_valid(form)


class VisitorPurposeListView(ModuleRequiredMixin, ManagerRequiredMixin, ListView):
    required_module = 'visitor'
    model = VisitorPurpose
    template_name = 'visitor/purpose_list.html'
    context_object_name = 'purposes'
    paginate_by = 20

    def get_queryset(self):
        return VisitorPurpose.objects.filter(is_active=True).order_by('code')


class VisitorPurposeCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'visitor'
    model = VisitorPurpose
    form_class = VisitorPurposeForm
    template_name = 'visitor/purpose_form.html'
    success_url = reverse_lazy('visitor:purpose_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '방문목적이 등록되었습니다.')
        return super().form_valid(form)
