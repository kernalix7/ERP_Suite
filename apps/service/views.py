from datetime import date

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView

from apps.core.import_views import BaseImportView
from apps.core.mixins import ManagerRequiredMixin

from .models import ServiceRequest, RepairRecord
from .forms import ServiceRequestForm, RepairRecordForm


class ServiceRequestListView(LoginRequiredMixin, ListView):
    model = ServiceRequest
    template_name = 'service/request_list.html'
    context_object_name = 'requests'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('product', 'customer')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class ServiceRequestCreateView(ManagerRequiredMixin, CreateView):
    model = ServiceRequest
    form_class = ServiceRequestForm
    template_name = 'service/request_form.html'
    success_url = reverse_lazy('service:request_list')

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['request_number'] = generate_document_number(ServiceRequest, 'request_number', 'AS')
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        # 보증기간 자동 확인 (해당 제품의 구매내역에서 확인)
        customer = form.instance.customer
        product = form.instance.product
        if customer and product:
            has_valid_warranty = customer.purchases.filter(
                is_active=True,
                product=product,
                warranty_end__gte=date.today(),
            ).exists()
            if has_valid_warranty:
                form.instance.is_warranty = True
                if not form.instance.request_type or form.instance.request_type == 'PAID':
                    form.instance.request_type = 'WARRANTY'
        return super().form_valid(form)


class ServiceRequestDetailView(LoginRequiredMixin, DetailView):
    model = ServiceRequest
    template_name = 'service/request_detail.html'
    slug_field = 'request_number'
    slug_url_kwarg = 'slug'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['repairs'] = self.object.repairs.all()
        ctx['total_repair_cost'] = self.object.repairs.aggregate(total=Sum('cost'))['total'] or 0
        return ctx


class ServiceRequestUpdateView(ManagerRequiredMixin, UpdateView):
    model = ServiceRequest
    form_class = ServiceRequestForm
    template_name = 'service/request_form.html'
    success_url = reverse_lazy('service:request_list')
    slug_field = 'request_number'
    slug_url_kwarg = 'slug'


class RepairRecordCreateView(ManagerRequiredMixin, CreateView):
    model = RepairRecord
    form_class = RepairRecordForm
    template_name = 'service/repair_form.html'
    success_url = reverse_lazy('service:request_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


# === 일괄 가져오기 ===

class ServiceRequestImportView(BaseImportView):
    resource_class = None
    page_title = 'AS 접수 일괄 가져오기'
    cancel_url = reverse_lazy('service:request_list')
    sample_url = reverse_lazy('service:request_import_sample')
    export_filename = 'AS요청_데이터'
    field_hints = [
        'AS번호(request_number)가 동일하면 기존 접수가 수정됩니다.',
        'customer_name: 고객명, product_code: 제품코드',
        'request_type: WARRANTY(보증), PAID(유상), RECALL(리콜)',
        'status: RECEIVED(접수), IN_PROGRESS(처리중), '
        'COMPLETED(완료), CANCELLED(취소)',
    ]

    def get_resource(self):
        from .resources import ServiceRequestResource
        return ServiceRequestResource()


class ServiceRequestImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('request_number', 18), ('customer_name', 15),
            ('product_code', 15), ('serial_number', 18),
            ('request_type', 12), ('status', 12),
            ('symptom', 30), ('received_date', 12),
        ]
        rows = [
            ['AS-2026-001', '홍길동', 'PRD-001', 'SN123456',
             'WARRANTY', 'RECEIVED', '전원 불량', '2026-03-01'],
        ]
        return export_to_excel(
            'AS접수_가져오기_양식', headers, rows,
            filename='AS접수_가져오기_양식.xlsx',
            required_columns=[0, 1, 2, 6, 7],
        )
