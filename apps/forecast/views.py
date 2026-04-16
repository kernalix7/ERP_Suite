from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Avg, Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from apps.module_manager.decorators import ModuleRequiredMixin
from .models import DemandForecast, ForecastParameter, SOPLineItem, SOPMeeting, SOPScenario
from .forms import DemandForecastForm, ForecastParameterForm, SOPMeetingForm


# === 수요예측 ===

class ForecastListView(ModuleRequiredMixin, ListView):
    required_module = 'forecast'
    model = DemandForecast
    template_name = 'forecast/forecast_list.html'
    context_object_name = 'forecasts'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('product')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(product__name__icontains=q)
        method = self.request.GET.get('method')
        if method:
            qs = qs.filter(forecast_method=method)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['method_choices'] = DemandForecast.Method.choices
        return ctx


class ForecastCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'forecast'
    model = DemandForecast
    form_class = DemandForecastForm
    template_name = 'forecast/forecast_form.html'
    success_url = reverse_lazy('forecast:forecast_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        obj = form.save(commit=False)
        obj.calculate_accuracy()
        obj.save()
        messages.success(self.request, '수요예측이 등록되었습니다.')
        return super().form_valid(form)


class ForecastDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'forecast'
    model = DemandForecast
    template_name = 'forecast/forecast_detail.html'
    context_object_name = 'forecast'

    def get_queryset(self):
        return super().get_queryset().select_related('product')


class ForecastAccuracyView(ModuleRequiredMixin, TemplateView):
    required_module = 'forecast'
    template_name = 'forecast/accuracy_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        forecasts = DemandForecast.objects.filter(
            is_active=True, accuracy_pct__isnull=False,
        )
        ctx['avg_accuracy'] = forecasts.aggregate(
            avg=Avg('accuracy_pct'),
        )['avg'] or Decimal('0')
        ctx['total_forecasts'] = forecasts.count()
        ctx['by_method'] = []
        for method_val, method_label in DemandForecast.Method.choices:
            method_qs = forecasts.filter(forecast_method=method_val)
            if method_qs.exists():
                ctx['by_method'].append({
                    'method': method_label,
                    'count': method_qs.count(),
                    'avg_accuracy': method_qs.aggregate(
                        avg=Avg('accuracy_pct'),
                    )['avg'] or Decimal('0'),
                })
        return ctx


# === 예측 파라미터 ===

class ParameterListView(ModuleRequiredMixin, ListView):
    required_module = 'forecast'
    model = ForecastParameter
    template_name = 'forecast/parameter_list.html'
    context_object_name = 'parameters'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(
            is_active=True,
        ).select_related('product')


class ParameterCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'forecast'
    model = ForecastParameter
    form_class = ForecastParameterForm
    template_name = 'forecast/parameter_form.html'
    success_url = reverse_lazy('forecast:parameter_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '예측 파라미터가 등록되었습니다.')
        return super().form_valid(form)


# === S&OP 회의 ===

class SOPMeetingListView(ModuleRequiredMixin, ListView):
    required_module = 'forecast'
    model = SOPMeeting
    template_name = 'forecast/sop_list.html'
    context_object_name = 'meetings'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = SOPMeeting.Status.choices
        return ctx


class SOPMeetingCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'forecast'
    model = SOPMeeting
    form_class = SOPMeetingForm
    template_name = 'forecast/sop_form.html'
    success_url = reverse_lazy('forecast:sop_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'S&OP 회의가 등록되었습니다.')
        return super().form_valid(form)


class SOPMeetingDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'forecast'
    model = SOPMeeting
    template_name = 'forecast/sop_detail.html'
    context_object_name = 'meeting'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['scenarios'] = self.object.scenarios.filter(
            is_active=True,
        ).prefetch_related('line_items')
        return ctx
