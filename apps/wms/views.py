from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from .models import BinLocation, PickOrder, PickOrderItem, PutAwayTask, WarehouseZone, WavePlan
from .forms import (
    BinLocationForm, PickOrderForm, PutAwayTaskForm, WarehouseZoneForm, WavePlanForm,
)


# === 창고 구역 ===

class ZoneListView(LoginRequiredMixin, ListView):
    model = WarehouseZone
    template_name = 'wms/zone_list.html'
    context_object_name = 'zones'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('warehouse').annotate(
            bin_count=Count('bins', filter=Q(bins__is_active=True)),
        )
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q))
        zone_type = self.request.GET.get('zone_type')
        if zone_type:
            qs = qs.filter(zone_type=zone_type)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['zone_type_choices'] = WarehouseZone.ZoneType.choices
        return ctx


class ZoneCreateView(ManagerRequiredMixin, CreateView):
    model = WarehouseZone
    form_class = WarehouseZoneForm
    template_name = 'wms/zone_form.html'
    success_url = reverse_lazy('wms:zone_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '창고구역이 등록되었습니다.')
        return super().form_valid(form)


class ZoneDetailView(LoginRequiredMixin, DetailView):
    model = WarehouseZone
    template_name = 'wms/zone_detail.html'
    context_object_name = 'zone'

    def get_queryset(self):
        return super().get_queryset().select_related('warehouse')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['bins'] = self.object.bins.filter(is_active=True).order_by('code')
        return ctx


class ZoneUpdateView(ManagerRequiredMixin, UpdateView):
    model = WarehouseZone
    form_class = WarehouseZoneForm
    template_name = 'wms/zone_form.html'
    success_url = reverse_lazy('wms:zone_list')

    def form_valid(self, form):
        messages.success(self.request, '창고구역이 수정되었습니다.')
        return super().form_valid(form)


# === 보관위치 ===

class BinListView(LoginRequiredMixin, ListView):
    model = BinLocation
    template_name = 'wms/bin_list.html'
    context_object_name = 'bins'
    paginate_by = 30

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('zone', 'zone__warehouse')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(code__icontains=q)
        zone = self.request.GET.get('zone')
        if zone:
            qs = qs.filter(zone_id=zone)
        return qs


class BinCreateView(ManagerRequiredMixin, CreateView):
    model = BinLocation
    form_class = BinLocationForm
    template_name = 'wms/bin_form.html'
    success_url = reverse_lazy('wms:bin_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '보관위치가 등록되었습니다.')
        return super().form_valid(form)


class BinUpdateView(ManagerRequiredMixin, UpdateView):
    model = BinLocation
    form_class = BinLocationForm
    template_name = 'wms/bin_form.html'
    success_url = reverse_lazy('wms:bin_list')

    def form_valid(self, form):
        messages.success(self.request, '보관위치가 수정되었습니다.')
        return super().form_valid(form)


# === 피킹 오더 ===

class PickOrderListView(LoginRequiredMixin, ListView):
    model = PickOrder
    template_name = 'wms/pickorder_list.html'
    context_object_name = 'pick_orders'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('order', 'assigned_to')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        priority = self.request.GET.get('priority')
        if priority:
            qs = qs.filter(priority=priority)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = PickOrder.Status.choices
        ctx['priority_choices'] = PickOrder.Priority.choices
        return ctx


class PickOrderCreateView(ManagerRequiredMixin, CreateView):
    model = PickOrder
    form_class = PickOrderForm
    template_name = 'wms/pickorder_form.html'
    success_url = reverse_lazy('wms:pickorder_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '피킹오더가 생성되었습니다.')
        return super().form_valid(form)


class PickOrderDetailView(LoginRequiredMixin, DetailView):
    model = PickOrder
    template_name = 'wms/pickorder_detail.html'
    context_object_name = 'pick_order'

    def get_queryset(self):
        return super().get_queryset().select_related('order', 'assigned_to')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.filter(
            is_active=True,
        ).select_related('product', 'bin_location')
        return ctx


class PickOrderUpdateView(ManagerRequiredMixin, UpdateView):
    model = PickOrder
    form_class = PickOrderForm
    template_name = 'wms/pickorder_form.html'

    def get_success_url(self):
        return self.object.get_absolute_url() if hasattr(self.object, 'get_absolute_url') else reverse_lazy('wms:pickorder_list')

    def form_valid(self, form):
        messages.success(self.request, '피킹오더가 수정되었습니다.')
        return super().form_valid(form)


# === 입고적치 ===

class PutAwayListView(LoginRequiredMixin, ListView):
    model = PutAwayTask
    template_name = 'wms/putaway_list.html'
    context_object_name = 'tasks'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('product', 'suggested_bin', 'actual_bin', 'assigned_to')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = PutAwayTask.Status.choices
        return ctx


class PutAwayCreateView(ManagerRequiredMixin, CreateView):
    model = PutAwayTask
    form_class = PutAwayTaskForm
    template_name = 'wms/putaway_form.html'
    success_url = reverse_lazy('wms:putaway_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '적치작업이 생성되었습니다.')
        return super().form_valid(form)


class PutAwayDetailView(LoginRequiredMixin, DetailView):
    model = PutAwayTask
    template_name = 'wms/putaway_detail.html'
    context_object_name = 'task'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'product', 'goods_receipt', 'suggested_bin', 'actual_bin', 'assigned_to',
        )


class PutAwayUpdateView(ManagerRequiredMixin, UpdateView):
    model = PutAwayTask
    form_class = PutAwayTaskForm
    template_name = 'wms/putaway_form.html'
    success_url = reverse_lazy('wms:putaway_list')

    def form_valid(self, form):
        messages.success(self.request, '적치작업이 수정되었습니다.')
        return super().form_valid(form)


# === 웨이브 계획 ===

class WavePlanListView(LoginRequiredMixin, ListView):
    model = WavePlan
    template_name = 'wms/waveplan_list.html'
    context_object_name = 'wave_plans'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).annotate(order_count=Count('pick_orders'))
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = WavePlan.Status.choices
        return ctx


class WavePlanCreateView(ManagerRequiredMixin, CreateView):
    model = WavePlan
    form_class = WavePlanForm
    template_name = 'wms/waveplan_form.html'
    success_url = reverse_lazy('wms:waveplan_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '웨이브계획이 생성되었습니다.')
        return super().form_valid(form)


class WavePlanDetailView(LoginRequiredMixin, DetailView):
    model = WavePlan
    template_name = 'wms/waveplan_detail.html'
    context_object_name = 'wave_plan'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pick_orders'] = self.object.pick_orders.filter(
            is_active=True,
        ).select_related('order', 'assigned_to')
        return ctx


# === 대시보드 ===

class WmsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'wms/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pending_picks'] = PickOrder.objects.filter(
            is_active=True, status=PickOrder.Status.PENDING,
        ).count()
        ctx['in_progress_picks'] = PickOrder.objects.filter(
            is_active=True, status=PickOrder.Status.PICKING,
        ).count()
        ctx['pending_putaways'] = PutAwayTask.objects.filter(
            is_active=True, status=PutAwayTask.Status.PENDING,
        ).count()
        ctx['total_bins'] = BinLocation.objects.filter(is_active=True).count()
        ctx['occupied_bins'] = BinLocation.objects.filter(
            is_active=True, is_occupied=True,
        ).count()
        return ctx
