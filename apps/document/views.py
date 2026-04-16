from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
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
    ContractForm, ContractMilestoneForm, DocumentApprovalActionForm,
    DocumentApprovalForm, DocumentCategoryForm, DocumentForm,
    DocumentVersionForm,
)
from .models import (
    Contract, ContractMilestone, Document, DocumentApproval,
    DocumentCategory, DocumentVersion,
)


# ──── Document Category ────

class DocumentCategoryListView(ModuleRequiredMixin, ManagerRequiredMixin, ListView):
    required_module = 'document'
    model = DocumentCategory
    template_name = 'document/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def get_queryset(self):
        return DocumentCategory.objects.filter(is_active=True).select_related('parent')


class DocumentCategoryCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'document'
    model = DocumentCategory
    form_class = DocumentCategoryForm
    template_name = 'document/category_form.html'
    success_url = reverse_lazy('document:category_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '문서 카테고리가 등록되었습니다.')
        return super().form_valid(form)


class DocumentCategoryUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'document'
    model = DocumentCategory
    form_class = DocumentCategoryForm
    template_name = 'document/category_form.html'
    success_url = reverse_lazy('document:category_list')

    def form_valid(self, form):
        messages.success(self.request, '문서 카테고리가 수정되었습니다.')
        return super().form_valid(form)


# ──── Document CRUD ────

class DocumentListView(ModuleRequiredMixin, ListView):
    required_module = 'document'
    model = Document
    template_name = 'document/document_list.html'
    context_object_name = 'documents'
    paginate_by = 20

    def get_queryset(self):
        qs = Document.objects.filter(is_active=True).select_related(
            'category', 'owner', 'department',
        )
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(document_number__icontains=q),
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category_id=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Document.Status.choices
        ctx['categories'] = DocumentCategory.objects.filter(is_active=True)
        return ctx


class DocumentCreateView(ModuleRequiredMixin, CreateView):
    required_module = 'document'
    model = Document
    form_class = DocumentForm
    template_name = 'document/document_form.html'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.owner = self.request.user
        messages.success(self.request, '문서가 등록되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('document:document_detail', kwargs={'slug': self.object.document_number})


class DocumentDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'document'
    model = Document
    template_name = 'document/document_detail.html'
    slug_field = 'document_number'

    def get_queryset(self):
        return Document.objects.filter(is_active=True).select_related(
            'category', 'owner', 'department',
        ).prefetch_related('versions', 'approvals__approver')


class DocumentUpdateView(ModuleRequiredMixin, UpdateView):
    required_module = 'document'
    model = Document
    form_class = DocumentForm
    template_name = 'document/document_form.html'
    slug_field = 'document_number'

    def get_queryset(self):
        qs = Document.objects.filter(is_active=True)
        if not self.request.user.is_superuser and getattr(self.request.user, 'role', '') not in ('admin', 'manager'):
            qs = qs.filter(owner=self.request.user)
        return qs

    def form_valid(self, form):
        messages.success(self.request, '문서가 수정되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('document:document_detail', kwargs={'slug': self.object.document_number})


class DocumentSearchView(ModuleRequiredMixin, ListView):
    required_module = 'document'
    model = Document
    template_name = 'document/document_search.html'
    context_object_name = 'documents'
    paginate_by = 20

    def get_queryset(self):
        qs = Document.objects.filter(is_active=True).select_related(
            'category', 'owner',
        )
        q = self.request.GET.get('q', '')
        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(document_number__icontains=q)
                | Q(tags__icontains=q),
            )
        access = self.request.GET.get('access_level')
        if access:
            qs = qs.filter(access_level=access)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['access_choices'] = Document.AccessLevel.choices
        return ctx


# ──── Document Version ────

class DocumentVersionCreateView(ModuleRequiredMixin, CreateView):
    required_module = 'document'
    model = DocumentVersion
    form_class = DocumentVersionForm
    template_name = 'document/version_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.document = get_object_or_404(
            Document, document_number=kwargs['slug'], is_active=True,
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.document = self.document
        with transaction.atomic():
            doc = Document.objects.select_for_update().get(pk=self.document.pk)
            new_version = doc.version + 1
            form.instance.version_number = new_version
            doc.version = new_version
            doc.save(update_fields=['version', 'updated_at'])
            self.document = doc
        messages.success(self.request, f'버전 {new_version}이 등록되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('document:document_detail', kwargs={'slug': self.document.document_number})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['document'] = self.document
        return ctx


# ──── Document Approval ────

class DocumentApprovalRequestView(ModuleRequiredMixin, CreateView):
    required_module = 'document'
    model = DocumentApproval
    form_class = DocumentApprovalForm
    template_name = 'document/approval_request_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.document = get_object_or_404(
            Document, document_number=kwargs['slug'], is_active=True,
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.document = self.document
        self.document.status = Document.Status.REVIEW
        self.document.save(update_fields=['status', 'updated_at'])
        messages.success(self.request, '결재 요청이 등록되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('document:document_detail', kwargs={'slug': self.document.document_number})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['document'] = self.document
        return ctx


class DocumentApprovalActionView(ModuleRequiredMixin, View):
    required_module = 'document'

    def post(self, request, pk, action):
        approval = get_object_or_404(
            DocumentApproval, pk=pk, approver=request.user, is_active=True,
        )
        # 이전 단계 미승인 시 현재 단계 승인/반려 차단
        prior_pending = DocumentApproval.objects.filter(
            document=approval.document,
            is_active=True,
            pk__lt=approval.pk,
            status=DocumentApproval.Status.PENDING,
        ).exists()
        if prior_pending:
            messages.error(request, '이전 결재 단계가 완료되지 않았습니다.')
            return redirect('document:document_detail', slug=approval.document.document_number)

        form = DocumentApprovalActionForm(request.POST)
        if form.is_valid():
            if action == 'approve':
                approval.status = DocumentApproval.Status.APPROVED
                approval.approved_at = timezone.now()
                # 모든 결재가 승인되었는지 확인 후 문서 상태 변경
                remaining = DocumentApproval.objects.filter(
                    document=approval.document,
                    is_active=True,
                    status=DocumentApproval.Status.PENDING,
                ).exclude(pk=approval.pk).exists()
                if not remaining:
                    approval.document.status = Document.Status.APPROVED
                    approval.document.save(update_fields=['status', 'updated_at'])
                messages.success(request, '문서가 승인되었습니다.')
            elif action == 'reject':
                approval.status = DocumentApproval.Status.REJECTED
                approval.approved_at = timezone.now()
                approval.document.status = Document.Status.DRAFT
                approval.document.save(update_fields=['status', 'updated_at'])
                messages.warning(request, '문서가 반려되었습니다.')
            approval.comment = form.cleaned_data.get('comment', '')
            approval.save()
        return redirect('document:document_detail', slug=approval.document.document_number)


# ──── Contract CRUD ────

class ContractListView(ModuleRequiredMixin, ListView):
    required_module = 'document'
    model = Contract
    template_name = 'document/contract_list.html'
    context_object_name = 'contracts'
    paginate_by = 20

    def get_queryset(self):
        qs = Contract.objects.filter(is_active=True).select_related('partner', 'signed_by')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(contract_number__icontains=q),
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        ctype = self.request.GET.get('contract_type')
        if ctype:
            qs = qs.filter(contract_type=ctype)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = Contract.Status.choices
        ctx['type_choices'] = Contract.ContractType.choices
        return ctx


class ContractCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'document'
    model = Contract
    form_class = ContractForm
    template_name = 'document/contract_form.html'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '계약이 등록되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('document:contract_detail', kwargs={'slug': self.object.contract_number})


class ContractDetailView(ModuleRequiredMixin, DetailView):
    required_module = 'document'
    model = Contract
    template_name = 'document/contract_detail.html'
    slug_field = 'contract_number'

    def get_queryset(self):
        return Contract.objects.filter(is_active=True).select_related(
            'partner', 'signed_by',
        ).prefetch_related('milestones')


class ContractUpdateView(ModuleRequiredMixin, ManagerRequiredMixin, UpdateView):
    required_module = 'document'
    model = Contract
    form_class = ContractForm
    template_name = 'document/contract_form.html'
    slug_field = 'contract_number'

    def get_queryset(self):
        return Contract.objects.filter(is_active=True)

    def form_valid(self, form):
        messages.success(self.request, '계약이 수정되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('document:contract_detail', kwargs={'slug': self.object.contract_number})


class ContractTerminateView(ModuleRequiredMixin, ManagerRequiredMixin, View):
    required_module = 'document'

    def post(self, request, slug):
        contract = get_object_or_404(Contract, contract_number=slug, is_active=True)
        contract.status = Contract.Status.TERMINATED
        contract.save(update_fields=['status', 'updated_at'])
        messages.success(request, '계약이 해지되었습니다.')
        return redirect('document:contract_detail', slug=slug)


class ContractRenewView(ModuleRequiredMixin, ManagerRequiredMixin, View):
    required_module = 'document'

    def post(self, request, slug):
        contract = get_object_or_404(Contract, contract_number=slug, is_active=True)
        if contract.end_date:
            contract.start_date = contract.end_date
            contract.end_date = contract.end_date + timedelta(days=365)
        contract.status = Contract.Status.ACTIVE
        contract.save(update_fields=['start_date', 'end_date', 'status', 'updated_at'])
        messages.success(request, '계약이 갱신되었습니다.')
        return redirect('document:contract_detail', slug=slug)


# ──── Contract Milestone ────

class ContractMilestoneCreateView(ModuleRequiredMixin, ManagerRequiredMixin, CreateView):
    required_module = 'document'
    model = ContractMilestone
    form_class = ContractMilestoneForm
    template_name = 'document/milestone_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.contract = get_object_or_404(
            Contract, contract_number=kwargs['slug'], is_active=True,
        )
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.contract = self.contract
        messages.success(self.request, '마일스톤이 등록되었습니다.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('document:contract_detail', kwargs={'slug': self.contract.contract_number})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['contract'] = self.contract
        return ctx


# ──── Contract Calendar ────

class ContractCalendarView(ModuleRequiredMixin, ListView):
    required_module = 'document'
    model = Contract
    template_name = 'document/contract_calendar.html'
    context_object_name = 'contracts'
    paginate_by = 20

    def get_queryset(self):
        today = date.today()
        days_ahead = 90
        return Contract.objects.filter(
            is_active=True,
            status=Contract.Status.ACTIVE,
            end_date__lte=today + timedelta(days=days_ahead),
            end_date__gte=today,
        ).select_related('partner').order_by('end_date')


# ──── Dashboard ────

class DocumentDashboardView(ModuleRequiredMixin, TemplateView):
    required_module = 'document'
    template_name = 'document/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()

        # Document stats
        docs = Document.objects.filter(is_active=True)
        ctx['total_documents'] = docs.count()
        ctx['draft_documents'] = docs.filter(status=Document.Status.DRAFT).count()
        ctx['review_documents'] = docs.filter(status=Document.Status.REVIEW).count()
        ctx['approved_documents'] = docs.filter(status=Document.Status.APPROVED).count()

        # Contract stats
        contracts = Contract.objects.filter(is_active=True)
        ctx['total_contracts'] = contracts.count()
        ctx['active_contracts'] = contracts.filter(status=Contract.Status.ACTIVE).count()
        ctx['expiring_contracts'] = contracts.filter(
            status=Contract.Status.ACTIVE,
            end_date__lte=today + timedelta(days=30),
            end_date__gte=today,
        ).count()
        ctx['total_contract_value'] = contracts.filter(
            status=Contract.Status.ACTIVE,
        ).aggregate(total=Sum('value'))['total'] or 0

        # Pending approvals for current user
        ctx['pending_approvals'] = DocumentApproval.objects.filter(
            is_active=True,
            status=DocumentApproval.Status.PENDING,
            approver=self.request.user,
        ).select_related('document').count()

        # Expiring soon contracts
        ctx['expiring_soon'] = Contract.objects.filter(
            is_active=True,
            status=Contract.Status.ACTIVE,
            end_date__lte=today + timedelta(days=30),
            end_date__gte=today,
        ).select_related('partner').order_by('end_date')[:5]

        return ctx
