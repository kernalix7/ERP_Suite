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
from .forms import (
    CardTransactionMatchForm, CorporateCardForm, ExpenseCategoryForm,
    ExpenseClaimForm, ExpenseItemFormSet, ExpensePolicyForm,
)
from .models import (
    CardTransaction, CorporateCard, ExpenseCategory, ExpenseClaim,
    ExpenseItem, ExpensePolicy,
)


# ──── Policy ────

class ExpensePolicyListView(ManagerRequiredMixin, ListView):
    model = ExpensePolicy
    template_name = 'expense/policy_list.html'
    context_object_name = 'policies'
    paginate_by = 20

    def get_queryset(self):
        return ExpensePolicy.objects.filter(is_active=True)


class ExpensePolicyCreateView(ManagerRequiredMixin, CreateView):
    model = ExpensePolicy
    form_class = ExpensePolicyForm
    template_name = 'expense/policy_form.html'
    success_url = reverse_lazy('expense:policy_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '경비 정책이 등록되었습니다.')
        return super().form_valid(form)


class ExpensePolicyUpdateView(ManagerRequiredMixin, UpdateView):
    model = ExpensePolicy
    form_class = ExpensePolicyForm
    template_name = 'expense/policy_form.html'
    success_url = reverse_lazy('expense:policy_list')

    def form_valid(self, form):
        messages.success(self.request, '경비 정책이 수정되었습니다.')
        return super().form_valid(form)


# ──── Category ────

class ExpenseCategoryListView(ManagerRequiredMixin, ListView):
    model = ExpenseCategory
    template_name = 'expense/category_list.html'
    context_object_name = 'categories'
    paginate_by = 20

    def get_queryset(self):
        return ExpenseCategory.objects.filter(is_active=True).select_related(
            'account_code', 'parent', 'policy',
        )


class ExpenseCategoryCreateView(ManagerRequiredMixin, CreateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = 'expense/category_form.html'
    success_url = reverse_lazy('expense:category_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '경비 카테고리가 등록되었습니다.')
        return super().form_valid(form)


class ExpenseCategoryUpdateView(ManagerRequiredMixin, UpdateView):
    model = ExpenseCategory
    form_class = ExpenseCategoryForm
    template_name = 'expense/category_form.html'
    success_url = reverse_lazy('expense:category_list')

    def form_valid(self, form):
        messages.success(self.request, '경비 카테고리가 수정되었습니다.')
        return super().form_valid(form)


# ──── Expense Claim ────

class ExpenseClaimListView(LoginRequiredMixin, ListView):
    model = ExpenseClaim
    template_name = 'expense/claim_list.html'
    context_object_name = 'claims'
    paginate_by = 20

    def get_queryset(self):
        qs = ExpenseClaim.objects.filter(is_active=True).select_related('employee', 'approved_by')
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(claim_number__icontains=q),
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = ExpenseClaim.Status.choices
        return ctx


class ExpenseClaimCreateView(LoginRequiredMixin, CreateView):
    model = ExpenseClaim
    form_class = ExpenseClaimForm
    template_name = 'expense/claim_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['items_formset'] = ExpenseItemFormSet(self.request.POST, self.request.FILES)
        else:
            ctx['items_formset'] = ExpenseItemFormSet()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['items_formset']
        form.instance.created_by = self.request.user
        # Try to link employee profile
        if hasattr(self.request.user, 'employee_profile'):
            form.instance.employee = self.request.user.employee_profile
        self.object = form.save()
        if formset.is_valid():
            formset.instance = self.object
            for item_form in formset:
                if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE'):
                    item_form.instance.created_by = self.request.user
            formset.save()
            self.object.recalculate_total()
        messages.success(self.request, '경비 청구가 등록되었습니다.')
        return redirect('expense:claim_detail', slug=self.object.claim_number)


class ExpenseClaimDetailView(LoginRequiredMixin, DetailView):
    model = ExpenseClaim
    template_name = 'expense/claim_detail.html'
    slug_field = 'claim_number'

    def get_queryset(self):
        return ExpenseClaim.objects.filter(is_active=True).select_related(
            'employee', 'approved_by',
        ).prefetch_related('items__category')


class ExpenseClaimSubmitView(LoginRequiredMixin, View):
    def post(self, request, slug):
        claim = get_object_or_404(ExpenseClaim, claim_number=slug, is_active=True)
        if claim.status != ExpenseClaim.Status.DRAFT:
            messages.error(request, '작성중 상태만 제출할 수 있습니다.')
            return redirect('expense:claim_detail', slug=slug)
        claim.status = ExpenseClaim.Status.SUBMITTED
        claim.submitted_date = date.today()
        claim.save(update_fields=['status', 'submitted_date', 'updated_at'])
        messages.success(request, '경비 청구가 제출되었습니다.')
        return redirect('expense:claim_detail', slug=slug)


class ExpenseClaimApproveView(ManagerRequiredMixin, View):
    def post(self, request, slug):
        claim = get_object_or_404(ExpenseClaim, claim_number=slug, is_active=True)
        if claim.status != ExpenseClaim.Status.SUBMITTED:
            messages.error(request, '제출된 청구만 승인할 수 있습니다.')
            return redirect('expense:claim_detail', slug=slug)
        claim.status = ExpenseClaim.Status.APPROVED
        claim.approved_by = request.user
        claim.approved_date = date.today()
        claim.save(update_fields=['status', 'approved_by', 'approved_date', 'updated_at'])
        messages.success(request, '경비 청구가 승인되었습니다.')
        return redirect('expense:claim_detail', slug=slug)


class ExpenseClaimRejectView(ManagerRequiredMixin, View):
    def post(self, request, slug):
        claim = get_object_or_404(ExpenseClaim, claim_number=slug, is_active=True)
        if claim.status != ExpenseClaim.Status.SUBMITTED:
            messages.error(request, '제출된 청구만 반려할 수 있습니다.')
            return redirect('expense:claim_detail', slug=slug)
        claim.status = ExpenseClaim.Status.REJECTED
        claim.rejection_reason = request.POST.get('reason', '')
        claim.save(update_fields=['status', 'rejection_reason', 'updated_at'])
        messages.success(request, '경비 청구가 반려되었습니다.')
        return redirect('expense:claim_detail', slug=slug)


# ──── Corporate Card ────

class CorporateCardListView(ManagerRequiredMixin, ListView):
    model = CorporateCard
    template_name = 'expense/card_list.html'
    context_object_name = 'cards'
    paginate_by = 20

    def get_queryset(self):
        return CorporateCard.objects.filter(is_active=True).select_related('employee')


class CorporateCardCreateView(ManagerRequiredMixin, CreateView):
    model = CorporateCard
    form_class = CorporateCardForm
    template_name = 'expense/card_form.html'
    success_url = reverse_lazy('expense:card_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, '법인카드가 등록되었습니다.')
        return super().form_valid(form)


# ──── Card Transaction ────

class CardTransactionListView(ManagerRequiredMixin, ListView):
    model = CardTransaction
    template_name = 'expense/transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 20

    def get_queryset(self):
        qs = CardTransaction.objects.filter(is_active=True).select_related(
            'card', 'category', 'matched_expense',
        )
        matched = self.request.GET.get('matched')
        if matched == 'yes':
            qs = qs.filter(matched_expense__isnull=False)
        elif matched == 'no':
            qs = qs.filter(matched_expense__isnull=True, is_personal=False)
        return qs


class CardTransactionMatchView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        txn = get_object_or_404(CardTransaction, pk=pk, is_active=True)
        form = CardTransactionMatchForm(request.POST)
        if form.is_valid():
            expense_item = form.cleaned_data.get('expense_item')
            txn.matched_expense = expense_item
            txn.save(update_fields=['matched_expense', 'updated_at'])
            messages.success(request, '카드 거래가 매칭되었습니다.')
        return redirect('expense:transaction_list')


# ──── Dashboard ────

class ExpenseDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'expense/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        claims = ExpenseClaim.objects.filter(is_active=True)

        ctx['total_claims'] = claims.count()
        ctx['pending_claims'] = claims.filter(status=ExpenseClaim.Status.SUBMITTED).count()
        ctx['approved_total'] = claims.filter(
            status__in=[ExpenseClaim.Status.APPROVED, ExpenseClaim.Status.PAID],
        ).aggregate(total=Sum('total_amount'))['total'] or 0
        ctx['monthly_total'] = claims.filter(
            status__in=[ExpenseClaim.Status.APPROVED, ExpenseClaim.Status.PAID],
            approved_date__year=today.year,
            approved_date__month=today.month,
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # Unmatched card transactions
        ctx['unmatched_transactions'] = CardTransaction.objects.filter(
            is_active=True, matched_expense__isnull=True, is_personal=False,
        ).count()

        # Recent claims
        ctx['recent_claims'] = claims.order_by('-pk')[:10]

        return ctx
