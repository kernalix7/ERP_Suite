from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView

from apps.core.import_views import BaseImportView
from apps.core.mixins import ManagerRequiredMixin

from .models import ProductRegistration
from .forms import ProductRegistrationForm


class RegistrationListView(LoginRequiredMixin, ListView):
    model = ProductRegistration
    template_name = 'warranty/registration_list.html'
    context_object_name = 'registrations'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(serial_number__icontains=q) | Q(customer_name__icontains=q)
            )
        return qs


class RegistrationCreateView(LoginRequiredMixin, CreateView):
    model = ProductRegistration
    form_class = ProductRegistrationForm
    template_name = 'warranty/registration_form.html'
    success_url = reverse_lazy('warranty:registration_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.sales.models import Customer
        ctx['customer_data_json'] = {
            str(c.pk): {'name': c.name, 'phone': c.phone or '', 'email': c.email or ''}
            for c in Customer.objects.filter(is_active=True)
        }
        return ctx

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class RegistrationDetailView(LoginRequiredMixin, DetailView):
    model = ProductRegistration
    template_name = 'warranty/registration_detail.html'


class RegistrationUpdateView(LoginRequiredMixin, UpdateView):
    model = ProductRegistration
    form_class = ProductRegistrationForm
    template_name = 'warranty/registration_form.html'
    success_url = reverse_lazy('warranty:registration_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.sales.models import Customer
        ctx['customer_data_json'] = {
            str(c.pk): {'name': c.name, 'phone': c.phone or '', 'email': c.email or ''}
            for c in Customer.objects.filter(is_active=True)
        }
        return ctx


class SerialCheckView(LoginRequiredMixin, View):
    """시리얼번호 조회 API"""
    def get(self, request):
        serial = request.GET.get('serial', '')
        try:
            reg = ProductRegistration.objects.get(serial_number=serial)
            return JsonResponse({
                'found': True,
                'serial_number': reg.serial_number,
                'product': str(reg.product),
                'customer_name': reg.customer_name,
                'warranty_valid': reg.is_warranty_valid,
                'warranty_end': str(reg.warranty_end),
                'is_verified': reg.is_verified,
            })
        except ProductRegistration.DoesNotExist:
            return JsonResponse({'found': False})


class WarrantyVerifyView(LoginRequiredMixin, TemplateView):
    """보증 확인 (시리얼번호 또는 QR 스캔)"""
    template_name = 'warranty/warranty_verify.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        serial_number = self.request.GET.get('serial_number', '').strip()
        context['serial_number'] = serial_number

        if serial_number:
            try:
                reg = ProductRegistration.objects.select_related('product').get(
                    serial_number=serial_number
                )
                context['registration'] = reg
                context['found'] = True
            except ProductRegistration.DoesNotExist:
                context['found'] = False

        return context


# === 일괄 가져오기 ===

class RegistrationImportView(BaseImportView):
    resource_class = None
    page_title = '제품등록(보증) 일괄 가져오기'
    cancel_url = reverse_lazy('warranty:registration_list')
    sample_url = reverse_lazy('warranty:registration_import_sample')
    field_hints = [
        '시리얼번호(serial_number)가 동일하면 기존 등록이 수정됩니다.',
        'product_code: 제품코드',
    ]

    def get_resource(self):
        from .resources import ProductRegistrationResource
        return ProductRegistrationResource()


class RegistrationImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('serial_number', 18), ('product_code', 15),
            ('customer_name', 15), ('phone', 15),
            ('purchase_date', 12), ('purchase_channel', 15),
            ('warranty_start', 12), ('warranty_end', 12),
        ]
        rows = [
            ['SN-2026-001', 'PRD-001', '홍길동', '010-1234-5678',
             '2026-03-01', '공식홈페이지', '2026-03-01', '2027-03-01'],
        ]
        return export_to_excel(
            '제품등록_가져오기_양식', headers, rows,
            filename='제품등록_가져오기_양식.xlsx',
            required_columns=[0, 1, 2, 3, 4, 6, 7],
        )
