from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView, TemplateView

from apps.core.mixins import ManagerRequiredMixin
from apps.module_manager.decorators import ModuleRequiredMixin
from .models import AuditFinding, CAPA, InternalAudit, ISODocument, NonConformance
from .forms import (
    CAPAForm, CAPAVerifyForm, InternalAuditForm, ISODocumentForm,
    NonConformanceForm, NonConformanceResolveForm,
)


# === 부적합 ===

class NCListView(ModuleRequiredMixin, ListView):
    required_module = 'qms'
    model = NonConformance
    template_name = 'qms/nc_list.html'
    context_object_name = 'ncs'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('product', 'detected_by')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(nc_number__icontains=q))
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        severity = self.request.GET.get('severity')
        if severity:
            qs = qs.filter(severity=severity)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = NonConformance.Status.choices
        ctx['severity_choices'] = NonConformance.Severity.choices
        return ctx


class NCCreateView(ModuleRequiredMixin, CreateView):
    required_module = 'qms'
    model = NonConformance
    form_class = NonConformanceForm
    template_name = 'qms/nc_form.html'
    success_url = reverse_lazy('qms:nc_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.detected_by = self.request.user
        messages.success(self.request, '부적합이 등록되었습니다.')
        return super().form_valid(form)


class NCDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'qms'
    model = NonConformance
    template_name = 'qms/nc_detail.html'
    context_object_name = 'nc'

    def get_queryset(self):
        return super().get_queryset().select_related('product', 'detected_by')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['capas'] = self.object.capas.filter(is_active=True)
        return ctx


class NCResolveView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'qms'
    model = NonConformance
    form_class = NonConformanceResolveForm
    template_name = 'qms/nc_resolve.html'

    def get_success_url(self):
        return reverse_lazy('qms:nc_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        form.instance.status = NonConformance.Status.RESOLVED
        messages.success(self.request, '부적합이 해결 처리되었습니다.')
        return super().form_valid(form)


# === CAPA ===

class CAPAListView(ModuleRequiredMixin, ListView):
    required_module = 'qms'
    model = CAPA
    template_name = 'qms/capa_list.html'
    context_object_name = 'capas'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('nc', 'assigned_to')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        capa_type = self.request.GET.get('type')
        if capa_type:
            qs = qs.filter(type=capa_type)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = CAPA.Status.choices
        ctx['type_choices'] = CAPA.Type.choices
        return ctx


class CAPACreateView(ModuleRequiredMixin, CreateView):
    required_module = 'qms'
    model = CAPA
    form_class = CAPAForm
    template_name = 'qms/capa_form.html'
    success_url = reverse_lazy('qms:capa_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'CAPA가 등록되었습니다.')
        return super().form_valid(form)


class CAPADetailView(ModuleRequiredMixin, DetailView):
    required_module = 'qms'
    model = CAPA
    template_name = 'qms/capa_detail.html'
    context_object_name = 'capa'

    def get_queryset(self):
        return super().get_queryset().select_related('nc', 'assigned_to')


class CAPAVerifyView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'qms'
    model = CAPA
    form_class = CAPAVerifyForm
    template_name = 'qms/capa_verify.html'

    def get_success_url(self):
        return reverse_lazy('qms:capa_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        form.instance.status = CAPA.Status.VERIFIED
        messages.success(self.request, 'CAPA 유효성 검증이 완료되었습니다.')
        return super().form_valid(form)


# === 내부감사 ===

class AuditListView(ModuleRequiredMixin, ListView):
    required_module = 'qms'
    model = InternalAudit
    template_name = 'qms/audit_list.html'
    context_object_name = 'audits'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('auditor')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = InternalAudit.Status.choices
        return ctx


class AuditCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'qms'
    model = InternalAudit
    form_class = InternalAuditForm
    template_name = 'qms/audit_form.html'
    success_url = reverse_lazy('qms:audit_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '내부감사가 등록되었습니다.')
        return super().form_valid(form)


class AuditDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'qms'
    model = InternalAudit
    template_name = 'qms/audit_detail.html'
    context_object_name = 'audit'

    def get_queryset(self):
        return super().get_queryset().select_related('auditor')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['findings'] = self.object.audit_findings.filter(
            is_active=True,
        ).select_related('capa')
        return ctx


# === ISO 문서 ===

class ISODocListView(ModuleRequiredMixin, ListView):
    required_module = 'qms'
    model = ISODocument
    template_name = 'qms/isodoc_list.html'
    context_object_name = 'documents'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(document_number__icontains=q))
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = ISODocument.Status.choices
        return ctx


class ISODocCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'qms'
    model = ISODocument
    form_class = ISODocumentForm
    template_name = 'qms/isodoc_form.html'
    success_url = reverse_lazy('qms:isodoc_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'ISO 문서가 등록되었습니다.')
        return super().form_valid(form)


class ISODocDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'qms'
    model = ISODocument
    template_name = 'qms/isodoc_detail.html'
    context_object_name = 'document'

    def get_queryset(self):
        return super().get_queryset().select_related('approved_by')


# === 대시보드 ===

class QmsDashboardView(ModuleRequiredMixin, TemplateView):
    required_module = 'qms'
    template_name = 'qms/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['open_ncs'] = NonConformance.objects.filter(
            is_active=True, status__in=['OPEN', 'INVESTIGATING'],
        ).count()
        ctx['open_capas'] = CAPA.objects.filter(
            is_active=True, status__in=['OPEN', 'IN_PROGRESS'],
        ).count()
        ctx['planned_audits'] = InternalAudit.objects.filter(
            is_active=True, status=InternalAudit.Status.PLANNED,
        ).count()
        ctx['active_docs'] = ISODocument.objects.filter(
            is_active=True, status=ISODocument.Status.ACTIVE,
        ).count()
        return ctx
