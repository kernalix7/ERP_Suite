import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
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
    CreditCard, CardTransaction, CardBilling,
)
from .forms import (
    CurrencyForm, ExchangeRateForm,
    TaxRateForm, TaxInvoiceForm, FixedCostForm, WithholdingTaxForm,
    AccountCodeForm, VoucherForm, VoucherLineFormSet,
    AccountReceivableForm, AccountPayableForm, PaymentForm, BankAccountForm,
    AccountTransferForm, PaymentDistributionFormSet,
    CreditCardForm, CardTransactionForm,
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
        monthly_fixed = []
        monthly_variable = []
        monthly_purchases = []
        months = []
        for m in range(1, 13):
            months.append(f'{m}월')
            revenue = Order.objects.filter(
                is_active=True,
                order_date__year=year, order_date__month=m,
                status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED', 'CLOSED'],
            ).aggregate(total=Sum('total_amount'))['total'] or 0
            monthly_revenue.append(int(revenue))

            # 고정비: FixedCost
            fixed = FixedCost.objects.filter(
                is_active=True,
                month__year=year, month__month=m,
            ).aggregate(total=Sum('amount'))['total'] or 0

            # 변동비: 매출원가 (COGS — 판매 주문의 원가 × 수량)
            variable = OrderItem.objects.filter(
                is_active=True,
                order__is_active=True,
                order__order_date__year=year, order__order_date__month=m,
                order__status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED', 'CLOSED'],
            ).aggregate(
                total=Sum(F('cost_price') * F('quantity'))
            )['total'] or 0

            # 당기매입액: 해당 월 발주(입고완료 기준) 금액
            from apps.purchase.models import PurchaseOrder
            purchases = PurchaseOrder.objects.filter(
                is_active=True,
                order_date__year=year, order_date__month=m,
                status__in=['RECEIVED', 'PARTIAL_RECEIVED', 'CONFIRMED'],
            ).aggregate(total=Sum('grand_total'))['total'] or 0

            monthly_fixed.append(int(fixed))
            monthly_variable.append(int(variable))
            monthly_costs.append(int(fixed) + int(variable))
            monthly_purchases.append(int(purchases))

        ctx['months_json'] = months
        ctx['revenue_json'] = monthly_revenue
        ctx['costs_json'] = monthly_costs
        ctx['fixed_costs_json'] = monthly_fixed
        ctx['variable_costs_json'] = monthly_variable
        ctx['purchases_json'] = monthly_purchases

        # 올해 총 매출/비용/이익
        ctx['year_revenue'] = sum(monthly_revenue)
        ctx['year_costs'] = sum(monthly_costs)
        ctx['year_profit'] = ctx['year_revenue'] - ctx['year_costs']
        ctx['year_fixed'] = sum(monthly_fixed)
        ctx['year_variable'] = sum(monthly_variable)
        ctx['year_purchases'] = sum(monthly_purchases)

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
            is_active=True,
            invoice_type='SALES', issue_date__year=year,
            issue_date__month__gte=q_start_month,
            issue_date__month__lte=q_start_month + 2,
        ).aggregate(total=Sum('tax_amount'))['total'] or 0
        purchase_tax = TaxInvoice.objects.filter(
            is_active=True,
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
    slug_field = 'invoice_number'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'partner', 'order',
        )


class TaxInvoiceUpdateView(ManagerRequiredMixin, UpdateView):
    model = TaxInvoice
    form_class = TaxInvoiceForm
    template_name = 'accounting/taxinvoice_form.html'
    slug_field = 'invoice_number'
    slug_url_kwarg = 'slug'
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
                is_active=True,
                invoice_type='SALES', issue_date__year=year,
                issue_date__month__gte=m_start, issue_date__month__lte=m_end,
            ).aggregate(
                supply=Sum('supply_amount'), tax=Sum('tax_amount'),
            )
            purchase = TaxInvoice.objects.filter(
                is_active=True,
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
            is_active=True,
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
            is_active=True,
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
            is_active=True,
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
                status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED', 'CLOSED'],
            ).aggregate(total=Sum('total_amount'))['total'] or 0

            # 매출원가 (판매된 제품의 원가) — DB 레벨 집계
            cogs = OrderItem.objects.filter(
                is_active=True,
                order__is_active=True,
                order__order_date__year=year, order__order_date__month=m,
                order__status__in=['CONFIRMED', 'SHIPPED', 'DELIVERED', 'CLOSED'],
            ).aggregate(
                total=Sum(F('cost_price') * F('quantity'))
            )['total'] or 0
            cogs = int(cogs)

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
            try:
                with transaction.atomic():
                    self.object = form.save(commit=False)
                    self.object.created_by = self.request.user
                    self.object.save()
                    formset.instance = self.object
                    formset.save()
                    if not self.object.is_balanced:
                        raise ValueError('unbalanced')
            except ValueError:
                messages.error(
                    self.request,
                    '차변 합계와 대변 합계가 일치하지 않습니다.',
                )
                return self.form_invalid(form)

            # 예산 초과 경고 (차단하지 않음)
            voucher_date = self.object.voucher_date
            if voucher_date:
                for line in self.object.lines.select_related('account').all():
                    if line.account.account_type == 'EXPENSE' and line.debit > 0:
                        budget = Budget.objects.filter(
                            account=line.account,
                            year=voucher_date.year,
                            month=voucher_date.month,
                            is_active=True,
                        ).first()
                        if budget and budget.actual_amount > int(budget.budget_amount):
                            messages.warning(
                                self.request,
                                f'{line.account.name} 예산 초과: '
                                f'예산 {int(budget.budget_amount):,}원 / '
                                f'실적 {budget.actual_amount:,}원 '
                                f'(집행률 {budget.execution_rate}%)',
                            )

            return redirect(self.get_success_url())
        return self.form_invalid(form)


class VoucherDetailView(ManagerRequiredMixin, DetailView):
    model = Voucher
    template_name = 'accounting/voucher_detail.html'
    slug_field = 'voucher_number'
    slug_url_kwarg = 'slug'

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
    slug_field = 'voucher_number'
    slug_url_kwarg = 'slug'
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
            try:
                with transaction.atomic():
                    self.object = form.save()
                    formset.instance = self.object
                    formset.save()
                    if not self.object.is_balanced:
                        raise ValueError('unbalanced')
            except ValueError:
                messages.error(
                    self.request,
                    '차변 합계와 대변 합계가 일치하지 않습니다.',
                )
                return self.form_invalid(form)
            return redirect(self.get_success_url())
        return self.form_invalid(form)


# === 세금계산서 PDF ===
class TaxInvoicePDFView(ManagerRequiredMixin, DetailView):
    model = TaxInvoice
    slug_field = 'invoice_number'
    slug_url_kwarg = 'slug'

    def get(self, request, *args, **kwargs):
        invoice = self.get_object()
        from apps.core.pdf import generate_tax_invoice_pdf
        return generate_tax_invoice_pdf(invoice)


# === 매출정산 PDF ===
class SalesSettlementPDFView(ManagerRequiredMixin, DetailView):
    model = SalesSettlement
    slug_field = 'settlement_number'
    slug_url_kwarg = 'slug'

    def get(self, request, *args, **kwargs):
        settlement = self.get_object()
        from apps.core.pdf import generate_settlement_pdf
        return generate_settlement_pdf(settlement)


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
            is_active=True,
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

        qs = super().get_queryset().filter(is_active=True).select_related(
            'partner', 'purchase_order',
        )
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
            is_active=True,
            status__in=['PENDING', 'PARTIAL', 'OVERDUE']
        ).aggregate(total=Sum('amount'), paid=Sum('paid_amount'))
        ctx['total_remaining'] = (total['total'] or 0) - (total['paid'] or 0)
        return ctx


class APDetailView(ManagerRequiredMixin, DetailView):
    model = AccountPayable
    template_name = 'accounting/ap_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'partner', 'purchase_order',
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
    slug_field = 'payment_number'
    slug_url_kwarg = 'slug'

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
            return redirect('accounting:payment_distribute', slug=self.object.payment_number)
        return self.render_to_response(ctx)


# ── 일괄 가져오기 ──

class FixedCostImportView(ManagerRequiredMixin, TemplateView):
    template_name = 'core/import.html'

    def get(self, request, *args, **kwargs):
        if request.GET.get('action') == 'export':
            from apps.core.import_views import export_resource_data
            from .resources import FixedCostResource
            return export_resource_data(FixedCostResource(), '고정비_데이터')
        return super().get(request, *args, **kwargs)

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
        ctx['supports_export'] = True
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

    def get(self, request, *args, **kwargs):
        if request.GET.get('action') == 'export':
            from apps.core.import_views import export_resource_data
            from .resources import AccountCodeResource
            return export_resource_data(AccountCodeResource(), '계정과목_데이터')
        return super().get(request, *args, **kwargs)

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
        ctx['supports_export'] = True
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

    def get(self, request, *args, **kwargs):
        if request.GET.get('action') == 'export':
            from apps.core.import_views import export_resource_data
            from .resources import TaxInvoiceResource
            return export_resource_data(TaxInvoiceResource(), '세금계산서_데이터')
        return super().get(request, *args, **kwargs)

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
        ctx['supports_export'] = True
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
    export_filename = '전표_데이터'
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
    export_filename = '원천징수_데이터'
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
    slug_field = 'settlement_number'
    slug_url_kwarg = 'slug'

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

            # 표준원가 자동 재계산: BOM 자재원가 → 노무비/간접비 → Product.cost_price 갱신
            from apps.production.models import StandardCost
            updated_count = 0
            for sc in StandardCost.objects.filter(is_current=True, is_active=True).select_related('product'):
                sc.calculate_material_cost()
                sc.save()  # labor_cost, overhead_cost, total 자동 재계산
                if sc.product.cost_price != sc.total_standard_cost:
                    sc.product.cost_price = sc.total_standard_cost
                    sc.product.save(update_fields=['cost_price', 'updated_at'])
                    updated_count += 1

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
            f'(총 재고자산: {total_value:,}원, '
            f'표준원가 갱신: {updated_count}건)',
        )
        return redirect(
            'accounting:settlement_detail', slug=settlement.settlement_number,
        )


class CostSettlementRecalcView(ManagerRequiredMixin, View):
    """기존 정산 건의 표준원가 재계산 + 스냅샷 갱신"""

    def post(self, request, slug):
        settlement = get_object_or_404(
            CostSettlement, settlement_number=slug, is_active=True,
        )
        from apps.production.models import StandardCost

        with transaction.atomic():
            # 표준원가 재계산
            updated_count = 0
            for sc in StandardCost.objects.filter(
                is_current=True, is_active=True,
            ).select_related('product'):
                sc.calculate_material_cost()
                sc.save()
                if sc.product.cost_price != sc.total_standard_cost:
                    sc.product.cost_price = sc.total_standard_cost
                    sc.product.save(update_fields=['cost_price', 'updated_at'])
                    updated_count += 1

            # 정산 항목 스냅샷 갱신
            total_value = 0
            for item in settlement.items.select_related('product').all():
                item.cost_price = item.product.cost_price or 0
                item.stock_quantity = item.product.current_stock
                item.inventory_value = item.stock_quantity * item.cost_price
                item.save(update_fields=[
                    'cost_price', 'stock_quantity',
                    'inventory_value', 'updated_at',
                ])
                total_value += item.inventory_value

            settlement.total_inventory_value = total_value
            settlement.save(
                update_fields=['total_inventory_value', 'updated_at'],
            )

        messages.success(
            request,
            f'{settlement.settlement_number} 원가 재계산 완료 '
            f'(총 재고자산: {total_value:,}원, '
            f'표준원가 갱신: {updated_count}건)',
        )
        return redirect(
            'accounting:settlement_detail', slug=settlement.settlement_number,
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
    slug_field = 'settlement_number'
    slug_url_kwarg = 'slug'

    def get_queryset(self):
        return super().get_queryset().select_related(
            'commission_bank_account', 'commission_deposit_account',
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
        # 계좌 목록 (출금/입금 공용)
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

    def post(self, request, slug):
        settlement = get_object_or_404(
            SalesSettlement, settlement_number=slug, is_active=True,
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
            'accounting:sales_settlement_detail', slug=settlement.settlement_number,
        )


class SalesSettlementCommissionPayView(ManagerRequiredMixin, View):
    """정산 수수료 지급 처리"""

    def post(self, request, slug):
        settlement = get_object_or_404(
            SalesSettlement, settlement_number=slug, is_active=True,
        )
        if settlement.commission_paid:
            messages.warning(request, '이미 수수료 지급 완료된 정산입니다.')
            return redirect(
                'accounting:sales_settlement_detail', slug=settlement.settlement_number,
            )

        bank_id = request.POST.get('commission_bank_account')
        bank = None
        if bank_id:
            bank = BankAccount.objects.filter(
                pk=bank_id, is_active=True,
            ).first()

        deposit_bank_id = request.POST.get('commission_deposit_account')
        deposit_bank = None
        if deposit_bank_id:
            deposit_bank = BankAccount.objects.filter(
                pk=deposit_bank_id, is_active=True,
            ).first()

        commission_total = int(settlement.total_commission)
        if commission_total <= 0:
            messages.info(request, '지급할 수수료가 없습니다.')
            return redirect(
                'accounting:sales_settlement_detail', slug=settlement.settlement_number,
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

            if not acct_payable or not acct_deposit:
                messages.warning(request, '수수료 전표 생성에 필요한 계정과목이 미등록되어 전표가 생성되지 않았습니다.')
            else:
                # 차변: 미지급금 (부채 감소)
                deposit_desc = f' → {deposit_bank.name}' if deposit_bank else ''
                VoucherLine.objects.create(
                    voucher=voucher,
                    account=acct_payable,
                    debit=commission_total,
                    credit=0,
                    description=(
                        f'{settlement.settlement_number} 수수료{deposit_desc}'
                    ),
                )
                # 대변: 보통예금 (자산 감소)
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

            # 입금계좌 잔액 증가 (선택된 경우)
            if deposit_bank:
                BankAccount.objects.filter(pk=deposit_bank.pk).update(
                    balance=F('balance') + commission_total,
                )

            # 정산 수수료 지급 상태 업데이트
            settlement.commission_bank_account = bank
            settlement.commission_deposit_account = deposit_bank
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
            'accounting:sales_settlement_detail', slug=settlement.settlement_number,
        )


class SalesSettlementCommissionManualView(ManagerRequiredMixin, View):
    """수수료 수동 지급완료 처리 (전표/출금 없이 상태만 변경)"""

    def post(self, request, slug):
        settlement = get_object_or_404(
            SalesSettlement, settlement_number=slug, is_active=True,
        )
        if settlement.commission_paid:
            messages.warning(request, '이미 수수료 지급 완료된 정산입니다.')
            return redirect(
                'accounting:sales_settlement_detail', slug=settlement.settlement_number,
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
            'accounting:sales_settlement_detail', slug=settlement.settlement_number,
        )


class SalesSettlementCreateView(ManagerRequiredMixin, TemplateView):
    """주문 선택 → 매출 정산 생성"""
    template_name = 'accounting/sales_settlement_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # 미정산 + 종결 주문만 표시
        orders = (
            Order.objects.filter(
                is_active=True,
                is_settled=False,
                status='CLOSED',
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
        ctx['order_costs'] = {str(k): v for k, v in order_costs.items()}
        ctx['commission_rates'] = {str(k): v for k, v in rates.items()}
        ctx['bank_accounts'] = BankAccount.objects.filter(is_active=True)
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
            total_platform_commission = 0
            total_commission = 0
            total_profit = 0
            total_cost_variance = 0

            orders = Order.objects.filter(
                pk__in=order_ids, is_settled=False,
            ).select_related('partner')

            for order in orders:
                revenue = int(order.total_amount)
                tax = int(order.tax_total)
                shipping = int(order.shipping_cost or 0)
                # 원가 계산: 주문시점 + 정산시점(현재)
                items = order.items.select_related('product').all()
                cost = sum(
                    int(i.cost_price or 0) * int(i.quantity)
                    for i in items
                )
                current_cost = sum(
                    int(i.product.cost_price or 0) * int(i.quantity)
                    for i in items
                )
                cost_variance = current_cost - cost
                cost_variance_rate = (
                    round(cost_variance / cost * 100, 2) if cost else 0
                )
                # 수수료: 정률(%) or 정액(원)
                platform_comm = int(order.platform_commission or 0)
                comm_type = request.POST.get(f'comm_type_{order.pk}', 'rate')
                rate_val = request.POST.get(f'rate_{order.pk}', '')
                if comm_type == 'fixed' and rate_val:
                    # 정액: 입력값 그대로 수수료
                    try:
                        settle_commission = round(Decimal(rate_val))
                    except Exception:
                        settle_commission = 0
                    comm_rate = Decimal('0')
                else:
                    # 정률: 기존 로직
                    if rate_val:
                        try:
                            comm_rate = Decimal(rate_val)
                        except Exception:
                            comm_rate = Decimal('0')
                    else:
                        comm_rate = rates_map.get(
                            order.partner_id, Decimal('0'),
                        )
                    net_revenue = max(revenue - platform_comm, 0)
                    comm_base_type = request.POST.get('commission_base', 'revenue')
                    if comm_base_type == 'profit':
                        comm_base = max(net_revenue - cost - shipping, 0)
                    else:
                        comm_base = net_revenue
                    settle_commission = round(comm_base * comm_rate / 100)
                profit = revenue - cost - shipping - platform_comm - settle_commission

                SalesSettlementOrder.objects.create(
                    settlement=settlement,
                    order=order,
                    revenue=revenue,
                    cost=cost,
                    current_cost=current_cost,
                    cost_variance=cost_variance,
                    cost_variance_rate=cost_variance_rate,
                    tax=tax,
                    shipping=shipping,
                    platform_commission=platform_comm,
                    commission_rate=comm_rate,
                    commission=settle_commission,
                    profit=profit,
                    created_by=request.user,
                )

                total_revenue += revenue
                total_cost += cost
                total_tax += tax
                total_shipping += shipping
                total_platform_commission += platform_comm
                total_commission += settle_commission
                total_profit += profit
                total_cost_variance += cost_variance

            settlement.total_revenue = total_revenue
            settlement.total_cost = total_cost
            settlement.total_tax = total_tax
            settlement.total_shipping = total_shipping
            settlement.total_platform_commission = total_platform_commission
            settlement.total_commission = total_commission
            settlement.total_profit = total_profit
            settlement.total_cost_variance = total_cost_variance
            settlement.save(update_fields=[
                'total_revenue', 'total_cost', 'total_tax',
                'total_shipping', 'total_platform_commission',
                'total_commission', 'total_profit',
                'total_cost_variance', 'updated_at',
            ])

            # 주문 정산완료 마킹
            orders.update(is_settled=True)

            # 정산 계좌 처리
            first_order = orders.first()
            partner = first_order.partner if first_order else None

            # 수수료 출금 (주문 배송완료 시그널에서 이미 출금된 건 제외)
            comm_bank_id = request.POST.get('commission_bank')
            if comm_bank_id and total_commission > 0 and partner:
                # 시그널에서 이미 처리된 수수료 출금 금액 합산
                already_paid = Payment.objects.filter(
                    partner=partner,
                    payment_type='DISBURSEMENT',
                    is_active=True,
                    reference__in=[
                        f'주문 {o.order_number} 수수료'
                        for o in orders
                    ],
                ).aggregate(total=Sum('amount'))['total'] or 0
                remaining_commission = total_commission - int(already_paid)

                comm_bank = BankAccount.objects.filter(
                    pk=comm_bank_id, is_active=True,
                ).first()
                if comm_bank and remaining_commission > 0:
                    Payment.objects.create(
                        payment_type='DISBURSEMENT',
                        partner=partner,
                        bank_account=comm_bank,
                        amount=remaining_commission,
                        payment_date=date.today(),
                        payment_method='BANK_TRANSFER',
                        reference=f'정산 {settlement.settlement_number} 수수료',
                        notes=f'매출정산 수수료 {remaining_commission:,}원',
                        created_by=request.user,
                    )
                settlement.commission_bank_account = comm_bank
                settlement.commission_paid = True
                settlement.commission_paid_date = date.today()
                settlement.commission_paid_amount = total_commission
                settlement.save()

            # 시그널에서 이미 수수료 전액 출금된 경우 자동 정산완료
            if (
                total_commission > 0
                and not settlement.commission_paid
                and partner
            ):
                already_paid = Payment.objects.filter(
                    partner=partner,
                    payment_type='DISBURSEMENT',
                    is_active=True,
                    reference__in=[
                        f'주문 {o.order_number} 수수료'
                        for o in orders
                    ],
                ).aggregate(total=Sum('amount'))['total'] or 0
                if int(already_paid) >= total_commission:
                    settlement.commission_paid = True
                    settlement.commission_paid_date = date.today()
                    settlement.commission_paid_amount = total_commission
                    settlement.save(update_fields=[
                        'commission_paid', 'commission_paid_date',
                        'commission_paid_amount', 'updated_at',
                    ])

            # 정산금 입금 (매출 - 수수료)
            settle_bank_id = request.POST.get('settlement_bank')
            if settle_bank_id and partner:
                settle_bank = BankAccount.objects.filter(
                    pk=settle_bank_id, is_active=True,
                ).first()
                if settle_bank:
                    net_amount = total_revenue + total_tax - total_commission
                    if net_amount > 0:
                        Payment.objects.create(
                            payment_type='RECEIPT',
                            partner=partner,
                            bank_account=settle_bank,
                            amount=net_amount,
                            payment_date=date.today(),
                            payment_method='BANK_TRANSFER',
                            reference=f'정산 {settlement.settlement_number} 입금',
                            notes=f'매출정산 입금 {net_amount:,}원 (매출 {total_revenue + total_tax:,} - 수수료 {total_commission:,})',
                            created_by=request.user,
                        )

        messages.success(
            request,
            f'매출정산 {settlement.settlement_number} 완료 '
            f'({orders.count()}건, 이익: {total_profit:,}원)',
        )
        return redirect(
            'accounting:sales_settlement_detail',
            slug=settlement.settlement_number,
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
            # 마감 전 미승인 전표 검증
            pending_vouchers = Voucher.objects.filter(
                is_active=True,
                voucher_date__year=year,
                voucher_date__month=month,
                approval_status__in=['DRAFT', 'SUBMITTED'],
            ).exists()
            if pending_vouchers:
                messages.error(request, '미승인 전표가 있어 마감할 수 없습니다. 먼저 전표를 승인하거나 삭제하세요.')
                return redirect(f'/accounting/closing/?year={year}')

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


# === 전자세금계산서 ===
class ElectronicInvoiceIssueView(ManagerRequiredMixin, View):
    """단건 전자세금계산서 발행"""

    def post(self, request, slug):
        invoice = get_object_or_404(TaxInvoice, invoice_number=slug, is_active=True)

        if invoice.electronic_status not in ('NONE', 'DRAFT', 'REJECTED'):
            messages.error(
                request,
                f'현재 상태({invoice.get_electronic_status_display()})에서는 발행할 수 없습니다.',
            )
            return redirect('accounting:taxinvoice_detail', slug=invoice.invoice_number)

        from .nts_client import NTSClient, NTSAPIError

        try:
            client = NTSClient()
            result = client.issue(invoice)

            with transaction.atomic():
                invoice.electronic_status = TaxInvoice.ElectronicStatus.ISSUED
                invoice.issue_id = result.get('issue_id', '')
                invoice.nts_confirmation_number = result.get('confirmation_number', '')
                invoice.sent_at = timezone.now()
                invoice.nts_response = result.get('raw_response', {})
                invoice.save(update_fields=[
                    'electronic_status', 'issue_id', 'nts_confirmation_number',
                    'sent_at', 'nts_response', 'updated_at',
                ])

            messages.success(request, f'전자세금계산서 발행 완료 ({invoice.invoice_number})')
        except NTSAPIError as e:
            messages.error(request, f'전자세금계산서 발행 실패: {e}')

        return redirect('accounting:taxinvoice_detail', slug=invoice.invoice_number)


class ElectronicInvoiceBatchIssueView(ManagerRequiredMixin, View):
    """선택 건 일괄 전자발행"""

    def post(self, request):
        invoice_ids = request.POST.getlist('invoice_ids')
        if not invoice_ids:
            messages.warning(request, '발행할 세금계산서를 선택해주세요.')
            return redirect('accounting:taxinvoice_list')

        invoices = TaxInvoice.objects.filter(
            pk__in=invoice_ids,
            is_active=True,
            electronic_status__in=['NONE', 'DRAFT', 'REJECTED'],
        )

        if not invoices.exists():
            messages.warning(request, '발행 가능한 세금계산서가 없습니다.')
            return redirect('accounting:taxinvoice_list')

        from .nts_client import NTSClient, NTSAPIError

        client = NTSClient()
        success_count = 0
        fail_count = 0

        for invoice in invoices:
            try:
                result = client.issue(invoice)
                with transaction.atomic():
                    invoice.electronic_status = TaxInvoice.ElectronicStatus.ISSUED
                    invoice.issue_id = result.get('issue_id', '')
                    invoice.nts_confirmation_number = result.get('confirmation_number', '')
                    invoice.sent_at = timezone.now()
                    invoice.nts_response = result.get('raw_response', {})
                    invoice.save(update_fields=[
                        'electronic_status', 'issue_id', 'nts_confirmation_number',
                        'sent_at', 'nts_response', 'updated_at',
                    ])
                success_count += 1
            except NTSAPIError:
                fail_count += 1

        if success_count:
            messages.success(request, f'{success_count}건 전자발행 완료')
        if fail_count:
            messages.error(request, f'{fail_count}건 전자발행 실패')

        return redirect('accounting:taxinvoice_list')


class ElectronicInvoiceStatusView(ManagerRequiredMixin, View):
    """국세청 전송상태 조회"""

    def get(self, request, slug):
        invoice = get_object_or_404(TaxInvoice, invoice_number=slug, is_active=True)

        if not invoice.issue_id:
            messages.warning(request, '전자발행되지 않은 세금계산서입니다.')
            return redirect('accounting:taxinvoice_detail', slug=invoice.invoice_number)

        from .nts_client import NTSClient, NTSAPIError

        try:
            client = NTSClient()
            result = client.query(invoice)

            status_value = result.get('status', '')
            if status_value and hasattr(TaxInvoice.ElectronicStatus, status_value):
                with transaction.atomic():
                    invoice.electronic_status = status_value
                    invoice.nts_confirmation_number = result.get(
                        'confirmation_number', invoice.nts_confirmation_number,
                    )
                    invoice.nts_response = result
                    invoice.save(update_fields=[
                        'electronic_status', 'nts_confirmation_number',
                        'nts_response', 'updated_at',
                    ])

            messages.success(
                request,
                f'상태 조회 완료: {invoice.get_electronic_status_display()}',
            )
        except NTSAPIError as e:
            messages.error(request, f'상태 조회 실패: {e}')

        return redirect('accounting:taxinvoice_detail', slug=invoice.invoice_number)


class ElectronicInvoiceCancelView(ManagerRequiredMixin, View):
    """전자세금계산서 취소"""

    def post(self, request, slug):
        invoice = get_object_or_404(TaxInvoice, invoice_number=slug, is_active=True)
        reason = request.POST.get('cancel_reason', '')

        if invoice.electronic_status not in ('ISSUED', 'SENT', 'ACCEPTED'):
            messages.error(
                request,
                f'현재 상태({invoice.get_electronic_status_display()})에서는 취소할 수 없습니다.',
            )
            return redirect('accounting:taxinvoice_detail', slug=invoice.invoice_number)

        from .nts_client import NTSClient, NTSAPIError

        try:
            client = NTSClient()
            result = client.cancel(invoice, reason=reason)

            with transaction.atomic():
                invoice.electronic_status = TaxInvoice.ElectronicStatus.CANCELLED
                invoice.nts_response = result.get('raw_response', {})
                invoice.save(update_fields=[
                    'electronic_status', 'nts_response', 'updated_at',
                ])

            messages.success(request, f'전자세금계산서 취소 완료 ({invoice.invoice_number})')
        except NTSAPIError as e:
            messages.error(request, f'전자세금계산서 취소 실패: {e}')

        return redirect('accounting:taxinvoice_detail', slug=invoice.invoice_number)


# === 재무제표 ===

class BalanceSheetView(ManagerRequiredMixin, TemplateView):
    """대차대조표 — 기준일 기준 자산/부채/자본 잔액"""
    template_name = 'accounting/balance_sheet.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        as_of = self.request.GET.get('as_of', date.today().isoformat())
        ctx['as_of'] = as_of

        qs = VoucherLine.objects.filter(
            is_active=True, voucher__is_active=True,
            voucher__approval_status='APPROVED',
            voucher__voucher_date__lte=as_of,
        )

        account_totals = qs.values(
            'account__pk', 'account__code', 'account__name', 'account__account_type',
        ).annotate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit'),
        ).order_by('account__code')

        assets = []
        liabilities = []
        equity = []
        total_assets = 0
        total_liabilities = 0
        total_equity = 0

        for row in account_totals:
            debit = int(row['total_debit'] or 0)
            credit = int(row['total_credit'] or 0)
            acct_type = row['account__account_type']

            if acct_type == 'ASSET':
                balance = debit - credit
                assets.append({
                    'code': row['account__code'],
                    'name': row['account__name'],
                    'balance': balance,
                })
                total_assets += balance
            elif acct_type == 'LIABILITY':
                balance = credit - debit
                liabilities.append({
                    'code': row['account__code'],
                    'name': row['account__name'],
                    'balance': balance,
                })
                total_liabilities += balance
            elif acct_type == 'EQUITY':
                balance = credit - debit
                equity.append({
                    'code': row['account__code'],
                    'name': row['account__name'],
                    'balance': balance,
                })
                total_equity += balance

        ctx['assets'] = assets
        ctx['liabilities'] = liabilities
        ctx['equity'] = equity
        ctx['total_assets'] = total_assets
        ctx['total_liabilities'] = total_liabilities
        ctx['total_equity'] = total_equity
        ctx['total_liabilities_equity'] = total_liabilities + total_equity
        ctx['is_balanced'] = total_assets == (total_liabilities + total_equity)
        return ctx


class BalanceSheetExcelView(ManagerRequiredMixin, TemplateView):
    """대차대조표 Excel 다운로드"""
    template_name = 'accounting/balance_sheet.html'

    def get(self, request, *args, **kwargs):
        import openpyxl
        from openpyxl.styles import Font

        as_of = request.GET.get('as_of', date.today().isoformat())

        qs = VoucherLine.objects.filter(
            is_active=True, voucher__is_active=True,
            voucher__approval_status='APPROVED',
            voucher__voucher_date__lte=as_of,
        )

        account_totals = qs.values(
            'account__code', 'account__name', 'account__account_type',
        ).annotate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit'),
        ).order_by('account__code')

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '대차대조표'
        bold = Font(bold=True)

        ws.cell(row=1, column=1, value=f'대차대조표 (기준일: {as_of})').font = bold
        headers = ['구분', '계정코드', '계정명', '잔액']
        for col, h in enumerate(headers, 1):
            ws.cell(row=3, column=col, value=h).font = bold

        row_num = 4
        for row in account_totals:
            debit = int(row['total_debit'] or 0)
            credit = int(row['total_credit'] or 0)
            acct_type = row['account__account_type']
            if acct_type not in ('ASSET', 'LIABILITY', 'EQUITY'):
                continue
            if acct_type == 'ASSET':
                balance = debit - credit
                label = '자산'
            elif acct_type == 'LIABILITY':
                balance = credit - debit
                label = '부채'
            else:
                balance = credit - debit
                label = '자본'
            ws.cell(row=row_num, column=1, value=label)
            ws.cell(row=row_num, column=2, value=row['account__code'])
            ws.cell(row=row_num, column=3, value=row['account__name'])
            ws.cell(row=row_num, column=4, value=balance)
            row_num += 1

        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename=balance_sheet_{as_of}.xlsx'
        wb.save(response)
        return response


class CashFlowView(ManagerRequiredMixin, TemplateView):
    """현금흐름표 — 영업/투자/재무 활동별 현금 흐름"""
    template_name = 'accounting/cash_flow.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        from_date = self.request.GET.get('from_date', date(today.year, 1, 1).isoformat())
        to_date = self.request.GET.get('to_date', today.isoformat())
        ctx['from_date'] = from_date
        ctx['to_date'] = to_date

        base_qs = VoucherLine.objects.filter(
            is_active=True, voucher__is_active=True,
            voucher__approval_status='APPROVED',
            voucher__voucher_date__gte=from_date,
            voucher__voucher_date__lte=to_date,
        )

        # 영업활동: 수익(REVENUE) - 비용(EXPENSE)
        revenue_lines = base_qs.filter(account__account_type='REVENUE')
        revenue_total = int(
            (revenue_lines.aggregate(s=Sum('credit'))['s'] or 0)
            - (revenue_lines.aggregate(s=Sum('debit'))['s'] or 0)
        )

        expense_lines = base_qs.filter(account__account_type='EXPENSE')
        expense_total = int(
            (expense_lines.aggregate(s=Sum('debit'))['s'] or 0)
            - (expense_lines.aggregate(s=Sum('credit'))['s'] or 0)
        )

        # AR/AP 변동
        ar_change = int(
            AccountReceivable.objects.filter(
                is_active=True,
                created_at__date__gte=from_date,
                created_at__date__lte=to_date,
            ).aggregate(s=Sum('balance'))['s'] or 0
        )
        ap_change = int(
            AccountPayable.objects.filter(
                is_active=True,
                created_at__date__gte=from_date,
                created_at__date__lte=to_date,
            ).aggregate(s=Sum('balance'))['s'] or 0
        )

        operating = revenue_total - expense_total - ar_change + ap_change

        # 투자활동: 자산 취득(-), 처분(+)
        from apps.asset.models import FixedAsset
        acquisitions = int(
            FixedAsset.objects.filter(
                is_active=True,
                acquisition_date__gte=from_date,
                acquisition_date__lte=to_date,
            ).aggregate(s=Sum('acquisition_cost'))['s'] or 0
        )
        disposals = int(
            FixedAsset.objects.filter(
                is_active=True,
                disposal_date__gte=from_date,
                disposal_date__lte=to_date,
            ).aggregate(s=Sum('disposal_amount'))['s'] or 0
        )
        investing = disposals - acquisitions

        # 재무활동: 자본 계정 변동
        equity_lines = base_qs.filter(account__account_type='EQUITY')
        financing = int(
            (equity_lines.aggregate(s=Sum('credit'))['s'] or 0)
            - (equity_lines.aggregate(s=Sum('debit'))['s'] or 0)
        )

        net_change = operating + investing + financing

        # 기초 현금 (BankAccount 기초잔액 합계)
        opening_cash = int(
            BankAccount.objects.filter(is_active=True).aggregate(
                s=Sum('opening_balance'),
            )['s'] or 0
        )
        closing_cash = opening_cash + net_change

        ctx.update({
            'revenue_total': revenue_total,
            'expense_total': expense_total,
            'ar_change': ar_change,
            'ap_change': ap_change,
            'operating': operating,
            'acquisitions': acquisitions,
            'disposals': disposals,
            'investing': investing,
            'financing': financing,
            'net_change': net_change,
            'opening_cash': opening_cash,
            'closing_cash': closing_cash,
        })
        return ctx


# === 카드 관리 ===
class CreditCardListView(ManagerRequiredMixin, ListView):
    model = CreditCard
    template_name = 'accounting/card_list.html'
    context_object_name = 'cards'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True)
        card_type = self.request.GET.get('card_type')
        if card_type:
            qs = qs.filter(card_type=card_type)
        card_issuer = self.request.GET.get('card_issuer')
        if card_issuer:
            qs = qs.filter(card_issuer=card_issuer)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(cardholder__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['type_choices'] = CreditCard.CardType.choices
        ctx['issuer_choices'] = CreditCard.CardIssuer.choices
        return ctx


class CreditCardCreateView(ManagerRequiredMixin, CreateView):
    model = CreditCard
    form_class = CreditCardForm
    template_name = 'accounting/card_form.html'
    success_url = reverse_lazy('accounting:card_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class CreditCardUpdateView(ManagerRequiredMixin, UpdateView):
    model = CreditCard
    form_class = CreditCardForm
    template_name = 'accounting/card_form.html'
    success_url = reverse_lazy('accounting:card_list')


class CreditCardDetailView(ManagerRequiredMixin, DetailView):
    model = CreditCard
    template_name = 'accounting/card_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['recent_transactions'] = CardTransaction.objects.filter(
            card=self.object, is_active=True,
        ).select_related('partner').order_by('-transaction_date', '-pk')[:10]
        ctx['recent_billings'] = CardBilling.objects.filter(
            card=self.object, is_active=True,
        ).order_by('-billing_month')[:5]
        return ctx


# === 카드 거래 ===
class CardTransactionListView(ManagerRequiredMixin, ListView):
    model = CardTransaction
    template_name = 'accounting/card_transaction_list.html'
    context_object_name = 'transactions'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('card', 'partner')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            qs = qs.filter(transaction_date__gte=date_from)
        if date_to:
            qs = qs.filter(transaction_date__lte=date_to)
        card_id = self.request.GET.get('card_id')
        if card_id:
            qs = qs.filter(card_id=card_id)
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category=category)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(merchant_name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cards'] = CreditCard.objects.filter(is_active=True)
        ctx['category_choices'] = CardTransaction.Category.choices
        return ctx


class CardTransactionCreateView(ManagerRequiredMixin, CreateView):
    model = CardTransaction
    form_class = CardTransactionForm
    template_name = 'accounting/card_transaction_form.html'
    success_url = reverse_lazy('accounting:card_transaction_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class CardTransactionUpdateView(ManagerRequiredMixin, UpdateView):
    model = CardTransaction
    form_class = CardTransactionForm
    template_name = 'accounting/card_transaction_form.html'
    success_url = reverse_lazy('accounting:card_transaction_list')


# === 카드 청구 ===
class CardBillingListView(ManagerRequiredMixin, ListView):
    model = CardBilling
    template_name = 'accounting/card_billing_list.html'
    context_object_name = 'billings'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(
            is_active=True,
        ).select_related('card')
        card_id = self.request.GET.get('card_id')
        if card_id:
            qs = qs.filter(card_id=card_id)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['cards'] = CreditCard.objects.filter(is_active=True)
        ctx['status_choices'] = CardBilling.Status.choices
        return ctx


class CardBillingDetailView(ManagerRequiredMixin, DetailView):
    model = CardBilling
    template_name = 'accounting/card_billing_detail.html'

    def get_queryset(self):
        return super().get_queryset().select_related('card', 'payment')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['billing_transactions'] = CardTransaction.objects.filter(
            billing=self.object, is_active=True,
        ).select_related('card', 'partner').order_by('-transaction_date')
        return ctx


class CardBillingPayView(ManagerRequiredMixin, View):
    """카드 청구 결제 처리 (POST only)"""

    def post(self, request, pk):
        with transaction.atomic():
            billing = CardBilling.objects.select_for_update().get(
                pk=pk, is_active=True,
            )

            if billing.status == 'PAID':
                messages.error(request, '이미 결제 완료된 청구서입니다.')
                return redirect('accounting:card_billing_detail', pk=pk)

            card = billing.card
            if not card.payment_account:
                messages.error(request, '카드에 결제계좌가 설정되지 않았습니다.')
                return redirect('accounting:card_billing_detail', pk=pk)

            pay_amount = billing.remaining_amount
            if pay_amount <= 0:
                messages.error(request, '결제할 금액이 없습니다.')
                return redirect('accounting:card_billing_detail', pk=pk)

            # Payment(DISBURSEMENT) 생성 — 거래처는 카드 거래내역에서 추출
            from apps.core.utils import generate_document_number
            from apps.sales.models import Partner
            # 카드 청구 결제용 거래처: 청구서 내 거래의 partner 또는 기본 거래처
            billing_partner = (
                CardTransaction.objects.filter(
                    billing=billing, partner__isnull=False, is_active=True,
                ).values_list('partner', flat=True).first()
            )
            if billing_partner:
                pay_partner = Partner.objects.get(pk=billing_partner)
            else:
                pay_partner, _ = Partner.objects.get_or_create(
                    code='CARD-ISSUER',
                    defaults={
                        'name': '카드사결제',
                        'partner_type': 'SUPPLIER',
                    },
                )
            payment = Payment.objects.create(
                payment_number=generate_document_number(Payment, 'payment_number', 'PM'),
                payment_type='DISBURSEMENT',
                partner=pay_partner,
                bank_account=card.payment_account,
                amount=pay_amount,
                payment_date=date.today(),
                payment_method='CARD',
                reference=f'카드청구결제: {card.name} {billing.billing_month.strftime("%Y-%m")}',
                created_by=request.user,
            )

            # CardBilling 갱신 (F() 원자적 업데이트)
            CardBilling.objects.filter(pk=billing.pk).update(
                paid_amount=F('paid_amount') + pay_amount,
                payment=payment,
            )
            billing.refresh_from_db()

            if billing.paid_amount >= billing.total_amount:
                new_status = 'PAID'
            elif billing.paid_amount > 0:
                new_status = 'PARTIAL'
            else:
                new_status = billing.status
            if new_status != billing.status:
                CardBilling.objects.filter(pk=billing.pk).update(status=new_status)

        messages.success(request, f'{pay_amount:,}원 카드 청구 결제 처리 완료')
        return redirect('accounting:card_billing_detail', pk=pk)


# === 환차손익 ===

class ExchangeGainLossView(ManagerRequiredMixin, TemplateView):
    """환율 변동에 따른 외화 미수/미지급 환차손익 계산"""
    template_name = 'accounting/exchange_gain_loss.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # 외화 주문 기반 AR (KRW가 아닌 통화)
        from apps.sales.models import Order
        from apps.purchase.models import PurchaseOrder

        ar_rows = []
        for ar in AccountReceivable.objects.filter(
            is_active=True, status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
            order__isnull=False, order__currency__isnull=False,
        ).select_related('partner', 'order__currency'):
            order = ar.order
            if not order.currency or order.currency.is_base:
                continue
            # 잔액 (외화 기준)
            remaining_krw = ar.remaining_amount
            original_rate = order.exchange_rate or 1
            if original_rate <= 0:
                continue
            foreign_remaining = remaining_krw / original_rate

            # 현재 환율 조회
            current_rate_obj = ExchangeRate.objects.filter(
                currency=order.currency, is_active=True,
            ).order_by('-rate_date').first()
            current_rate = current_rate_obj.rate if current_rate_obj else original_rate

            revalued_krw = int(foreign_remaining * current_rate)
            gain_loss = revalued_krw - int(remaining_krw)

            ar_rows.append({
                'partner': ar.partner.name,
                'currency': order.currency.code,
                'foreign_amount': round(foreign_remaining, 2),
                'original_rate': original_rate,
                'original_krw': int(remaining_krw),
                'current_rate': current_rate,
                'revalued_krw': revalued_krw,
                'gain_loss': gain_loss,
                'type': 'AR',
            })

        ap_rows = []
        for ap in AccountPayable.objects.filter(
            is_active=True, status__in=['PENDING', 'PARTIAL', 'OVERDUE'],
            purchase_order__isnull=False,
            purchase_order__currency__isnull=False,
        ).select_related('partner', 'purchase_order__currency'):
            po = ap.purchase_order
            if not po.currency or po.currency.is_base:
                continue
            remaining_krw = ap.remaining_amount
            original_rate = po.exchange_rate or 1
            if original_rate <= 0:
                continue
            foreign_remaining = remaining_krw / original_rate

            current_rate_obj = ExchangeRate.objects.filter(
                currency=po.currency, is_active=True,
            ).order_by('-rate_date').first()
            current_rate = current_rate_obj.rate if current_rate_obj else original_rate

            revalued_krw = int(foreign_remaining * current_rate)
            gain_loss = revalued_krw - int(remaining_krw)

            ap_rows.append({
                'partner': ap.partner.name,
                'currency': po.currency.code,
                'foreign_amount': round(foreign_remaining, 2),
                'original_rate': original_rate,
                'original_krw': int(remaining_krw),
                'current_rate': current_rate,
                'revalued_krw': revalued_krw,
                'gain_loss': gain_loss,
                'type': 'AP',
            })

        all_rows = ar_rows + ap_rows
        total_gain = sum(r['gain_loss'] for r in all_rows if r['gain_loss'] > 0)
        total_loss = sum(r['gain_loss'] for r in all_rows if r['gain_loss'] < 0)
        net_gain_loss = total_gain + total_loss

        ctx['ar_rows'] = ar_rows
        ctx['ap_rows'] = ap_rows
        ctx['total_gain'] = total_gain
        ctx['total_loss'] = total_loss
        ctx['net_gain_loss'] = net_gain_loss
        return ctx
