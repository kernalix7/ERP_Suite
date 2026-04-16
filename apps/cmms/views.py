from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F, Q
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import ListView, CreateView, DetailView, UpdateView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from apps.module_manager.decorators import ModuleRequiredMixin
from .models import Equipment, EquipmentDowntime, MaintenanceSchedule, MaintenanceWorkOrder, SparePart
from .forms import (
    EquipmentForm, EquipmentDowntimeForm, MaintenanceScheduleForm,
    MaintenanceWorkOrderForm, SparePartForm, WorkOrderCompleteForm,
)


# === 설비 ===

class EquipmentListView(ModuleRequiredMixin, ListView):
    required_module = 'cmms'
    model = Equipment
    template_name = 'cmms/equipment_list.html'
    context_object_name = 'equipment_list'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('department')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Equipment.Status.choices
        return ctx


class EquipmentCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'cmms'
    model = Equipment
    form_class = EquipmentForm
    template_name = 'cmms/equipment_form.html'
    success_url = reverse_lazy('cmms:equipment_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '설비가 등록되었습니다.')
        return super().form_valid(form)


class EquipmentDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'cmms'
    model = Equipment
    template_name = 'cmms/equipment_detail.html'
    context_object_name = 'equipment'

    def get_queryset(self):
        return super().get_queryset().select_related('department')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['schedules'] = self.object.schedules.filter(
            is_active=True,
        ).select_related('assigned_to')
        ctx['recent_work_orders'] = self.object.work_orders.filter(
            is_active=True,
        ).order_by('-created_at')[:10]
        ctx['downtimes'] = self.object.downtimes.filter(
            is_active=True,
        ).order_by('-start_time')[:10]
        return ctx


class EquipmentUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'cmms'
    model = Equipment
    form_class = EquipmentForm
    template_name = 'cmms/equipment_form.html'
    success_url = reverse_lazy('cmms:equipment_list')

    def form_valid(self, form):
        messages.success(self.request, '설비 정보가 수정되었습니다.')
        return super().form_valid(form)


# === 보전 스케줄 ===

class ScheduleListView(ModuleRequiredMixin, ListView):
    required_module = 'cmms'
    model = MaintenanceSchedule
    template_name = 'cmms/schedule_list.html'
    context_object_name = 'schedules'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('equipment', 'assigned_to')
        mtype = self.request.GET.get('maintenance_type')
        if mtype:
            qs = qs.filter(maintenance_type=mtype)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['type_choices'] = MaintenanceSchedule.MaintenanceType.choices
        return ctx


class ScheduleCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'cmms'
    model = MaintenanceSchedule
    form_class = MaintenanceScheduleForm
    template_name = 'cmms/schedule_form.html'
    success_url = reverse_lazy('cmms:schedule_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '보전스케줄이 등록되었습니다.')
        return super().form_valid(form)


class ScheduleDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'cmms'
    model = MaintenanceSchedule
    template_name = 'cmms/schedule_detail.html'
    context_object_name = 'schedule'

    def get_queryset(self):
        return super().get_queryset().select_related('equipment', 'assigned_to')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['work_orders'] = self.object.work_orders.filter(
            is_active=True,
        ).order_by('-created_at')
        return ctx


class ScheduleUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'cmms'
    model = MaintenanceSchedule
    form_class = MaintenanceScheduleForm
    template_name = 'cmms/schedule_form.html'
    success_url = reverse_lazy('cmms:schedule_list')

    def form_valid(self, form):
        messages.success(self.request, '보전스케줄이 수정되었습니다.')
        return super().form_valid(form)


# === 작업지시 ===

class WorkOrderListView(ModuleRequiredMixin, ListView):
    required_module = 'cmms'
    model = MaintenanceWorkOrder
    template_name = 'cmms/workorder_list.html'
    context_object_name = 'work_orders'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('equipment', 'assigned_to')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        priority = self.request.GET.get('priority')
        if priority:
            qs = qs.filter(priority=priority)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = MaintenanceWorkOrder.Status.choices
        ctx['priority_choices'] = MaintenanceWorkOrder.Priority.choices
        return ctx


class WorkOrderCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'cmms'
    model = MaintenanceWorkOrder
    form_class = MaintenanceWorkOrderForm
    template_name = 'cmms/workorder_form.html'
    success_url = reverse_lazy('cmms:workorder_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '작업지시가 생성되었습니다.')
        return super().form_valid(form)


class WorkOrderDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'cmms'
    model = MaintenanceWorkOrder
    template_name = 'cmms/workorder_detail.html'
    context_object_name = 'work_order'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'equipment', 'schedule', 'assigned_to',
        )


class WorkOrderCompleteView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'cmms'
    model = MaintenanceWorkOrder
    form_class = WorkOrderCompleteForm
    template_name = 'cmms/workorder_complete.html'
    success_url = reverse_lazy('cmms:workorder_list')

    def form_valid(self, form):
        form.instance.status = MaintenanceWorkOrder.Status.COMPLETED
        form.instance.completed_at = timezone.now()
        messages.success(self.request, '작업이 완료 처리되었습니다.')
        return super().form_valid(form)


# === 예비부품 ===

class SparePartListView(ModuleRequiredMixin, ListView):
    required_module = 'cmms'
    model = SparePart
    template_name = 'cmms/sparepart_list.html'
    context_object_name = 'spare_parts'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        return qs


class SparePartCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'cmms'
    model = SparePart
    form_class = SparePartForm
    template_name = 'cmms/sparepart_form.html'
    success_url = reverse_lazy('cmms:sparepart_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '예비부품이 등록되었습니다.')
        return super().form_valid(form)


# === 비가동 기록 ===

class DowntimeListView(ModuleRequiredMixin, ListView):
    required_module = 'cmms'
    model = EquipmentDowntime
    template_name = 'cmms/downtime_list.html'
    context_object_name = 'downtimes'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('equipment', 'work_order')
        equipment = self.request.GET.get('equipment')
        if equipment:
            qs = qs.filter(equipment_id=equipment)
        return qs


class DowntimeCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'cmms'
    model = EquipmentDowntime
    form_class = EquipmentDowntimeForm
    template_name = 'cmms/downtime_form.html'
    success_url = reverse_lazy('cmms:downtime_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '비가동 기록이 등록되었습니다.')
        return super().form_valid(form)


# === 대시보드 ===

class CmmsDashboardView(ModuleRequiredMixin, TemplateView):
    required_module = 'cmms'
    template_name = 'cmms/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_equipment'] = Equipment.objects.filter(
            is_active=True, status=Equipment.Status.ACTIVE,
        ).count()
        ctx['maintenance_count'] = Equipment.objects.filter(
            is_active=True, status=Equipment.Status.MAINTENANCE,
        ).count()
        ctx['open_work_orders'] = MaintenanceWorkOrder.objects.filter(
            is_active=True, status__in=['OPEN', 'IN_PROGRESS'],
        ).count()
        ctx['overdue_schedules'] = MaintenanceSchedule.objects.filter(
            is_active=True,
            next_due__lt=timezone.now().date(),
        ).count()
        ctx['low_stock_parts'] = SparePart.objects.filter(
            is_active=True, current_stock__lt=F('min_stock'),
        ).count()
        return ctx
