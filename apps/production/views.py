from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from .models import BOM, BOMItem, ProductionPlan, WorkOrder, ProductionRecord
from .forms import BOMForm, BOMItemFormSet, ProductionPlanForm, WorkOrderForm, ProductionRecordForm


class BOMListView(LoginRequiredMixin, ListView):
    model = BOM
    template_name = 'production/bom_list.html'
    context_object_name = 'boms'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related('product')


class BOMCreateView(LoginRequiredMixin, CreateView):
    model = BOM
    form_class = BOMForm
    template_name = 'production/bom_form.html'
    success_url = reverse_lazy('production:bom_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = BOMItemFormSet(self.request.POST)
        else:
            ctx['formset'] = BOMItemFormSet()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user
            self.object.save()
            formset.instance = self.object
            formset.save()
            return redirect(self.get_success_url())
        return self.form_invalid(form)


class BOMDetailView(LoginRequiredMixin, DetailView):
    model = BOM
    template_name = 'production/bom_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('product')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.select_related(
            'material',
        ).all()
        return ctx


class BOMUpdateView(LoginRequiredMixin, UpdateView):
    model = BOM
    form_class = BOMForm
    template_name = 'production/bom_form.html'
    success_url = reverse_lazy('production:bom_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = BOMItemFormSet(self.request.POST, instance=self.object)
        else:
            ctx['formset'] = BOMItemFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            return super().form_valid(form)
        return self.form_invalid(form)


class ProductionPlanListView(LoginRequiredMixin, ListView):
    model = ProductionPlan
    template_name = 'production/plan_list.html'
    context_object_name = 'plans'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'product', 'bom',
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class ProductionPlanCreateView(LoginRequiredMixin, CreateView):
    model = ProductionPlan
    form_class = ProductionPlanForm
    template_name = 'production/plan_form.html'
    success_url = reverse_lazy('production:plan_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ProductionPlanDetailView(LoginRequiredMixin, DetailView):
    model = ProductionPlan
    template_name = 'production/plan_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'product', 'bom',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['work_orders'] = (
            self.object.work_orders
            .select_related('assigned_to')
            .all()
        )
        return ctx


class ProductionPlanUpdateView(LoginRequiredMixin, UpdateView):
    model = ProductionPlan
    form_class = ProductionPlanForm
    template_name = 'production/plan_form.html'
    success_url = reverse_lazy('production:plan_list')


class WorkOrderListView(LoginRequiredMixin, ListView):
    model = WorkOrder
    template_name = 'production/workorder_list.html'
    context_object_name = 'work_orders'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'production_plan', 'production_plan__product',
            'assigned_to',
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class WorkOrderCreateView(LoginRequiredMixin, CreateView):
    model = WorkOrder
    form_class = WorkOrderForm
    template_name = 'production/workorder_form.html'
    success_url = reverse_lazy('production:workorder_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class WorkOrderDetailView(LoginRequiredMixin, DetailView):
    model = WorkOrder
    template_name = 'production/workorder_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'production_plan', 'production_plan__product',
            'assigned_to',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['records'] = (
            self.object.records
            .select_related('worker')
            .all()
        )
        return ctx


class WorkOrderUpdateView(LoginRequiredMixin, UpdateView):
    model = WorkOrder
    form_class = WorkOrderForm
    template_name = 'production/workorder_form.html'
    success_url = reverse_lazy('production:workorder_list')


class ProductionRecordListView(LoginRequiredMixin, ListView):
    model = ProductionRecord
    template_name = 'production/record_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related(
            'work_order',
            'work_order__production_plan',
            'work_order__production_plan__product',
            'worker',
        )


class ProductionRecordCreateView(LoginRequiredMixin, CreateView):
    model = ProductionRecord
    form_class = ProductionRecordForm
    template_name = 'production/record_form.html'
    success_url = reverse_lazy('production:record_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
