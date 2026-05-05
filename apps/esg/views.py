from datetime import date

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView, DetailView, ListView, TemplateView, UpdateView, View,
)

from apps.core.mixins import ManagerRequiredMixin
from apps.module_manager.decorators import ModuleRequiredMixin
from .forms import (
    CarbonEmissionForm, ComplianceRequirementForm, ESGCategoryForm,
    ESGMetricForm, ESGRecordForm, ESGReportForm, SafetyIncidentForm,
)
from .models import (
    CarbonEmission, ComplianceRequirement, ESGCategory, ESGMetric,
    ESGRecord, ESGReport, SafetyIncident,
)


# ──── ESG Metric ────

class ESGMetricListView(ModuleRequiredMixin, ListView):
    required_module = 'esg'
    model = ESGMetric
    template_name = 'esg/metric_list.html'
    context_object_name = 'metrics'
    paginate_by = 20

    def get_queryset(self):
        qs = ESGMetric.objects.filter(is_active=True).select_related('category')
        cat_type = self.request.GET.get('category_type')
        if cat_type:
            qs = qs.filter(category__category_type=cat_type)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['category_types'] = ESGCategory.CategoryType.choices
        return ctx


class ESGMetricCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'esg'
    model = ESGMetric
    form_class = ESGMetricForm
    template_name = 'esg/metric_form.html'
    success_url = reverse_lazy('esg:metric_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'ESG 지표가 등록되었습니다.')
        return super().form_valid(form)


class ESGMetricUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'esg'
    model = ESGMetric
    form_class = ESGMetricForm
    template_name = 'esg/metric_form.html'
    success_url = reverse_lazy('esg:metric_list')

    def form_valid(self, form):
        messages.success(self.request, 'ESG 지표가 수정되었습니다.')
        return super().form_valid(form)


# ──── ESG Record ────

class ESGRecordListView(ModuleRequiredMixin, ListView):
    required_module = 'esg'
    model = ESGRecord
    template_name = 'esg/record_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        qs = ESGRecord.objects.filter(is_active=True).select_related(
            'metric__category', 'recorded_by',
        )
        metric = self.request.GET.get('metric')
        if metric:
            qs = qs.filter(metric_id=metric)
        return qs


class ESGRecordCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'esg'
    model = ESGRecord
    form_class = ESGRecordForm
    template_name = 'esg/record_form.html'
    success_url = reverse_lazy('esg:record_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.recorded_by = self.request.user
        messages.success(self.request, 'ESG 실적이 기록되었습니다.')
        return super().form_valid(form)


# ──── Carbon Emission ────

class CarbonDashboardView(ModuleRequiredMixin, TemplateView):
    required_module = 'esg'
    template_name = 'esg/carbon_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        emissions = CarbonEmission.objects.filter(is_active=True)

        ctx['total_emission'] = emissions.aggregate(
            total=Sum('amount_kg'),
        )['total'] or 0
        ctx['scope1'] = emissions.filter(scope=CarbonEmission.Scope.SCOPE1).aggregate(
            total=Sum('amount_kg'),
        )['total'] or 0
        ctx['scope2'] = emissions.filter(scope=CarbonEmission.Scope.SCOPE2).aggregate(
            total=Sum('amount_kg'),
        )['total'] or 0
        ctx['scope3'] = emissions.filter(scope=CarbonEmission.Scope.SCOPE3).aggregate(
            total=Sum('amount_kg'),
        )['total'] or 0

        # Monthly trend (current year)
        today = date.today()
        monthly = emissions.filter(
            period__year=today.year,
        ).values('period__month').annotate(
            total=Sum('amount_kg'),
        ).order_by('period__month')
        ctx['monthly_emissions'] = list(monthly)

        return ctx


class CarbonEmissionListView(ModuleRequiredMixin, ListView):
    required_module = 'esg'
    model = CarbonEmission
    template_name = 'esg/carbon_list.html'
    context_object_name = 'emissions'
    paginate_by = 20

    def get_queryset(self):
        qs = CarbonEmission.objects.filter(is_active=True).select_related('created_by')
        scope = self.request.GET.get('scope')
        if scope:
            qs = qs.filter(scope=scope)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['scope_choices'] = CarbonEmission.Scope.choices
        return ctx


class CarbonEmissionCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'esg'
    model = CarbonEmission
    form_class = CarbonEmissionForm
    template_name = 'esg/carbon_form.html'
    success_url = reverse_lazy('esg:carbon_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '탄소 배출 데이터가 등록되었습니다.')
        return super().form_valid(form)


# ──── Safety Incident ────

class SafetyIncidentListView(ModuleRequiredMixin, ListView):
    required_module = 'esg'
    model = SafetyIncident
    template_name = 'esg/incident_list.html'
    context_object_name = 'incidents'
    paginate_by = 20

    def get_queryset(self):
        qs = SafetyIncident.objects.filter(is_active=True).select_related('reported_by', 'created_by')
        severity = self.request.GET.get('severity')
        if severity:
            qs = qs.filter(severity=severity)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['severity_choices'] = SafetyIncident.Severity.choices
        ctx['status_choices'] = SafetyIncident.Status.choices
        return ctx


class SafetyIncidentCreateView(ModuleRequiredMixin, CreateView):
    required_module = 'esg'
    model = SafetyIncident
    form_class = SafetyIncidentForm
    template_name = 'esg/incident_form.html'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.reported_by = self.request.user
        messages.success(self.request, '안전 사고가 보고되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('esg:incident_detail', kwargs={'slug': self.object.incident_number})


class SafetyIncidentDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'esg'
    model = SafetyIncident
    template_name = 'esg/incident_detail.html'
    slug_field = 'incident_number'

    def get_queryset(self):
        return SafetyIncident.objects.filter(is_active=True)


class SafetyIncidentUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'esg'
    model = SafetyIncident
    form_class = SafetyIncidentForm
    template_name = 'esg/incident_form.html'
    slug_field = 'incident_number'

    def get_queryset(self):
        return SafetyIncident.objects.filter(is_active=True)

    def form_valid(self, form):
        messages.success(self.request, '안전 사고 정보가 수정되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('esg:incident_detail', kwargs={'slug': self.object.incident_number})


# ──── Compliance ────

class ComplianceListView(ModuleRequiredMixin, ListView):
    required_module = 'esg'
    model = ComplianceRequirement
    template_name = 'esg/compliance_list.html'
    context_object_name = 'requirements'
    paginate_by = 20

    def get_queryset(self):
        qs = ComplianceRequirement.objects.filter(is_active=True).select_related('responsible')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = ComplianceRequirement.Status.choices
        return ctx


class ComplianceCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'esg'
    model = ComplianceRequirement
    form_class = ComplianceRequirementForm
    template_name = 'esg/compliance_form.html'
    success_url = reverse_lazy('esg:compliance_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '컴플라이언스 요구사항이 등록되었습니다.')
        return super().form_valid(form)


class ComplianceUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'esg'
    model = ComplianceRequirement
    form_class = ComplianceRequirementForm
    template_name = 'esg/compliance_form.html'
    success_url = reverse_lazy('esg:compliance_list')

    def form_valid(self, form):
        messages.success(self.request, '컴플라이언스 요구사항이 수정되었습니다.')
        return super().form_valid(form)


# ──── ESG Report ────

class ESGReportListView(ModuleRequiredMixin, ListView):
    required_module = 'esg'
    model = ESGReport
    template_name = 'esg/report_list.html'
    context_object_name = 'reports'
    paginate_by = 20

    def get_queryset(self):
        return ESGReport.objects.filter(is_active=True).select_related('created_by')


class ESGReportCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'esg'
    model = ESGReport
    form_class = ESGReportForm
    template_name = 'esg/report_form.html'
    success_url = reverse_lazy('esg:report_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.generated_at = timezone.now()
        messages.success(self.request, 'ESG 보고서가 생성되었습니다.')
        return super().form_valid(form)


class ESGReportDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'esg'
    model = ESGReport
    template_name = 'esg/report_detail.html'

    def get_queryset(self):
        return ESGReport.objects.filter(is_active=True)


# ──── ESG Dashboard ────

class ESGDashboardView(ModuleRequiredMixin, TemplateView):
    required_module = 'esg'
    template_name = 'esg/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()

        # Carbon totals
        emissions = CarbonEmission.objects.filter(is_active=True, period__year=today.year)
        ctx['yearly_carbon'] = emissions.aggregate(total=Sum('amount_kg'))['total'] or 0

        # Safety stats
        incidents = SafetyIncident.objects.filter(is_active=True, date__year=today.year)
        ctx['incident_count'] = incidents.count()
        ctx['critical_incidents'] = incidents.filter(severity=SafetyIncident.Severity.CRITICAL).count()
        ctx['open_incidents'] = incidents.exclude(status=SafetyIncident.Status.CLOSED).count()

        # Compliance stats
        compliance = ComplianceRequirement.objects.filter(is_active=True)
        ctx['total_compliance'] = compliance.count()
        ctx['compliant_count'] = compliance.filter(
            status=ComplianceRequirement.Status.COMPLIANT,
        ).count()
        ctx['non_compliant_count'] = compliance.filter(
            status=ComplianceRequirement.Status.NON_COMPLIANT,
        ).count()
        ctx['overdue_compliance'] = compliance.filter(
            due_date__lt=today,
            status__in=[ComplianceRequirement.Status.PENDING, ComplianceRequirement.Status.IN_PROGRESS],
        ).count()

        # ESG category breakdown
        ctx['categories'] = ESGCategory.objects.filter(is_active=True).annotate(
            metric_count=Count('metrics'),
        )

        return ctx
