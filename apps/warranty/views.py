from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView

from .models import ProductRegistration
from .forms import ProductRegistrationForm


class RegistrationListView(LoginRequiredMixin, ListView):
    model = ProductRegistration
    template_name = 'warranty/registration_list.html'
    context_object_name = 'registrations'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(serial_number__icontains=q) | qs.filter(customer_name__icontains=q)
        return qs


class RegistrationCreateView(LoginRequiredMixin, CreateView):
    model = ProductRegistration
    form_class = ProductRegistrationForm
    template_name = 'warranty/registration_form.html'
    success_url = reverse_lazy('warranty:registration_list')

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
