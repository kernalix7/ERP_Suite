import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from apps.core.import_views import BaseImportView
from apps.core.mixins import AdminRequiredMixin, ManagerRequiredMixin
from django.db.models import F, Q, Sum
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
    Currency, ExchangeRate,
    TaxRate, TaxInvoice, FixedCost, WithholdingTax, AccountCode, Voucher, VoucherLine,
    AccountReceivable, AccountPayable, Payment, BankAccount,
    AccountTransfer, PaymentDistribution,
    CostSettlement, CostSettlementItem,
    SalesSettlement, SalesSettlementOrder,
    Budget, ClosingPeriod,
)
from .forms import (
    CurrencyForm, ExchangeRateForm,
    TaxRateForm, TaxInvoiceForm, FixedCostForm, WithholdingTaxForm,
    AccountCodeForm, VoucherForm, VoucherLineFormSet,
    AccountReceivableForm, AccountPayableForm, PaymentForm, BankAccountForm,
    AccountTransferForm, PaymentDistributionFormSet,
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

        ctx['months_json'] = months
        ctx['revenue_json'] = monthly_revenue
        ctx['costs_json'] = monthly_costs

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
        ctx['product_margins_json'] = product_margins

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
    paginate_by = 20

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

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['invoice_number'] = generate_document_number(TaxInvoice, 'invoice_number', 'TI')
        return initial

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


# === 결제계좌 ===

class BankAccountListView(ManagerRequiredMixin, ListView):
    model = BankAccount
    template_name = 'accounting/bankaccount_list.html'
    context_object_name = 'accounts'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class BankAccountCreateView(ManagerRequiredMixin, CreateView):
    model = BankAccount
    form_class = BankAccountForm
    template_name = 'accounting/bankaccount_form.html'
    success_url = reverse_lazy('accounting:bankaccount_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class BankAccountUpdateView(ManagerRequiredMixin, UpdateView):
    model = BankAccount
    form_class = BankAccountForm
    template_name = 'accounting/bankaccount_form.html'
    success_url = reverse_lazy('accounting:bankaccount_list')


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
        from apps.production.models import BOM
        products = Product.objects.filter(product_type='FINISHED', unit_price__gt=0)
        # BOM 일괄 조회 (N+1 방지)
        default_boms = {
            b.product_id: b
            for b in BOM.objects.filter(
                product__in=products, is_default=True,
            ).select_related('product').prefetch_related('items__material')
        }
        breakeven_data = []
        for p in products:
            # 변동비 = BOM 원가 (자재 원가)
            bom = default_boms.get(p.pk)
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
        ctx['breakeven_json'] = breakeven_data
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
                is_active=True,
                order_date__year=year, order_date__month=m,
                status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED'],
            ).aggregate(total=Sum('total_amount'))['total'] or 0

            # 매출원가 (판매된 제품의 원가)
            cogs_items = OrderItem.objects.filter(
                is_active=True,
                order__is_active=True,
                order__order_date__year=year, order__order_date__month=m,
                order__status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED'],
            ).select_related('product')
            cogs = int(sum(
                item.quantity * (
                    item.cost_price
                    if item.cost_price
                    else item.product.cost_price
                )
                for item in cogs_items
            ))

            gross_profit = int(revenue) - cogs

            # 고정비
            fixed = FixedCost.objects.filter(
                is_active=True,
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
        ctx['monthly_json'] = monthly_data

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
    paginate_by = 20

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

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['voucher_number'] = generate_document_number(Voucher, 'voucher_number', 'VC')
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = VoucherLineFormSet(self.request.POST)
        else:
            ctx['formset'] = VoucherLineFormSet()
        return ctx

    def form_valid(self, form):
        voucher_date = form.cleaned_data.get('voucher_date')
        if voucher_date:
            closed = ClosingPeriod.objects.filter(
                year=voucher_date.year,
                month=voucher_date.month,
                is_closed=True,
                is_active=True,
            ).exists()
            if closed:
                messages.error(
                    self.request,
                    f'{voucher_date.year}년 {voucher_date.month}월은 결산 마감되어 전표를 생성할 수 없습니다.',
                )
                return self.form_invalid(form)

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
        voucher_date = form.cleaned_data.get('voucher_date')
        if voucher_date:
            closed = ClosingPeriod.objects.filter(
                year=voucher_date.year,
                month=voucher_date.month,
                is_closed=True,
                is_active=True,
            ).exists()
            if closed:
                messages.error(
                    self.request,
                    f'{voucher_date.year}년 {voucher_date.month}월은 결산 마감되어 전표를 수정할 수 없습니다.',
                )
                return self.form_invalid(form)

        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            self.object = form.save()
            formset.instance = self.object
            formset.save()
            return super().form_valid(form)
        return self.form_invalid(form)


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
        # 자동 연체 전환: due_date가 지난 미완납 AR을 OVERDUE로 갱신
        today = date.today()
        AccountReceivable.objects.filter(
            is_active=True,
            due_date__lt=today,
            status__in=['PENDING', 'PARTIAL'],
        ).update(status='OVERDUE')

        qs = super().get_queryset().filter(is_active=True).select_related('partner', 'order')
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
        from apps.core.utils import generate_document_number
        initial['payment_number'] = generate_document_number(Payment, 'payment_number', 'PM')
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
        # 자동 연체 전환: due_date가 지난 미완납 AP를 OVERDUE로 갱신
        today = date.today()
        AccountPayable.objects.filter(
            is_active=True,
            due_date__lt=today,
            status__in=['PENDING', 'PARTIAL'],
        ).update(status='OVERDUE')

        qs = super().get_queryset().filter(is_active=True).select_related('partner')
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
        from apps.core.utils import generate_document_number
        initial['payment_number'] = generate_document_number(Payment, 'payment_number', 'PM')
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


# === 계좌 상세 ===
class BankAccountDetailView(ManagerRequiredMixin, DetailView):
    model = BankAccount
    template_name = 'accounting/bankaccount_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('account_code')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        account = self.object
        ctx['payments'] = Payment.objects.filter(
            bank_account=account, is_active=True,
        ).select_related('partner').order_by('-payment_date')[:20]
        ctx['transfers'] = AccountTransfer.objects.filter(
            Q(from_account=account) | Q(to_account=account),
            is_active=True,
        ).select_related('from_account', 'to_account').order_by('-transfer_date')[:20]
        ctx['distributions'] = PaymentDistribution.objects.filter(
            bank_account=account, is_active=True,
        ).select_related('payment').order_by('-pk')[:20]
        return ctx


# === 계좌 대시보드 ===
class BankAccountDashboardView(ManagerRequiredMixin, TemplateView):
    template_name = 'accounting/bankaccount_dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        accounts = BankAccount.objects.filter(is_active=True)
        ctx['accounts'] = accounts
        ctx['total_balance'] = accounts.aggregate(
            total=Sum('balance'),
        )['total'] or 0
        return ctx


# === 계좌이체 ===
class AccountTransferListView(ManagerRequiredMixin, ListView):
    model = AccountTransfer
    template_name = 'accounting/transfer_list.html'
    context_object_name = 'transfers'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(
            is_active=True,
        ).select_related('from_account', 'to_account')


class AccountTransferCreateView(ManagerRequiredMixin, CreateView):
    model = AccountTransfer
    form_class = AccountTransferForm
    template_name = 'accounting/transfer_form.html'
    success_url = reverse_lazy('accounting:transfer_list')

    def get_initial(self):
        initial = super().get_initial()
        from apps.core.utils import generate_document_number
        initial['transfer_number'] = generate_document_number(
            AccountTransfer, 'transfer_number', 'BT'
        )
        initial['transfer_date'] = date.today()
        return initial

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


# === 결제 분배 ===
class PaymentDistributeView(ManagerRequiredMixin, DetailView):
    model = Payment
    template_name = 'accounting/payment_distribute.html'

    def get_queryset(self):
        return super().get_queryset().select_related('partner', 'bank_account')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = PaymentDistributionFormSet(
                self.request.POST, instance=self.object,
            )
        else:
            ctx['formset'] = PaymentDistributionFormSet(instance=self.object)
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        ctx = self.get_context_data()
        formset = ctx['formset']
        if formset.is_valid():
            with transaction.atomic():
                distributions = formset.save(commit=False)
                for dist in distributions:
                    dist.created_by = request.user
                    dist.save()
                for obj in formset.deleted_objects:
                    obj.delete()
            messages.success(request, '결제 분배가 저장되었습니다.')
            return redirect('accounting:payment_distribute', pk=self.object.pk)
        return self.render_to_response(ctx)


# ── 일괄 가져오기 ──

class FixedCostImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '고정비 일괄 가져오기'
        ctx['cancel_url'] = reverse_lazy('accounting:fixedcost_list')
        ctx['sample_url'] = reverse_lazy('accounting:fixedcost_import_sample')
        ctx['field_hints'] = [
            'category: RENT(임대료), LABOR(인건비), EQUIPMENT(장비), '
            'INSURANCE(보험), TELECOM(통신비), SUBSCRIPTION(구독), OTHER(기타)',
            'month: YYYY-MM-DD 형식 (해당월 1일)',
            '동일 (name, month) 조합이 있으면 금액이 수정됩니다.',
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        from apps.core.import_views import parse_import_file, build_preview, collect_errors
        from .resources import FixedCostResource

        action = request.POST.get('action', 'preview')
        import_file = request.FILES.get('import_file')

        if not import_file:
            messages.error(request, '파일을 선택해주세요.')
            return self.get(request, *args, **kwargs)

        resource = FixedCostResource()
        try:
            data = parse_import_file(import_file)
            if data is None:
                messages.error(request, '지원하지 않는 파일 형식입니다.')
                return self.get(request, *args, **kwargs)
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as e:
            messages.error(request, f'파일 읽기 오류: {e}')
            return self.get(request, *args, **kwargs)

        if action == 'preview':
            result = resource.import_data(data, dry_run=True)
            ctx = self.get_context_data(**kwargs)
            ctx['preview'] = build_preview(result, data)
            ctx['errors'] = collect_errors(result)
            return self.render_to_response(ctx)
        else:
            result = resource.import_data(data, dry_run=False)
            if result.has_errors():
                ctx = self.get_context_data(**kwargs)
                ctx['errors'] = collect_errors(result)
                return self.render_to_response(ctx)
            total = result.totals.get('new', 0) + result.totals.get('update', 0)
            messages.success(request, f'고정비 {total}건이 성공적으로 가져오기 되었습니다.')
            return HttpResponseRedirect(reverse_lazy('accounting:fixedcost_list'))


class FixedCostImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('name', 25), ('category', 15), ('amount', 15),
            ('month', 12), ('is_recurring', 10),
        ]
        rows = [
            ['사무실 임대료', 'RENT', 1500000, '2026-03-01', True],
            ['서버 호스팅', 'SUBSCRIPTION', 100000, '2026-03-01', True],
        ]
        return export_to_excel(
            '고정비_가져오기_양식', headers, rows,
            filename='고정비_가져오기_양식.xlsx',
            required_columns=[0, 2, 3],  # name, amount, month
        )


class AccountCodeImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '계정과목 일괄 가져오기'
        ctx['cancel_url'] = reverse_lazy('accounting:accountcode_list')
        ctx['sample_url'] = reverse_lazy(
            'accounting:accountcode_import_sample',
        )
        ctx['field_hints'] = [
            '계정코드(code)가 동일하면 기존 계정이 수정됩니다.',
            'account_type: ASSET(자산), LIABILITY(부채), '
            'EQUITY(자본), REVENUE(수익), EXPENSE(비용)',
            'parent_code: 상위 계정코드 (없으면 비워두기)',
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        from apps.core.import_views import (
            parse_import_file, build_preview, collect_errors,
        )
        from .resources import AccountCodeResource

        action = request.POST.get('action', 'preview')
        import_file = request.FILES.get('import_file')
        if not import_file:
            messages.error(request, '파일을 선택해주세요.')
            return self.get(request, *args, **kwargs)

        resource = AccountCodeResource()
        try:
            data = parse_import_file(import_file)
            if data is None:
                messages.error(request, '지원하지 않는 파일 형식입니다.')
                return self.get(request, *args, **kwargs)
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as e:
            messages.error(request, f'파일 읽기 오류: {e}')
            return self.get(request, *args, **kwargs)

        if action == 'preview':
            result = resource.import_data(data, dry_run=True)
            ctx = self.get_context_data(**kwargs)
            ctx['preview'] = build_preview(result, data)
            ctx['errors'] = collect_errors(result)
            return self.render_to_response(ctx)
        else:
            result = resource.import_data(data, dry_run=False)
            if result.has_errors():
                ctx = self.get_context_data(**kwargs)
                ctx['errors'] = collect_errors(result)
                return self.render_to_response(ctx)
            total = (result.totals.get('new', 0)
                     + result.totals.get('update', 0))
            messages.success(request, f'{total}건 가져오기 완료.')
            return HttpResponseRedirect(
                str(reverse_lazy('accounting:accountcode_list')),
            )


class AccountCodeImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('code', 12), ('name', 25),
            ('account_type', 12), ('parent_code', 12),
        ]
        rows = [
            ['1000', '자산', 'ASSET', ''],
            ['1100', '유동자산', 'ASSET', '1000'],
            ['1110', '현금및현금성자산', 'ASSET', '1100'],
            ['4000', '매출', 'REVENUE', ''],
            ['5000', '매출원가', 'EXPENSE', ''],
        ]
        return export_to_excel(
            '계정과목_가져오기_양식', headers, rows,
            filename='계정과목_가져오기_양식.xlsx',
            required_columns=[0, 1, 2],  # code, name, account_type
        )


class TaxInvoiceImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['page_title'] = '세금계산서 일괄 가져오기'
        ctx['cancel_url'] = reverse_lazy('accounting:taxinvoice_list')
        ctx['sample_url'] = reverse_lazy(
            'accounting:taxinvoice_import_sample',
        )
        ctx['field_hints'] = [
            '세금계산서번호(invoice_number)가 동일하면 수정됩니다.',
            'invoice_type: SALES(매출), PURCHASE(매입)',
            'partner_code: 거래처코드',
            '금액: 숫자만 입력 (원 단위)',
        ]
        return ctx

    def post(self, request, *args, **kwargs):
        from apps.core.import_views import (
            parse_import_file, build_preview, collect_errors,
        )
        from .resources import TaxInvoiceResource

        action = request.POST.get('action', 'preview')
        import_file = request.FILES.get('import_file')
        if not import_file:
            messages.error(request, '파일을 선택해주세요.')
            return self.get(request, *args, **kwargs)

        resource = TaxInvoiceResource()
        try:
            data = parse_import_file(import_file)
            if data is None:
                messages.error(request, '지원하지 않는 파일 형식입니다.')
                return self.get(request, *args, **kwargs)
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as e:
            messages.error(request, f'파일 읽기 오류: {e}')
            return self.get(request, *args, **kwargs)

        if action == 'preview':
            result = resource.import_data(data, dry_run=True)
            ctx = self.get_context_data(**kwargs)
            ctx['preview'] = build_preview(result, data)
            ctx['errors'] = collect_errors(result)
            return self.render_to_response(ctx)
        else:
            result = resource.import_data(data, dry_run=False)
            if result.has_errors():
                ctx = self.get_context_data(**kwargs)
                ctx['errors'] = collect_errors(result)
                return self.render_to_response(ctx)
            total = (result.totals.get('new', 0)
                     + result.totals.get('update', 0))
            messages.success(request, f'{total}건 가져오기 완료.')
            return HttpResponseRedirect(
                str(reverse_lazy('accounting:taxinvoice_list')),
            )


class TaxInvoiceImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('invoice_number', 18), ('invoice_type', 12),
            ('partner_code', 15), ('issue_date', 12),
            ('supply_amount', 15), ('tax_amount', 12),
            ('total_amount', 15), ('description', 25),
        ]
        rows = [
            ['INV-2026-001', 'SALES', 'PTN-001', '2026-03-01',
             1000000, 100000, 1100000, '3월 납품건'],
            ['INV-2026-002', 'PURCHASE', 'PTN-002', '2026-03-05',
             500000, 50000, 550000, '자재 구매'],
        ]
        return export_to_excel(
            '세금계산서_가져오기_양식', headers, rows,
            filename='세금계산서_가져오기_양식.xlsx',
            money_columns=[4, 5, 6],
            required_columns=[0, 1, 3, 4],  # invoice_number, invoice_type, issue_date, supply_amount
        )


# === 전표 일괄 가져오기 ===

class VoucherImportView(BaseImportView):
    resource_class = None
    page_title = '전표 일괄 가져오기'
    cancel_url = reverse_lazy('accounting:voucher_list')
    sample_url = reverse_lazy('accounting:voucher_import_sample')
    field_hints = [
        '전표번호(voucher_number)가 동일하면 기존 전표가 수정됩니다.',
        'voucher_type: RECEIPT(입금), PAYMENT(출금), TRANSFER(대체)',
    ]

    def get_resource(self):
        from .resources import VoucherResource
        return VoucherResource()


class VoucherImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('voucher_number', 18), ('voucher_type', 12),
            ('voucher_date', 12), ('description', 30),
        ]
        rows = [
            ['VCH-2026-001', 'RECEIPT', '2026-03-01', '매출대금 입금'],
            ['VCH-2026-002', 'PAYMENT', '2026-03-05', '원자재 구매'],
        ]
        return export_to_excel(
            '전표_가져오기_양식', headers, rows,
            filename='전표_가져오기_양식.xlsx',
            required_columns=[0, 1, 2, 3],
        )


# === 원천징수 일괄 가져오기 ===

class WithholdingImportView(BaseImportView):
    resource_class = None
    page_title = '원천징수 일괄 가져오기'
    cancel_url = reverse_lazy('accounting:withholding_list')
    sample_url = reverse_lazy('accounting:withholding_import_sample')
    field_hints = [
        '소득자명(payee_name) + 지급일(payment_date) 조합이 동일하면 수정됩니다.',
        'tax_type: INCOME(소득세), CORPORATE(법인세), RESIDENT(주민세)',
    ]

    def get_resource(self):
        from .resources import WithholdingTaxResource
        return WithholdingTaxResource()


class WithholdingImportSampleView(ManagerRequiredMixin, View):
    def get(self, request):
        from apps.core.excel import export_to_excel
        headers = [
            ('tax_type', 12), ('payee_name', 15),
            ('payment_date', 12), ('gross_amount', 15),
            ('tax_rate', 10), ('tax_amount', 15), ('net_amount', 15),
        ]
        rows = [
            ['INCOME', '홍길동', '2026-03-10', 3000000,
             3.3, 99000, 2901000],
        ]
        return export_to_excel(
            '원천징수_가져오기_양식', headers, rows,
            filename='원천징수_가져오기_양식.xlsx',
            money_columns=[3, 5, 6],
            required_columns=[0, 1, 2, 3, 4, 5, 6],
        )


# === 원가 정산 ===

class CostSettlementListView(ManagerRequiredMixin, ListView):
    model = CostSettlement
    template_name = 'accounting/settlement_list.html'
    context_object_name = 'settlements'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class CostSettlementDetailView(ManagerRequiredMixin, DetailView):
    model = CostSettlement
    template_name = 'accounting/settlement_detail.html'
    context_object_name = 'settlement'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = (
            self.object.items
            .select_related('product')
            .order_by('product__code')
        )
        return ctx


class CostSettlementCreateView(ManagerRequiredMixin, TemplateView):
    template_name = 'accounting/settlement_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        # 기본값: 전월
        if today.month == 1:
            default_year, default_month = today.year - 1, 12
        else:
            default_year, default_month = today.year, today.month - 1
        ctx['default_year'] = default_year
        ctx['default_month'] = default_month
        ctx['period_choices'] = CostSettlement.Period.choices
        return ctx

    def post(self, request, *args, **kwargs):
        from calendar import monthrange

        period_type = request.POST.get('period_type', 'MONTHLY')
        year = safe_int(request.POST.get('year'), date.today().year)
        month = safe_int(request.POST.get('month'), date.today().month)

        # 정산 기간 계산
        if period_type == 'MONTHLY':
            period_start = date(year, month, 1)
            _, last_day = monthrange(year, month)
            period_end = date(year, month, last_day)
        elif period_type == 'QUARTERLY':
            q_start_month = ((month - 1) // 3) * 3 + 1
            period_start = date(year, q_start_month, 1)
            q_end_month = q_start_month + 2
            _, last_day = monthrange(year, q_end_month)
            period_end = date(year, q_end_month, last_day)
        else:  # YEARLY
            period_start = date(year, 1, 1)
            period_end = date(year, 12, 31)

        # 중복 검증
        exists = CostSettlement.objects.filter(
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            is_active=True,
        ).exists()
        if exists:
            messages.error(
                request,
                f'해당 기간({period_start}~{period_end}) 정산이 '
                f'이미 존재합니다.',
            )
            return self.get(request, *args, **kwargs)

        with transaction.atomic():
            settlement = CostSettlement.objects.create(
                period_type=period_type,
                period_start=period_start,
                period_end=period_end,
                created_by=request.user,
            )

            products = Product.objects.filter(is_active=True)
            total_value = 0
            items = []
            for p in products:
                value = p.current_stock * (p.cost_price or 0)
                items.append(CostSettlementItem(
                    settlement=settlement,
                    product=p,
                    stock_quantity=p.current_stock,
                    cost_price=p.cost_price or 0,
                    inventory_value=value,
                ))
                total_value += value

            CostSettlementItem.objects.bulk_create(items)
            settlement.total_inventory_value = total_value
            settlement.save(
                update_fields=['total_inventory_value', 'updated_at'],
            )

        messages.success(
            request,
            f'{period_start}~{period_end} 원가정산 완료 '
            f'(총 재고자산: {total_value:,}원)',
        )
        return redirect(
            'accounting:settlement_detail', pk=settlement.pk,
        )


# ===== 매출 정산 =====

class SalesSettlementListView(ManagerRequiredMixin, ListView):
    model = SalesSettlement
    template_name = 'accounting/sales_settlement_list.html'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class SalesSettlementDetailView(ManagerRequiredMixin, DetailView):
    model = SalesSettlement
    template_name = 'accounting/sales_settlement_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'commission_bank_account',
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = (
            self.object.settlement_orders
            .select_related('order__partner', 'order__customer')
            .all()
        )
        # 주문별 입금 상태
        from apps.sales.models import Order
        order_ids = [i.order_id for i in ctx['items']]
        orders = Order.objects.filter(pk__in=order_ids)
        ctx['paid_count'] = orders.filter(is_paid=True).count()
        ctx['unpaid_count'] = orders.filter(is_paid=False).count()
        # 수수료 지급 계좌 목록
        ctx['bank_accounts'] = BankAccount.objects.filter(
            is_active=True,
        )
        # 최근 전표 (수동 지급 시 연결용)
        ctx['recent_vouchers'] = Voucher.objects.filter(
            is_active=True,
        ).order_by('-voucher_date', '-pk')[:20]
        return ctx


class SalesSettlementPaymentView(ManagerRequiredMixin, View):
    """정산 내 미입금 주문 일괄 입금 처리"""

    def post(self, request, pk):
        settlement = get_object_or_404(
            SalesSettlement, pk=pk, is_active=True,
        )
        from apps.sales.signals import _auto_create_payment

        items = settlement.settlement_orders.select_related(
            'order',
        ).all()
        count = 0
        for item in items:
            order = item.order
            if not order.is_paid:
                try:
                    _auto_create_payment(order)
                    count += 1
                except Exception:
                    pass

        if count:
            messages.success(
                request,
                f'{count}건 입금 처리 완료',
            )
        else:
            messages.info(request, '처리할 미입금 주문이 없습니다.')
        return redirect(
            'accounting:sales_settlement_detail', pk=pk,
        )


class SalesSettlementCommissionPayView(ManagerRequiredMixin, View):
    """정산 수수료 지급 처리"""

    def post(self, request, pk):
        settlement = get_object_or_404(
            SalesSettlement, pk=pk, is_active=True,
        )
        if settlement.commission_paid:
            messages.warning(request, '이미 수수료 지급 완료된 정산입니다.')
            return redirect(
                'accounting:sales_settlement_detail', pk=pk,
            )

        bank_id = request.POST.get('commission_bank_account')
        bank = None
        if bank_id:
            bank = BankAccount.objects.filter(
                pk=bank_id, is_active=True,
            ).first()

        commission_total = int(settlement.total_commission)
        if commission_total <= 0:
            messages.info(request, '지급할 수수료가 없습니다.')
            return redirect(
                'accounting:sales_settlement_detail', pk=pk,
            )

        with transaction.atomic():
            # 정산 내 첫 번째 거래처 기준
            first_item = settlement.settlement_orders.select_related(
                'order__partner',
            ).first()
            partner = first_item.order.partner if first_item and first_item.order.partner else None

            # 수수료 지급 전표 생성
            voucher = Voucher.objects.create(
                voucher_type='PAYMENT',
                voucher_date=date.today(),
                description=(
                    f'수수료 지급 - {settlement.settlement_number}'
                ),
                approval_status='APPROVED',
                created_by=request.user,
            )

            acct_payable = AccountCode.objects.filter(
                code='205',
            ).first()  # 미지급금
            acct_deposit = AccountCode.objects.filter(
                code='103',
            ).first()  # 보통예금

            # 차변: 미지급금 (부채 감소)
            if acct_payable:
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=acct_payable,
                    debit=commission_total,
                    credit=0,
                    description=(
                        f'{settlement.settlement_number} 수수료'
                    ),
                )
            # 대변: 보통예금 (자산 감소)
            if acct_deposit:
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=acct_deposit,
                    debit=0,
                    credit=commission_total,
                    description=(
                        f'{bank.name} 출금' if bank
                        else '수수료 지급'
                    ),
                )

            # 출금 기록 (시그널에서 계좌 잔액 자동 차감)
            Payment.objects.create(
                payment_type='DISBURSEMENT',
                partner=partner,
                bank_account=bank,
                voucher=voucher,
                amount=commission_total,
                payment_date=date.today(),
                payment_method='BANK_TRANSFER',
                reference=(
                    f'수수료 {settlement.settlement_number}'
                ),
                created_by=request.user,
            )

            # 미지급금 생성/업데이트
            if first_item and first_item.order.partner:
                ap, created = AccountPayable.objects.get_or_create(
                    partner=first_item.order.partner,
                    notes=f'수수료 {settlement.settlement_number}',
                    defaults={
                        'amount': commission_total,
                        'paid_amount': commission_total,
                        'due_date': date.today(),
                        'status': AccountPayable.Status.PAID,
                        'created_by': request.user,
                    },
                )
                if not created:
                    ap.paid_amount = commission_total
                    ap.status = AccountPayable.Status.PAID
                    ap.save()

            # 정산 수수료 지급 상태 업데이트
            settlement.commission_bank_account = bank
            settlement.commission_paid = True
            settlement.commission_paid_date = date.today()
            settlement.commission_paid_amount = commission_total
            settlement.commission_voucher = voucher
            settlement.save()

        messages.success(
            request,
            f'수수료 {commission_total:,}원 지급 완료',
        )
        return redirect(
            'accounting:sales_settlement_detail', pk=pk,
        )


class SalesSettlementCommissionManualView(ManagerRequiredMixin, View):
    """수수료 수동 지급완료 처리 (전표/출금 없이 상태만 변경)"""

    def post(self, request, pk):
        settlement = get_object_or_404(
            SalesSettlement, pk=pk, is_active=True,
        )
        if settlement.commission_paid:
            messages.warning(request, '이미 수수료 지급 완료된 정산입니다.')
            return redirect(
                'accounting:sales_settlement_detail', pk=pk,
            )

        commission_total = int(settlement.total_commission)
        memo = request.POST.get('memo', '')
        voucher_id = request.POST.get('voucher')

        settlement.commission_paid = True
        settlement.commission_paid_date = date.today()
        settlement.commission_paid_amount = commission_total
        settlement.commission_memo = memo
        if voucher_id:
            v = Voucher.objects.filter(pk=voucher_id).first()
            if v:
                settlement.commission_voucher = v
        settlement.save()

        messages.success(
            request,
            f'수수료 {commission_total:,}원 수동 지급완료 처리'
            + (f' ({memo})' if memo else ''),
        )
        return redirect(
            'accounting:sales_settlement_detail', pk=pk,
        )


class SalesSettlementCreateView(ManagerRequiredMixin, TemplateView):
    """주문 선택 → 매출 정산 생성"""
    template_name = 'accounting/sales_settlement_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # 미정산 + 입금완료 주문만 표시
        orders = (
            Order.objects.filter(
                is_active=True,
                is_settled=False,
                is_paid=True,
                status__in=['DELIVERED', 'SHIPPED', 'CONFIRMED'],
            )
            .select_related('partner', 'customer')
            .prefetch_related('items__product')
            .order_by('-order_date')
        )
        # 주문별 원가 계산 + 객체에 동적 속성 추가
        order_costs = {}
        for order in orders:
            cost = sum(
                int(i.cost_price or 0) * int(i.quantity)
                for i in order.items.all()
            )
            order_costs[order.pk] = cost
            order.cost_total = cost
        # 수수료율 맵 (partner_id → total rate) — CommissionRate 항목 합산
        from apps.sales.models import Partner
        rates = {}
        for p in Partner.objects.filter(is_active=True):
            r = float(p.total_commission_rate)
            if r > 0:
                rates[p.pk] = r
        ctx['orders'] = orders
        ctx['order_costs'] = json.dumps({str(k): v for k, v in order_costs.items()})
        ctx['commission_rates'] = json.dumps(rates)
        return ctx

    def post(self, request, *args, **kwargs):
        order_ids = request.POST.getlist('orders')
        if not order_ids:
            messages.error(request, '정산할 주문을 선택해주세요.')
            return self.get(request, *args, **kwargs)

        description = request.POST.get('description', '')

        from apps.sales.models import Partner
        rates_map = {}
        for p in Partner.objects.filter(is_active=True):
            r = p.total_commission_rate
            if r > 0:
                rates_map[p.pk] = r

        with transaction.atomic():
            settlement = SalesSettlement.objects.create(
                settlement_date=date.today(),
                description=description,
                created_by=request.user,
            )

            total_revenue = 0
            total_cost = 0
            total_tax = 0
            total_shipping = 0
            total_commission = 0
            total_profit = 0

            orders = Order.objects.filter(
                pk__in=order_ids, is_settled=False,
            ).select_related('partner')

            for order in orders:
                revenue = int(order.total_amount)
                tax = int(order.tax_total)
                shipping = int(order.shipping_cost or 0)
                # 원가 계산
                items = order.items.select_related('product').all()
                cost = sum(
                    int(i.cost_price or 0) * int(i.quantity)
                    for i in items
                )
                # 수수료율: POST에서 개별 입력값 우선, 없으면 기본율
                rate_key = f'rate_{order.pk}'
                rate = request.POST.get(rate_key, '')
                if rate:
                    try:
                        comm_rate = Decimal(rate)
                    except Exception:
                        comm_rate = Decimal('0')
                else:
                    comm_rate = rates_map.get(
                        order.partner_id, Decimal('0'),
                    )
                # 수수료 = (공급가액 - 원가) × 수수료율
                margin = revenue - cost
                commission = round(margin * comm_rate / 100)
                profit = margin - shipping - commission

                SalesSettlementOrder.objects.create(
                    settlement=settlement,
                    order=order,
                    revenue=revenue,
                    cost=cost,
                    tax=tax,
                    shipping=shipping,
                    commission_rate=comm_rate,
                    commission=commission,
                    profit=profit,
                    created_by=request.user,
                )

                total_revenue += revenue
                total_cost += cost
                total_tax += tax
                total_shipping += shipping
                total_commission += commission
                total_profit += profit

            settlement.total_revenue = total_revenue
            settlement.total_cost = total_cost
            settlement.total_tax = total_tax
            settlement.total_shipping = total_shipping
            settlement.total_commission = total_commission
            settlement.total_profit = total_profit
            settlement.save(update_fields=[
                'total_revenue', 'total_cost', 'total_tax',
                'total_shipping', 'total_commission',
                'total_profit', 'updated_at',
            ])

            # 주문 정산완료 마킹
            orders.update(is_settled=True)

        messages.success(
            request,
            f'매출정산 {settlement.settlement_number} 완료 '
            f'({orders.count()}건, 이익: {total_profit:,}원)',
        )
        return redirect(
            'accounting:sales_settlement_detail',
            pk=settlement.pk,
        )


# === 은행 대사 ===
class BankReconciliationView(ManagerRequiredMixin, TemplateView):
    """은행 대사 — 시스템 잔액 vs 실제 통장 잔액 비교"""
    template_name = 'accounting/bank_reconciliation.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        accounts = BankAccount.objects.filter(is_active=True)
        recon_data = []
        total_system = 0
        total_actual = 0
        for acct in accounts:
            system_balance = int(acct.balance)
            total_system += system_balance
            # 입출금 건수
            receipt_count = Payment.objects.filter(
                bank_account=acct, payment_type='RECEIPT', is_active=True,
            ).count()
            disbursement_count = Payment.objects.filter(
                bank_account=acct, payment_type='DISBURSEMENT', is_active=True,
            ).count()
            recon_data.append({
                'pk': acct.pk,
                'name': acct.name,
                'bank_name': acct.bank,
                'account_number': acct.account_number,
                'system_balance': system_balance,
                'receipt_count': receipt_count,
                'disbursement_count': disbursement_count,
            })
        ctx['recon_data'] = recon_data
        ctx['total_system'] = total_system
        ctx['recon_date'] = date.today().isoformat()
        return ctx


# === 계정별 원장 ===
class AccountLedgerView(ManagerRequiredMixin, TemplateView):
    """계정별 원장 조회 — 특정 계정과목의 전표 라인을 시간순 표시 + 잔액 누적"""
    template_name = 'accounting/account_ledger.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        account_id = self.request.GET.get('account')
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')

        ctx['accounts'] = AccountCode.objects.filter(is_active=True).order_by('code')
        ctx['selected_account'] = account_id
        ctx['date_from'] = date_from
        ctx['date_to'] = date_to

        if not account_id:
            ctx['lines'] = []
            return ctx

        account = get_object_or_404(AccountCode, pk=account_id)
        ctx['account'] = account

        qs = VoucherLine.objects.filter(
            account=account, is_active=True,
            voucher__is_active=True,
            voucher__approval_status='APPROVED',
        ).select_related('voucher').order_by('voucher__voucher_date', 'pk')

        if date_from:
            qs = qs.filter(voucher__voucher_date__gte=date_from)
        if date_to:
            qs = qs.filter(voucher__voucher_date__lte=date_to)

        # 잔액 누적 계산
        lines = []
        running_balance = 0
        total_debit = 0
        total_credit = 0
        for line in qs:
            debit = int(line.debit)
            credit = int(line.credit)
            # 자산/비용: 차변 증가, 대변 감소
            # 부채/자본/수익: 대변 증가, 차변 감소
            if account.account_type in ('ASSET', 'EXPENSE'):
                running_balance += debit - credit
            else:
                running_balance += credit - debit
            total_debit += debit
            total_credit += credit
            lines.append({
                'date': line.voucher.voucher_date,
                'voucher_number': line.voucher.voucher_number,
                'voucher_pk': line.voucher.pk,
                'voucher_type': line.voucher.get_voucher_type_display(),
                'description': line.description or line.voucher.description,
                'debit': debit,
                'credit': credit,
                'balance': running_balance,
            })

        ctx['lines'] = lines
        ctx['total_debit'] = total_debit
        ctx['total_credit'] = total_credit
        ctx['closing_balance'] = running_balance
        return ctx


# === 시산표 ===
class TrialBalanceView(ManagerRequiredMixin, TemplateView):
    """시산표 — 모든 계정과목의 차변/대변 합계 + 잔액"""
    template_name = 'accounting/trial_balance.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        date_from = self.request.GET.get('date_from', '')
        date_to = self.request.GET.get('date_to', '')
        ctx['date_from'] = date_from
        ctx['date_to'] = date_to

        qs = VoucherLine.objects.filter(
            is_active=True, voucher__is_active=True,
            voucher__approval_status='APPROVED',
        )
        if date_from:
            qs = qs.filter(voucher__voucher_date__gte=date_from)
        if date_to:
            qs = qs.filter(voucher__voucher_date__lte=date_to)

        account_totals = qs.values(
            'account__pk', 'account__code', 'account__name', 'account__account_type',
        ).annotate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit'),
        ).order_by('account__code')

        rows = []
        grand_debit = 0
        grand_credit = 0
        for row in account_totals:
            debit = int(row['total_debit'] or 0)
            credit = int(row['total_credit'] or 0)
            acct_type = row['account__account_type']
            if acct_type in ('ASSET', 'EXPENSE'):
                balance = debit - credit
            else:
                balance = credit - debit
            grand_debit += debit
            grand_credit += credit
            rows.append({
                'pk': row['account__pk'],
                'code': row['account__code'],
                'name': row['account__name'],
                'account_type': acct_type,
                'debit': debit,
                'credit': credit,
                'balance': balance,
            })

        ctx['rows'] = rows
        ctx['grand_debit'] = grand_debit
        ctx['grand_credit'] = grand_credit
        ctx['is_balanced'] = grand_debit == grand_credit
        return ctx


# === 예산 관리 ===
class BudgetListView(ManagerRequiredMixin, TemplateView):
    """예산 vs 실적 대비표"""
    template_name = 'accounting/budget_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        year = safe_int(self.request.GET.get('year'), date.today().year)
        month = safe_int(self.request.GET.get('month'), date.today().month)

        ctx['year'] = year
        ctx['month'] = month
        ctx['years'] = range(date.today().year - 2, date.today().year + 2)
        ctx['months'] = range(1, 13)

        budgets = Budget.objects.filter(
            year=year, month=month, is_active=True,
        ).select_related('account').order_by('account__code')

        # 해당 월의 VoucherLine 실적을 한 번에 배치 조회
        period_start = date(year, month, 1)
        if month == 12:
            period_end = date(year + 1, 1, 1)
        else:
            period_end = date(year, month + 1, 1)

        actuals_qs = VoucherLine.objects.filter(
            is_active=True,
            voucher__is_active=True,
            voucher__voucher_date__gte=period_start,
            voucher__voucher_date__lt=period_end,
        ).values('account_id').annotate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit'),
        )
        actuals_map = {
            row['account_id']: (
                int(row['total_debit'] or 0),
                int(row['total_credit'] or 0),
            )
            for row in actuals_qs
        }

        rows = []
        total_budget = 0
        total_actual = 0
        for b in budgets:
            debit, credit = actuals_map.get(b.account_id, (0, 0))
            if b.account.account_type == 'EXPENSE':
                actual = debit
            elif b.account.account_type == 'REVENUE':
                actual = credit
            else:
                actual = debit - credit
            budget_amt = int(b.budget_amount)
            variance = budget_amt - actual
            rate = (
                round(actual / budget_amt * 100, 1)
                if budget_amt > 0 else 0
            )
            total_budget += budget_amt
            total_actual += actual
            rows.append({
                'pk': b.pk,
                'code': b.account.code,
                'name': b.account.name,
                'account_type': b.account.get_account_type_display(),
                'budget': budget_amt,
                'actual': actual,
                'variance': variance,
                'rate': rate,
            })

        ctx['rows'] = rows
        ctx['total_budget'] = total_budget
        ctx['total_actual'] = total_actual
        ctx['total_variance'] = total_budget - total_actual
        return ctx


class BudgetCreateView(ManagerRequiredMixin, View):
    """예산 등록 (POST)"""
    def get(self, request):
        ctx = {
            'accounts': AccountCode.objects.filter(
                is_active=True, account_type__in=['EXPENSE', 'REVENUE'],
            ).order_by('code'),
            'year': date.today().year,
            'month': date.today().month,
        }
        from django.shortcuts import render
        return render(request, 'accounting/budget_form.html', ctx)

    def post(self, request):
        account_id = request.POST.get('account')
        year = safe_int(request.POST.get('year'), date.today().year)
        month = safe_int(request.POST.get('month'), date.today().month)
        amount = safe_int(request.POST.get('budget_amount'), 0)
        desc = request.POST.get('description', '')

        if not account_id or amount <= 0:
            messages.error(request, '계정과목과 예산액을 입력해주세요.')
            return redirect('accounting:budget_create')

        account = get_object_or_404(AccountCode, pk=account_id)

        budget, created = Budget.objects.update_or_create(
            account=account, year=year, month=month,
            defaults={
                'budget_amount': amount,
                'description': desc,
                'created_by': request.user,
                'is_active': True,
            },
        )
        action = '등록' if created else '수정'
        messages.success(
            request,
            f'{year}년 {month}월 {account.name} 예산 {amount:,}원 {action}',
        )
        return redirect(
            f'/accounting/budget/?year={year}&month={month}',
        )


# === AR/AP Aging 분석 ===

class ARAgingView(ManagerRequiredMixin, TemplateView):
    """미수금 Aging 분석 (30/60/90/120일 이상 구간별)"""
    template_name = 'accounting/ar_aging.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()

        # 자동 연체 전환
        AccountReceivable.objects.filter(
            is_active=True,
            due_date__lt=today,
            status__in=['PENDING', 'PARTIAL'],
        ).update(status='OVERDUE')

        # 미완납 AR만 대상
        ar_qs = AccountReceivable.objects.filter(
            is_active=True,
            status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
        ).select_related('partner', 'order')

        buckets = {
            'current': {'label': '미도래', 'items': [], 'total': 0},
            'over_30': {'label': '30일 이내', 'items': [], 'total': 0},
            'over_60': {'label': '31~60일', 'items': [], 'total': 0},
            'over_90': {'label': '61~90일', 'items': [], 'total': 0},
            'over_120': {'label': '91~120일', 'items': [], 'total': 0},
            'over_120_plus': {'label': '120일 초과', 'items': [], 'total': 0},
        }

        grand_total = 0
        for ar in ar_qs:
            remaining = int(ar.amount) - int(ar.paid_amount)
            if remaining <= 0:
                continue
            days_overdue = (today - ar.due_date).days
            grand_total += remaining

            if days_overdue <= 0:
                bucket_key = 'current'
            elif days_overdue <= 30:
                bucket_key = 'over_30'
            elif days_overdue <= 60:
                bucket_key = 'over_60'
            elif days_overdue <= 90:
                bucket_key = 'over_90'
            elif days_overdue <= 120:
                bucket_key = 'over_120'
            else:
                bucket_key = 'over_120_plus'

            buckets[bucket_key]['items'].append({
                'ar': ar,
                'remaining': remaining,
                'days_overdue': max(days_overdue, 0),
            })
            buckets[bucket_key]['total'] += remaining

        ctx['buckets'] = buckets
        ctx['grand_total'] = grand_total
        ctx['today'] = today

        # 거래처별 집계
        partner_summary = {}
        for bucket_key, bucket_data in buckets.items():
            for item in bucket_data['items']:
                partner_name = item['ar'].partner.name
                if partner_name not in partner_summary:
                    partner_summary[partner_name] = {
                        'name': partner_name,
                        'current': 0, 'over_30': 0, 'over_60': 0,
                        'over_90': 0, 'over_120': 0, 'over_120_plus': 0,
                        'total': 0,
                    }
                partner_summary[partner_name][bucket_key] += item['remaining']
                partner_summary[partner_name]['total'] += item['remaining']

        ctx['partner_summary'] = sorted(
            partner_summary.values(), key=lambda x: -x['total'],
        )
        return ctx


class APAgingView(ManagerRequiredMixin, TemplateView):
    """미지급금 Aging 분석 (30/60/90/120일 이상 구간별)"""
    template_name = 'accounting/ap_aging.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()

        # 자동 연체 전환
        AccountPayable.objects.filter(
            is_active=True,
            due_date__lt=today,
            status__in=['PENDING', 'PARTIAL'],
        ).update(status='OVERDUE')

        # 미완납 AP만 대상
        ap_qs = AccountPayable.objects.filter(
            is_active=True,
            status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
        ).select_related('partner')

        buckets = {
            'current': {'label': '미도래', 'items': [], 'total': 0},
            'over_30': {'label': '30일 이내', 'items': [], 'total': 0},
            'over_60': {'label': '31~60일', 'items': [], 'total': 0},
            'over_90': {'label': '61~90일', 'items': [], 'total': 0},
            'over_120': {'label': '91~120일', 'items': [], 'total': 0},
            'over_120_plus': {'label': '120일 초과', 'items': [], 'total': 0},
        }

        grand_total = 0
        for ap in ap_qs:
            remaining = int(ap.amount) - int(ap.paid_amount)
            if remaining <= 0:
                continue
            days_overdue = (today - ap.due_date).days
            grand_total += remaining

            if days_overdue <= 0:
                bucket_key = 'current'
            elif days_overdue <= 30:
                bucket_key = 'over_30'
            elif days_overdue <= 60:
                bucket_key = 'over_60'
            elif days_overdue <= 90:
                bucket_key = 'over_90'
            elif days_overdue <= 120:
                bucket_key = 'over_120'
            else:
                bucket_key = 'over_120_plus'

            buckets[bucket_key]['items'].append({
                'ap': ap,
                'remaining': remaining,
                'days_overdue': max(days_overdue, 0),
            })
            buckets[bucket_key]['total'] += remaining

        ctx['buckets'] = buckets
        ctx['grand_total'] = grand_total
        ctx['today'] = today

        # 거래처별 집계
        partner_summary = {}
        for bucket_key, bucket_data in buckets.items():
            for item in bucket_data['items']:
                partner_name = item['ap'].partner.name
                if partner_name not in partner_summary:
                    partner_summary[partner_name] = {
                        'name': partner_name,
                        'current': 0, 'over_30': 0, 'over_60': 0,
                        'over_90': 0, 'over_120': 0, 'over_120_plus': 0,
                        'total': 0,
                    }
                partner_summary[partner_name][bucket_key] += item['remaining']
                partner_summary[partner_name]['total'] += item['remaining']

        ctx['partner_summary'] = sorted(
            partner_summary.values(), key=lambda x: -x['total'],
        )
        return ctx


# === 결산 마감 ===

class ClosingPeriodListView(ManagerRequiredMixin, TemplateView):
    """결산 마감 현황"""
    template_name = 'accounting/closing_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        year = safe_int(self.request.GET.get('year'), date.today().year)
        ctx['year'] = year
        ctx['years'] = range(date.today().year - 2, date.today().year + 2)

        # 1~12월 결산 현황
        existing = {
            cp.month: cp
            for cp in ClosingPeriod.objects.filter(
                year=year, is_active=True,
            ).select_related('closed_by')
        }

        periods = []
        for m in range(1, 13):
            cp = existing.get(m)
            voucher_count = Voucher.objects.filter(
                voucher_date__year=year,
                voucher_date__month=m,
                is_active=True,
            ).count()
            periods.append({
                'month': m,
                'closing': cp,
                'is_closed': cp.is_closed if cp else False,
                'closed_at': cp.closed_at if cp else None,
                'closed_by': cp.closed_by if cp else None,
                'pk': cp.pk if cp else None,
                'voucher_count': voucher_count,
            })

        ctx['periods'] = periods
        return ctx


class ClosingPeriodCloseView(AdminRequiredMixin, View):
    """결산 마감/해제 실행 (POST)"""

    def post(self, request, year, month):
        from django.utils import timezone

        if month < 1 or month > 12:
            messages.error(request, '잘못된 월입니다.')
            return redirect(f'/accounting/closing/?year={year}')

        cp, created = ClosingPeriod.objects.get_or_create(
            year=year, month=month,
            defaults={
                'created_by': request.user,
                'is_active': True,
            },
        )

        if cp.is_closed:
            # 마감 해제
            cp.is_closed = False
            cp.closed_at = None
            cp.closed_by = None
            cp.save()
            messages.success(request, f'{year}년 {month}월 결산 마감이 해제되었습니다.')
        else:
            # 마감 실행
            cp.is_closed = True
            cp.closed_at = timezone.now()
            cp.closed_by = request.user
            cp.save()
            messages.success(request, f'{year}년 {month}월 결산이 마감되었습니다.')

        return redirect(f'/accounting/closing/?year={year}')


# === 예산 보고서 (연도별 월간 차트) ===

class BudgetReportView(ManagerRequiredMixin, TemplateView):
    """예산 vs 실적 보고서 (연도별 월간 차트)"""
    template_name = 'accounting/budget_report.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        year = safe_int(self.request.GET.get('year'), date.today().year)
        ctx['year'] = year
        ctx['years'] = range(date.today().year - 2, date.today().year + 2)

        # 월별 예산 합계 / 실적 합계
        monthly_budget = []
        monthly_actual = []
        months_label = []

        for m in range(1, 13):
            months_label.append(f'{m}월')

            # 해당 월 예산 합계
            budget_total = Budget.objects.filter(
                year=year, month=m, is_active=True,
            ).aggregate(total=Sum('budget_amount'))['total'] or 0
            monthly_budget.append(int(budget_total))

            # 해당 월 실적 합계 (전표 기반)
            period_start = date(year, m, 1)
            if m == 12:
                period_end = date(year + 1, 1, 1)
            else:
                period_end = date(year, m + 1, 1)

            actuals_qs = VoucherLine.objects.filter(
                is_active=True,
                voucher__is_active=True,
                voucher__voucher_date__gte=period_start,
                voucher__voucher_date__lt=period_end,
            ).aggregate(
                total_debit=Sum('debit'),
                total_credit=Sum('credit'),
            )
            debit = int(actuals_qs['total_debit'] or 0)
            credit = int(actuals_qs['total_credit'] or 0)
            # 비용 위주로 집행 실적 표시 (차변 합계)
            monthly_actual.append(debit)

        ctx['months_label'] = months_label
        ctx['monthly_budget'] = monthly_budget
        ctx['monthly_actual'] = monthly_actual

        # 계정별 연간 예산 vs 실적 상세
        budgets = Budget.objects.filter(
            year=year, is_active=True,
        ).select_related('account').order_by('account__code', 'month')

        # 계정별 연간 합산
        account_map = {}
        for b in budgets:
            key = b.account_id
            if key not in account_map:
                account_map[key] = {
                    'code': b.account.code,
                    'name': b.account.name,
                    'account_type': b.account.get_account_type_display(),
                    'account_type_raw': b.account.account_type,
                    'budget': 0,
                    'actual': 0,
                }
            account_map[key]['budget'] += int(b.budget_amount)

        # 연간 실적 배치 조회
        if account_map:
            period_start = date(year, 1, 1)
            period_end = date(year + 1, 1, 1)
            actuals_qs = VoucherLine.objects.filter(
                is_active=True,
                voucher__is_active=True,
                voucher__voucher_date__gte=period_start,
                voucher__voucher_date__lt=period_end,
                account_id__in=account_map.keys(),
            ).values('account_id').annotate(
                total_debit=Sum('debit'),
                total_credit=Sum('credit'),
            )
            for row in actuals_qs:
                aid = row['account_id']
                if aid in account_map:
                    d = int(row['total_debit'] or 0)
                    c = int(row['total_credit'] or 0)
                    atype = account_map[aid]['account_type_raw']
                    if atype == 'EXPENSE':
                        account_map[aid]['actual'] = d
                    elif atype == 'REVENUE':
                        account_map[aid]['actual'] = c
                    else:
                        account_map[aid]['actual'] = d - c

        rows = []
        total_budget = 0
        total_actual = 0
        for data in sorted(account_map.values(), key=lambda x: x['code']):
            variance = data['budget'] - data['actual']
            rate = round(data['actual'] / data['budget'] * 100, 1) if data['budget'] > 0 else 0
            total_budget += data['budget']
            total_actual += data['actual']
            rows.append({
                'code': data['code'],
                'name': data['name'],
                'account_type': data['account_type'],
                'budget': data['budget'],
                'actual': data['actual'],
                'variance': variance,
                'rate': rate,
            })

        ctx['rows'] = rows
        ctx['total_budget'] = total_budget
        ctx['total_actual'] = total_actual
        ctx['total_variance'] = total_budget - total_actual
        ctx['total_rate'] = round(total_actual / total_budget * 100, 1) if total_budget > 0 else 0

        return ctx


# ── 통화 관리 ──────────────────────────────────────────────


class CurrencyListView(ManagerRequiredMixin, ListView):
    model = Currency
    template_name = 'accounting/currency_list.html'
    context_object_name = 'currencies'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class CurrencyCreateView(ManagerRequiredMixin, CreateView):
    model = Currency
    form_class = CurrencyForm
    template_name = 'accounting/currency_form.html'
    success_url = reverse_lazy('accounting:currency_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class CurrencyUpdateView(ManagerRequiredMixin, UpdateView):
    model = Currency
    form_class = CurrencyForm
    template_name = 'accounting/currency_form.html'
    success_url = reverse_lazy('accounting:currency_list')


# ── 환율 관리 ──────────────────────────────────────────────


class ExchangeRateListView(ManagerRequiredMixin, ListView):
    model = ExchangeRate
    template_name = 'accounting/exchange_rate_list.html'
    context_object_name = 'rates'
    paginate_by = 30

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('currency')
        currency_id = self.request.GET.get('currency')
        if currency_id:
            qs = qs.filter(currency_id=currency_id)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['currencies'] = Currency.objects.filter(
            is_active=True,
        )
        return ctx


class ExchangeRateCreateView(ManagerRequiredMixin, CreateView):
    model = ExchangeRate
    form_class = ExchangeRateForm
    template_name = 'accounting/exchange_rate_form.html'
    success_url = reverse_lazy('accounting:exchangerate_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)
