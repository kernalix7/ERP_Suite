from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, DetailView, UpdateView

from apps.core.mixins import ManagerRequiredMixin
from apps.module_manager.decorators import ModuleRequiredMixin
from .models import BOMRevision, Drawing, ECNItem, EngineeringChangeNotice, ProductVersion
from .forms import (
    BOMRevisionForm, DrawingForm, EngineeringChangeNoticeForm, ProductVersionForm,
)


# === 제품 버전 ===

class ProductVersionListView(ModuleRequiredMixin, ListView):
    required_module = 'plm'
    model = ProductVersion
    template_name = 'plm/version_list.html'
    context_object_name = 'versions'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('product')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(product__name__icontains=q) | Q(version_number__icontains=q))
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = ProductVersion.Status.choices
        return ctx


class ProductVersionCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'plm'
    model = ProductVersion
    form_class = ProductVersionForm
    template_name = 'plm/version_form.html'
    success_url = reverse_lazy('plm:version_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '제품 버전이 등록되었습니다.')
        return super().form_valid(form)


class ProductVersionDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'plm'
    model = ProductVersion
    template_name = 'plm/version_detail.html'
    context_object_name = 'version'

    def get_queryset(self):
        return super().get_queryset().select_related('product')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['drawings'] = self.object.drawings.filter(is_active=True)
        return ctx


# === BOM 리비전 ===

class BOMRevisionListView(ModuleRequiredMixin, ListView):
    required_module = 'plm'
    model = BOMRevision
    template_name = 'plm/bomrevision_list.html'
    context_object_name = 'revisions'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('bom', 'approved_by')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = BOMRevision.Status.choices
        return ctx


class BOMRevisionDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'plm'
    model = BOMRevision
    template_name = 'plm/bomrevision_detail.html'
    context_object_name = 'revision'

    def get_queryset(self):
        return super().get_queryset().select_related('bom', 'approved_by')


# === ECN ===

class ECNListView(ModuleRequiredMixin, ListView):
    required_module = 'plm'
    model = EngineeringChangeNotice
    template_name = 'plm/ecn_list.html'
    context_object_name = 'ecns'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('requested_by')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(ecn_number__icontains=q))
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = EngineeringChangeNotice.Status.choices
        return ctx


class ECNCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'plm'
    model = EngineeringChangeNotice
    form_class = EngineeringChangeNoticeForm
    template_name = 'plm/ecn_form.html'
    success_url = reverse_lazy('plm:ecn_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.requested_by = self.request.user
        messages.success(self.request, 'ECN이 등록되었습니다.')
        return super().form_valid(form)


class ECNDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'plm'
    model = EngineeringChangeNotice
    template_name = 'plm/ecn_detail.html'
    context_object_name = 'ecn'

    def get_queryset(self):
        return super().get_queryset().select_related('requested_by', 'approved_by')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.filter(
            is_active=True,
        ).select_related('product')
        ctx['affected_products'] = self.object.affected_products.filter(is_active=True)
        return ctx


class ECNUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'plm'
    model = EngineeringChangeNotice
    form_class = EngineeringChangeNoticeForm
    template_name = 'plm/ecn_form.html'

    def get_success_url(self):
        return reverse_lazy('plm:ecn_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, 'ECN이 수정되었습니다.')
        return super().form_valid(form)


# === 도면 ===

class DrawingListView(ModuleRequiredMixin, ListView):
    required_module = 'plm'
    model = Drawing
    template_name = 'plm/drawing_list.html'
    context_object_name = 'drawings'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('product', 'version')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(drawing_number__icontains=q) | Q(product__name__icontains=q))
        return qs


class DrawingCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'plm'
    model = Drawing
    form_class = DrawingForm
    template_name = 'plm/drawing_form.html'
    success_url = reverse_lazy('plm:drawing_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '도면이 업로드되었습니다.')
        return super().form_valid(form)
