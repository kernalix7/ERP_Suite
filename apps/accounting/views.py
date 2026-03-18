import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.core.mixins import ManagerRequiredMixin
from django.db.models import F, Sum
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView


def safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

from apps.inventory.models import Product
from apps.sales.models import Order, OrderItem
from .models import (
    TaxRate, TaxInvoice, FixedCost, WithholdingTax, AccountCode, Voucher, VoucherLine,
    ApprovalRequest, ApprovalStep, AccountReceivable, AccountPayable, Payment,
)
from .forms import (
    TaxRateForm, TaxInvoiceForm, FixedCostForm, WithholdingTaxForm,
    AccountCodeForm, VoucherForm, VoucherLineFormSet,
    ApprovalRequestForm, ApprovalActionForm,
    AccountReceivableForm, AccountPayableForm, PaymentForm,
)


class AccountingDashboardView(ManagerRequiredMixin, TemplateView):
    template_name = 'accounting/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        year = today.year

        # 월별 매출 (올해)
        monthly_revenue = []
        monthly_costs = []
        months = []
        for m in range(1, 13):
            months.append(f'{m}월')
            revenue = Order.objects.filter(
                order_date__year=year, order_date__month=m,
                status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED'],
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            monthly_revenue.append(int(revenue))

            costs = FixedCost.objects.filter(
                month__year=year, month__month=m,
            ).aggregate(total=Sum('amount'))['total'] or 0
            monthly_costs.append(int(costs))

        ctx['months_json'] = json.dumps(months)
        ctx['revenue_json'] = json.dumps(monthly_revenue)
        ctx['costs_json'] = json.dumps(monthly_costs)

        # 올해 총 매출/비용/이익
        ctx['year_revenue'] = sum(monthly_revenue)
        ctx['year_costs'] = sum(monthly_costs)
        ctx['year_profit'] = ctx['year_revenue'] - ctx['year_costs']

        # 제품별 이익률
        products = Product.objects.filter(product_type='FINISHED', unit_price__gt=0)
        product_margins = []
        for p in products[:10]:
            product_margins.append({
                'name': p.name,
                'margin': float(p.profit_margin),
                'unit_price': int(p.unit_price),
                'cost_price': int(p.cost_price),
            })
        ctx['product_margins_json'] = json.dumps(product_margins, ensure_ascii=False)

        # 이번 분기 부가세
        quarter = (today.month - 1) // 3 + 1
        q_start_month = (quarter - 1) * 3 + 1
        sales_tax = TaxInvoice.objects.filter(
            invoice_type='SALES', issue_date__year=year,
            issue_date__month__gte=q_start_month,
            issue_date__month__lte=q_start_month + 2,
        ).aggregate(total=Sum('tax_amount'))['total'] or 0
        purchase_tax = TaxInvoice.objects.filter(
            invoice_type='PURCHASE', issue_date__year=year,
            issue_date__month__gte=q_start_month,
            issue_date__month__lte=q_start_month + 2,
        ).aggregate(total=Sum('tax_amount'))['total'] or 0
        ctx['quarter'] = quarter
        ctx['sales_tax'] = sales_tax
        ctx['purchase_tax'] = purchase_tax
        ctx['net_vat'] = sales_tax - purchase_tax

        return ctx


# === 세율 ===
class TaxRateListView(ManagerRequiredMixin, ListView):
    model = TaxRate
    template_name = 'accounting/taxrate_list.html'
    context_object_name = 'tax_rates'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class TaxRateCreateView(ManagerRequiredMixin, CreateView):
    model = TaxRate
    form_class = TaxRateForm
    template_name = 'accounting/taxrate_form.html'
    success_url = reverse_lazy('accounting:taxrate_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class TaxRateUpdateView(ManagerRequiredMixin, UpdateView):
    model = TaxRate
    form_class = TaxRateForm
    template_name = 'accounting/taxrate_form.html'
    success_url = reverse_lazy('accounting:taxrate_list')


# === 세금계산서 ===
class TaxInvoiceListView(ManagerRequiredMixin, ListView):
    model = TaxInvoice
    template_name = 'accounting/taxinvoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'partner', 'order',
        )
        inv_type = self.request.GET.get('type')
        if inv_type:
            qs = qs.filter(invoice_type=inv_type)
        return qs


class TaxInvoiceCreateView(ManagerRequiredMixin, CreateView):
    model = TaxInvoice
    form_class = TaxInvoiceForm
    template_name = 'accounting/taxinvoice_form.html'
    success_url = reverse_lazy('accounting:taxinvoice_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class TaxInvoiceDetailView(ManagerRequiredMixin, DetailView):
    model = TaxInvoice
    template_name = 'accounting/taxinvoice_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'partner', 'order',
        )


class TaxInvoiceUpdateView(ManagerRequiredMixin, UpdateView):
    model = TaxInvoice
    form_class = TaxInvoiceForm
    template_name = 'accounting/taxinvoice_form.html'
    success_url = reverse_lazy('accounting:taxinvoice_list')


# === 부가세 집계 ===
class VATSummaryView(ManagerRequiredMixin, TemplateView):
    template_name = 'accounting/vat_summary.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        year = safe_int(self.request.GET.get('year'), date.today().year)
        ctx['year'] = year
        ctx['years'] = list(range(date.today().year, date.today().year - 5, -1))

        quarters = []
        for q in range(1, 5):
            m_start = (q - 1) * 3 + 1
            m_end = m_start + 2
            sales = TaxInvoice.objects.filter(
                invoice_type='SALES', issue_date__year=year,
                issue_date__month__gte=m_start, issue_date__month__lte=m_end,
            ).aggregate(
                supply=Sum('supply_amount'), tax=Sum('tax_amount'),
            )
            purchase = TaxInvoice.objects.filter(
                invoice_type='PURCHASE', issue_date__year=year,
                issue_date__month__gte=m_start, issue_date__month__lte=m_end,
            ).aggregate(
                supply=Sum('supply_amount'), tax=Sum('tax_amount'),
            )
            s_tax = sales['tax'] or 0
            p_tax = purchase['tax'] or 0
            quarters.append({
                'quarter': q,
                'sales_supply': sales['supply'] or 0,
                'sales_tax': s_tax,
                'purchase_supply': purchase['supply'] or 0,
                'purchase_tax': p_tax,
                'net_vat': s_tax - p_tax,
            })
        ctx['quarters'] = quarters
        ctx['annual_total'] = {
            'sales_tax': sum(q['sales_tax'] for q in quarters),
            'purchase_tax': sum(q['purchase_tax'] for q in quarters),
            'net_vat': sum(q['net_vat'] for q in quarters),
        }
        return ctx


# === 고정비 ===
class FixedCostListView(ManagerRequiredMixin, ListView):
    model = FixedCost
    template_name = 'accounting/fixedcost_list.html'
    context_object_name = 'costs'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        ctx['monthly_total'] = FixedCost.objects.filter(
            month__year=today.year, month__month=today.month,
        ).aggregate(total=Sum('amount'))['total'] or 0
        ctx['categories'] = FixedCost.CostCategory.choices
        return ctx


class FixedCostCreateView(ManagerRequiredMixin, CreateView):
    model = FixedCost
    form_class = FixedCostForm
    template_name = 'accounting/fixedcost_form.html'
    success_url = reverse_lazy('accounting:fixedcost_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class FixedCostUpdateView(ManagerRequiredMixin, UpdateView):
    model = FixedCost
    form_class = FixedCostForm
    template_name = 'accounting/fixedcost_form.html'
    success_url = reverse_lazy('accounting:fixedcost_list')


# === 손익분기점 ===
class BreakEvenView(ManagerRequiredMixin, TemplateView):
    template_name = 'accounting/breakeven.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()

        # 월간 고정비 합계
        monthly_fixed = FixedCost.objects.filter(
            month__year=today.year, month__month=today.month,
        ).aggregate(total=Sum('amount'))['total'] or 0
        ctx['monthly_fixed_cost'] = monthly_fixed

        # 완제품별 손익분기점
        products = Product.objects.filter(product_type='FINISHED', unit_price__gt=0)
        breakeven_data = []
        for p in products:
            # 변동비 = BOM 원가 (자재 원가)
            from apps.production.models import BOM
            bom = BOM.objects.filter(product=p, is_default=True).first()
            variable_cost = int(bom.total_material_cost) if bom else int(p.cost_price)
            contribution = int(p.unit_price) - variable_cost

            if contribution > 0:
                bep_qty = int(monthly_fixed / contribution) if monthly_fixed else 0
                bep_revenue = bep_qty * int(p.unit_price)
            else:
                bep_qty = 0
                bep_revenue = 0

            breakeven_data.append({
                'name': p.name,
                'unit_price': int(p.unit_price),
                'variable_cost': variable_cost,
                'contribution': contribution,
                'bep_quantity': bep_qty,
                'bep_revenue': bep_revenue,
            })

        ctx['breakeven_data'] = breakeven_data
        ctx['breakeven_json'] = json.dumps(breakeven_data, ensure_ascii=False)
        ctx['fixed_cost_breakdown'] = FixedCost.objects.filter(
            month__year=today.year, month__month=today.month,
        ).values('category').annotate(total=Sum('amount')).order_by('-total')
        return ctx


# === 월별 손익 ===
class MonthlyPLView(ManagerRequiredMixin, TemplateView):
    template_name = 'accounting/monthly_pl.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        year = safe_int(self.request.GET.get('year'), date.today().year)
        ctx['year'] = year
        ctx['years'] = list(range(date.today().year, date.today().year - 5, -1))

        monthly_data = []
        for m in range(1, 13):
            # 매출
            revenue = Order.objects.filter(
                order_date__year=year, order_date__month=m,
                status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED'],
            ).aggregate(total=Sum('total_amount'))['total'] or 0

            # 매출원가 (판매된 제품의 원가)
            cogs_items = OrderItem.objects.filter(
                order__order_date__year=year, order__order_date__month=m,
                order__status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED'],
            )
            cogs = sum(
                item.quantity * item.product.cost_price
                for item in cogs_items
            )

            gross_profit = int(revenue) - cogs

            # 고정비
            fixed = FixedCost.objects.filter(
                month__year=year, month__month=m,
            ).aggregate(total=Sum('amount'))['total'] or 0

            net_profit = gross_profit - int(fixed)

            monthly_data.append({
                'month': m,
                'revenue': int(revenue),
                'cogs': cogs,
                'gross_profit': gross_profit,
                'fixed_costs': int(fixed),
                'net_profit': net_profit,
            })

        ctx['monthly_data'] = monthly_data
        ctx['monthly_json'] = json.dumps(monthly_data)

        # 연간 합계
        ctx['annual'] = {
            'revenue': sum(d['revenue'] for d in monthly_data),
            'cogs': sum(d['cogs'] for d in monthly_data),
            'gross_profit': sum(d['gross_profit'] for d in monthly_data),
            'fixed_costs': sum(d['fixed_costs'] for d in monthly_data),
            'net_profit': sum(d['net_profit'] for d in monthly_data),
        }
        return ctx


# === 원천징수 ===
class WithholdingTaxListView(ManagerRequiredMixin, ListView):
    model = WithholdingTax
    template_name = 'accounting/withholding_list.html'
    context_object_name = 'withholdings'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class WithholdingTaxCreateView(ManagerRequiredMixin, CreateView):
    model = WithholdingTax
    form_class = WithholdingTaxForm
    template_name = 'accounting/withholding_form.html'
    success_url = reverse_lazy('accounting:withholding_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class WithholdingTaxUpdateView(ManagerRequiredMixin, UpdateView):
    model = WithholdingTax
    form_class = WithholdingTaxForm
    template_name = 'accounting/withholding_form.html'
    success_url = reverse_lazy('accounting:withholding_list')


# === 계정과목 ===
class AccountCodeListView(ManagerRequiredMixin, ListView):
    model = AccountCode
    template_name = 'accounting/accountcode_list.html'
    context_object_name = 'account_codes'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class AccountCodeCreateView(ManagerRequiredMixin, CreateView):
    model = AccountCode
    form_class = AccountCodeForm
    template_name = 'accounting/accountcode_form.html'
    success_url = reverse_lazy('accounting:accountcode_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class AccountCodeUpdateView(ManagerRequiredMixin, UpdateView):
    model = AccountCode
    form_class = AccountCodeForm
    template_name = 'accounting/accountcode_form.html'
    success_url = reverse_lazy('accounting:accountcode_list')


# === 전표 ===
class VoucherListView(ManagerRequiredMixin, ListView):
    model = Voucher
    template_name = 'accounting/voucher_list.html'
    context_object_name = 'vouchers'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'approved_by',
        )
        voucher_type = self.request.GET.get('type')
        status = self.request.GET.get('status')
        if voucher_type:
            qs = qs.filter(voucher_type=voucher_type)
        if status:
            qs = qs.filter(approval_status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['type_choices'] = Voucher.VoucherType.choices
        ctx['status_choices'] = Voucher.ApprovalStatus.choices
        return ctx


class VoucherCreateView(ManagerRequiredMixin, CreateView):
    model = Voucher
    form_class = VoucherForm
    template_name = 'accounting/voucher_form.html'
    success_url = reverse_lazy('accounting:voucher_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = VoucherLineFormSet(self.request.POST)
        else:
            ctx['formset'] = VoucherLineFormSet()
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save(commit=False)
            self.object.created_by = self.request.user
            self.object.save()
            formset.instance = self.object
            formset.save()
            return redirect(self.get_success_url())
        return self.form_invalid(form)


class VoucherDetailView(ManagerRequiredMixin, DetailView):
    model = Voucher
    template_name = 'accounting/voucher_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['lines'] = self.object.lines.select_related(
            'account',
        ).all()
        return ctx


class VoucherUpdateView(ManagerRequiredMixin, UpdateView):
    model = Voucher
    form_class = VoucherForm
    template_name = 'accounting/voucher_form.html'
    success_url = reverse_lazy('accounting:voucher_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = VoucherLineFormSet(self.request.POST, instance=self.object)
        else:
            ctx['formset'] = VoucherLineFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            return super().form_valid(form)
        return self.form_invalid(form)


# === 결재/품의 ===
class ApprovalListView(ManagerRequiredMixin, ListView):
    model = ApprovalRequest
    template_name = 'accounting/approval_list.html'
    context_object_name = 'approvals'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related(
            'requester', 'approver',
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        tab = self.request.GET.get('tab', 'all')
        if tab == 'my':
            qs = qs.filter(requester=self.request.user)
        elif tab == 'pending':
            qs = qs.filter(
                approver=self.request.user,
                status='SUBMITTED',
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pending_count'] = ApprovalRequest.objects.filter(
            approver=self.request.user, status='SUBMITTED'
        ).count()
        return ctx


class ApprovalCreateView(ManagerRequiredMixin, CreateView):
    model = ApprovalRequest
    form_class = ApprovalRequestForm
    template_name = 'accounting/approval_form.html'
    success_url = reverse_lazy('accounting:approval_list')

    def form_valid(self, form):
        form.instance.requester = self.request.user
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class ApprovalDetailView(ManagerRequiredMixin, DetailView):
    model = ApprovalRequest
    template_name = 'accounting/approval_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'requester', 'approver',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['action_form'] = ApprovalActionForm()
        ctx['steps'] = self.object.steps.select_related('approver').order_by('step_order')
        # Multi-step: check if current user is the approver for the current step
        current_step_obj = self.object.steps.filter(
            step_order=self.object.current_step, status='PENDING'
        ).first()
        ctx['current_step_obj'] = current_step_obj
        ctx['can_approve_step'] = (
            current_step_obj is not None
            and current_step_obj.approver == self.request.user
            and self.object.status == 'SUBMITTED'
        )
        # Legacy single-approver fallback
        ctx['can_approve'] = (
            not self.object.steps.exists()
            and self.object.approver == self.request.user
            and self.object.status == 'SUBMITTED'
        )
        ctx['can_submit'] = (
            self.object.requester == self.request.user
            and self.object.status == 'DRAFT'
        )
        return ctx


class ApprovalSubmitView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        from django.utils import timezone
        obj = get_object_or_404(ApprovalRequest, pk=pk, requester=request.user)
        if obj.status == 'DRAFT':
            obj.status = 'SUBMITTED'
            obj.submitted_at = timezone.now()
            obj.save(update_fields=['status', 'submitted_at', 'updated_at'])
        return HttpResponseRedirect(reverse_lazy('accounting:approval_detail', args=[pk]))


class ApprovalActionView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        from django.utils import timezone
        obj = get_object_or_404(ApprovalRequest, pk=pk, approver=request.user)
        if obj.status != 'SUBMITTED':
            return HttpResponseRedirect(reverse_lazy('accounting:approval_detail', args=[pk]))
        action = request.POST.get('action')
        if action == 'approve':
            obj.status = 'APPROVED'
            obj.approved_at = timezone.now()
        elif action == 'reject':
            obj.status = 'REJECTED'
            obj.reject_reason = request.POST.get('reject_reason', '')
        obj.save()
        return HttpResponseRedirect(reverse_lazy('accounting:approval_detail', args=[pk]))


# === 세금계산서 PDF ===
class TaxInvoicePDFView(ManagerRequiredMixin, DetailView):
    model = TaxInvoice

    def get(self, request, *args, **kwargs):
        invoice = self.get_object()
        from apps.core.pdf import generate_tax_invoice_pdf
        return generate_tax_invoice_pdf(invoice)


# === 미수금 (Accounts Receivable) ===
class ARListView(ManagerRequiredMixin, ListView):
    model = AccountReceivable
    template_name = 'accounting/ar_list.html'
    context_object_name = 'receivables'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('partner', 'order')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        partner_id = self.request.GET.get('partner')
        if partner_id:
            qs = qs.filter(partner_id=partner_id)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(partner__name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = AccountReceivable.Status.choices
        from apps.sales.models import Partner
        ctx['partners'] = Partner.objects.filter(is_active=True)
        total = AccountReceivable.objects.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE']
        ).aggregate(total=Sum('amount'), paid=Sum('paid_amount'))
        ctx['total_remaining'] = (total['total'] or 0) - (total['paid'] or 0)
        return ctx


class ARDetailView(ManagerRequiredMixin, DetailView):
    model = AccountReceivable
    template_name = 'accounting/ar_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'partner', 'order',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['payments'] = (
            self.object.payments
            .select_related('partner')
            .order_by('-payment_date')
        )
        return ctx


class ARCreateView(ManagerRequiredMixin, CreateView):
    model = AccountReceivable
    form_class = AccountReceivableForm
    template_name = 'accounting/ar_form.html'
    success_url = reverse_lazy('accounting:ar_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class PaymentCreateView(ManagerRequiredMixin, CreateView):
    """입금 등록 - AR에 대한 결제"""
    model = Payment
    form_class = PaymentForm
    template_name = 'accounting/payment_form.html'

    def get_initial(self):
        initial = super().get_initial()
        ar = AccountReceivable.objects.filter(pk=self.kwargs['pk']).first()
        if ar:
            initial['partner'] = ar.partner_id
            initial['payment_type'] = 'RECEIPT'
            initial['amount'] = ar.remaining_amount
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['receivable'] = get_object_or_404(AccountReceivable, pk=self.kwargs['pk'])
        ctx['is_receipt'] = True
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            ar = AccountReceivable.objects.select_for_update().get(pk=self.kwargs['pk'])
            amount = form.cleaned_data['amount']
            if amount > ar.remaining_amount:
                form.add_error('amount', f'잔액({ar.remaining_amount:,}원)을 초과할 수 없습니다.')
                return self.form_invalid(form)

            payment = form.save(commit=False)
            payment.receivable = ar
            payment.partner = ar.partner
            payment.payment_type = 'RECEIPT'
            payment.created_by = self.request.user
            payment.save()

            ar.paid_amount = F('paid_amount') + amount
            ar.save(update_fields=['paid_amount', 'updated_at'])
            ar.refresh_from_db()

            if ar.paid_amount >= ar.amount:
                ar.status = 'PAID'
            elif ar.paid_amount > 0:
                ar.status = 'PARTIAL'
            ar.save(update_fields=['status', 'updated_at'])

        messages.success(self.request, f'{amount:,}원 입금 처리 완료')
        return redirect('accounting:ar_detail', pk=ar.pk)

    def get_success_url(self):
        return reverse_lazy('accounting:ar_detail', args=[self.kwargs['pk']])


# === 미지급금 (Accounts Payable) ===
class APListView(ManagerRequiredMixin, ListView):
    model = AccountPayable
    template_name = 'accounting/ap_list.html'
    context_object_name = 'payables'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('partner')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        partner_id = self.request.GET.get('partner')
        if partner_id:
            qs = qs.filter(partner_id=partner_id)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(partner__name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = AccountPayable.Status.choices
        from apps.sales.models import Partner
        ctx['partners'] = Partner.objects.filter(is_active=True)
        total = AccountPayable.objects.filter(
            status__in=['PENDING', 'PARTIAL', 'OVERDUE']
        ).aggregate(total=Sum('amount'), paid=Sum('paid_amount'))
        ctx['total_remaining'] = (total['total'] or 0) - (total['paid'] or 0)
        return ctx


class APDetailView(ManagerRequiredMixin, DetailView):
    model = AccountPayable
    template_name = 'accounting/ap_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'partner',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['payments'] = (
            self.object.payments
            .select_related('partner')
            .order_by('-payment_date')
        )
        return ctx


class APCreateView(ManagerRequiredMixin, CreateView):
    model = AccountPayable
    form_class = AccountPayableForm
    template_name = 'accounting/ap_form.html'
    success_url = reverse_lazy('accounting:ap_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class DisbursementCreateView(ManagerRequiredMixin, CreateView):
    """출금 등록 - AP에 대한 결제"""
    model = Payment
    form_class = PaymentForm
    template_name = 'accounting/payment_form.html'

    def get_initial(self):
        initial = super().get_initial()
        ap = AccountPayable.objects.filter(pk=self.kwargs['pk']).first()
        if ap:
            initial['partner'] = ap.partner_id
            initial['payment_type'] = 'DISBURSEMENT'
            initial['amount'] = ap.remaining_amount
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['payable'] = get_object_or_404(AccountPayable, pk=self.kwargs['pk'])
        ctx['is_receipt'] = False
        return ctx

    def form_valid(self, form):
        with transaction.atomic():
            ap = AccountPayable.objects.select_for_update().get(pk=self.kwargs['pk'])
            amount = form.cleaned_data['amount']
            if amount > ap.remaining_amount:
                form.add_error('amount', f'잔액({ap.remaining_amount:,}원)을 초과할 수 없습니다.')
                return self.form_invalid(form)

            payment = form.save(commit=False)
            payment.payable = ap
            payment.partner = ap.partner
            payment.payment_type = 'DISBURSEMENT'
            payment.created_by = self.request.user
            payment.save()

            ap.paid_amount = F('paid_amount') + amount
            ap.save(update_fields=['paid_amount', 'updated_at'])
            ap.refresh_from_db()

            if ap.paid_amount >= ap.amount:
                ap.status = 'PAID'
            elif ap.paid_amount > 0:
                ap.status = 'PARTIAL'
            ap.save(update_fields=['status', 'updated_at'])

        messages.success(self.request, f'{amount:,}원 출금 처리 완료')
        return redirect('accounting:ap_detail', pk=ap.pk)

    def get_success_url(self):
        return reverse_lazy('accounting:ap_detail', args=[self.kwargs['pk']])


# === 다단계 결재 처리 ===
class ApprovalStepActionView(ManagerRequiredMixin, View):
    """결재 단계별 승인/반려 처리"""
    def post(self, request, pk, step_pk):
        from django.utils import timezone
        from django.shortcuts import get_object_or_404

        approval = get_object_or_404(ApprovalRequest, pk=pk)
        step = get_object_or_404(
            ApprovalStep, pk=step_pk, request=approval, approver=request.user,
        )

        if approval.status != 'SUBMITTED' or step.status != 'PENDING':
            return HttpResponseRedirect(reverse_lazy('accounting:approval_detail', args=[pk]))

        if step.step_order != approval.current_step:
            return HttpResponseRedirect(reverse_lazy('accounting:approval_detail', args=[pk]))

        action = request.POST.get('action')
        comment = request.POST.get('comment', '')

        step.comment = comment
        step.acted_at = timezone.now()

        if action == 'approve':
            step.status = 'APPROVED'
            step.save()
            # Check if there's a next step
            next_step = approval.steps.filter(step_order__gt=step.step_order).order_by('step_order').first()
            if next_step:
                approval.current_step = next_step.step_order
                approval.save(update_fields=['current_step', 'updated_at'])
            else:
                # All steps approved
                approval.status = 'APPROVED'
                approval.approved_at = timezone.now()
                approval.save(update_fields=['status', 'approved_at', 'updated_at'])
        elif action == 'reject':
            step.status = 'REJECTED'
            step.save()
            approval.status = 'REJECTED'
            approval.reject_reason = comment
            approval.save(update_fields=['status', 'reject_reason', 'updated_at'])

        return HttpResponseRedirect(reverse_lazy('accounting:approval_detail', args=[pk]))
