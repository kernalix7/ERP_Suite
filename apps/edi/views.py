from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import (
    CreateView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from apps.core.mixins import ManagerRequiredMixin

from .forms import (
    EDIDocumentTypeForm,
    EDIMappingForm,
    EDIPartnerForm,
    EDIScheduleForm,
)
from .models import (
    EDIDocumentType,
    EDIMapping,
    EDIPartner,
    EDISchedule,
    EDITransaction,
)


# ── EDI Partner views ──

class EDIPartnerListView(ManagerRequiredMixin, ListView):
    model = EDIPartner
    template_name = 'edi/partner_list.html'
    context_object_name = 'edi_partners'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related('partner')


class EDIPartnerCreateView(ManagerRequiredMixin, CreateView):
    model = EDIPartner
    form_class = EDIPartnerForm
    template_name = 'edi/partner_form.html'
    success_url = reverse_lazy('edi:partner_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class EDIPartnerUpdateView(ManagerRequiredMixin, UpdateView):
    model = EDIPartner
    form_class = EDIPartnerForm
    template_name = 'edi/partner_form.html'
    success_url = reverse_lazy('edi:partner_list')


# ── Document Type views ──

class DocumentTypeListView(ManagerRequiredMixin, ListView):
    model = EDIDocumentType
    template_name = 'edi/doctype_list.html'
    context_object_name = 'doc_types'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class DocumentTypeCreateView(ManagerRequiredMixin, CreateView):
    model = EDIDocumentType
    form_class = EDIDocumentTypeForm
    template_name = 'edi/doctype_form.html'
    success_url = reverse_lazy('edi:doctype_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class DocumentTypeUpdateView(ManagerRequiredMixin, UpdateView):
    model = EDIDocumentType
    form_class = EDIDocumentTypeForm
    template_name = 'edi/doctype_form.html'
    success_url = reverse_lazy('edi:doctype_list')


# ── Transaction views ──

class TransactionListView(LoginRequiredMixin, ListView):
    model = EDITransaction
    template_name = 'edi/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'partner__partner', 'document_type',
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        direction = self.request.GET.get('direction')
        if direction:
            qs = qs.filter(direction=direction)
        return qs


class TransactionDetailView(LoginRequiredMixin, DetailView):
    model = EDITransaction
    template_name = 'edi/transaction_detail.html'
    context_object_name = 'transaction'
    slug_field = 'transaction_id'
    slug_url_kwarg = 'transaction_id'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related(
            'partner__partner', 'document_type',
        )


class TransactionRetryView(ManagerRequiredMixin, View):
    def post(self, request, transaction_id):
        tx = get_object_or_404(
            EDITransaction, transaction_id=transaction_id, is_active=True,
        )
        if tx.status == EDITransaction.Status.ERROR:
            tx.status = EDITransaction.Status.PENDING
            tx.error_message = ''
            tx.save(update_fields=['status', 'error_message', 'updated_at'])
        return redirect('edi:transaction_detail', transaction_id=tx.transaction_id)


# ── Mapping views ──

class MappingListView(ManagerRequiredMixin, ListView):
    model = EDIMapping
    template_name = 'edi/mapping_list.html'
    context_object_name = 'mappings'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related('document_type')


class MappingCreateView(ManagerRequiredMixin, CreateView):
    model = EDIMapping
    form_class = EDIMappingForm
    template_name = 'edi/mapping_form.html'
    success_url = reverse_lazy('edi:mapping_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class MappingUpdateView(ManagerRequiredMixin, UpdateView):
    model = EDIMapping
    form_class = EDIMappingForm
    template_name = 'edi/mapping_form.html'
    success_url = reverse_lazy('edi:mapping_list')


# ── Schedule views ──

class ScheduleListView(ManagerRequiredMixin, ListView):
    model = EDISchedule
    template_name = 'edi/schedule_list.html'
    context_object_name = 'schedules'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related(
            'partner__partner', 'document_type',
        )


class ScheduleCreateView(ManagerRequiredMixin, CreateView):
    model = EDISchedule
    form_class = EDIScheduleForm
    template_name = 'edi/schedule_form.html'
    success_url = reverse_lazy('edi:schedule_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ScheduleUpdateView(ManagerRequiredMixin, UpdateView):
    model = EDISchedule
    form_class = EDIScheduleForm
    template_name = 'edi/schedule_form.html'
    success_url = reverse_lazy('edi:schedule_list')


# ── Dashboard ──

class EDIDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'edi/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        transactions = EDITransaction.objects.filter(is_active=True)
        ctx['total_count'] = transactions.count()
        ctx['pending_count'] = transactions.filter(status=EDITransaction.Status.PENDING).count()
        ctx['error_count'] = transactions.filter(status=EDITransaction.Status.ERROR).count()
        ctx['processed_count'] = transactions.filter(status=EDITransaction.Status.PROCESSED).count()
        ctx['by_status'] = (
            transactions.values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )
        ctx['recent_transactions'] = (
            transactions.select_related('partner__partner', 'document_type')
            .order_by('-created_at')[:10]
        )
        return ctx
