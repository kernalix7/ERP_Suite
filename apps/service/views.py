from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from .models import ServiceRequest, RepairRecord
from .forms import ServiceRequestForm, RepairRecordForm


class ServiceRequestListView(LoginRequiredMixin, ListView):
    model = ServiceRequest
    template_name = 'service/request_list.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class ServiceRequestCreateView(LoginRequiredMixin, CreateView):
    model = ServiceRequest
    form_class = ServiceRequestForm
    template_name = 'service/request_form.html'
    success_url = reverse_lazy('service:request_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        # 보증기간 자동 확인
        customer = form.instance.customer
        if customer and customer.is_warranty_valid:
            form.instance.is_warranty = True
            if not form.instance.request_type or form.instance.request_type == 'PAID':
                form.instance.request_type = 'WARRANTY'
        return super().form_valid(form)


class ServiceRequestDetailView(LoginRequiredMixin, DetailView):
    model = ServiceRequest
    template_name = 'service/request_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['repairs'] = self.object.repairs.all()
        ctx['total_repair_cost'] = self.object.repairs.aggregate(total=Sum('cost'))['total'] or 0
        return ctx


class ServiceRequestUpdateView(LoginRequiredMixin, UpdateView):
    model = ServiceRequest
    form_class = ServiceRequestForm
    template_name = 'service/request_form.html'
    success_url = reverse_lazy('service:request_list')


class RepairRecordCreateView(LoginRequiredMixin, CreateView):
    model = RepairRecord
    form_class = RepairRecordForm
    template_name = 'service/repair_form.html'
    success_url = reverse_lazy('service:request_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
