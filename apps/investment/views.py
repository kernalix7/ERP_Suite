import json

from apps.core.mixins import ManagerRequiredMixin
from django.db.models import Sum
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView

from .models import Investor, InvestmentRound, Investment, EquityChange, Distribution
from .forms import (
    InvestorForm, InvestmentRoundForm, InvestmentForm,
    EquityChangeForm, DistributionForm,
)


class InvestmentDashboardView(ManagerRequiredMixin, TemplateView):
    template_name = 'investment/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # 총 투자금
        ctx['total_invested'] = Investment.objects.aggregate(
            total=Sum('amount')
        )['total'] or 0

        # 투자자 수
        ctx['investor_count'] = Investor.objects.count()

        # 최근 기업가치
        latest_round = InvestmentRound.objects.first()
        ctx['latest_valuation'] = latest_round.post_valuation if latest_round else 0
        ctx['latest_round'] = latest_round

        # 지분 현황 (파이차트용)
        investors = Investor.objects.all()
        equity_data = []
        total_share = 0
        for inv in investors:
            share = float(inv.current_share)
            if share > 0:
                equity_data.append({'name': inv.name, 'share': share})
                total_share += share
        # 잔여 지분 (대표/창업자)
        if total_share < 100:
            equity_data.insert(0, {'name': '대표/창업자', 'share': round(100 - total_share, 3)})
        ctx['equity_json'] = json.dumps(equity_data, ensure_ascii=False)

        # 예정된 배당
        ctx['upcoming_distributions'] = Distribution.objects.filter(
            status__in=['SCHEDULED', 'PENDING']
        )[:5]

        # 최근 투자 내역
        ctx['recent_investments'] = Investment.objects.select_related(
            'investor', 'round'
        )[:5]

        return ctx


# === 투자자 ===
class InvestorListView(ManagerRequiredMixin, ListView):
    model = Investor
    template_name = 'investment/investor_list.html'
    context_object_name = 'investors'

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class InvestorCreateView(ManagerRequiredMixin, CreateView):
    model = Investor
    form_class = InvestorForm
    template_name = 'investment/investor_form.html'
    success_url = reverse_lazy('investment:investor_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class InvestorDetailView(ManagerRequiredMixin, DetailView):
    model = Investor
    template_name = 'investment/investor_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['investments'] = self.object.investments.select_related('round').all()
        ctx['equity_changes'] = self.object.equity_changes.all()
        ctx['distributions'] = self.object.distributions.all()
        ctx['total_distributed'] = self.object.total_distributed
        return ctx


class InvestorUpdateView(ManagerRequiredMixin, UpdateView):
    model = Investor
    form_class = InvestorForm
    template_name = 'investment/investor_form.html'
    success_url = reverse_lazy('investment:investor_list')


# === 투자 라운드 ===
class RoundListView(ManagerRequiredMixin, ListView):
    model = InvestmentRound
    template_name = 'investment/round_list.html'
    context_object_name = 'rounds'


class RoundCreateView(ManagerRequiredMixin, CreateView):
    model = InvestmentRound
    form_class = InvestmentRoundForm
    template_name = 'investment/round_form.html'
    success_url = reverse_lazy('investment:round_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class RoundDetailView(ManagerRequiredMixin, DetailView):
    model = InvestmentRound
    template_name = 'investment/round_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['investments'] = self.object.investments.select_related('investor').all()
        return ctx


class RoundUpdateView(ManagerRequiredMixin, UpdateView):
    model = InvestmentRound
    form_class = InvestmentRoundForm
    template_name = 'investment/round_form.html'
    success_url = reverse_lazy('investment:round_list')


# === 투자 내역 ===
class InvestmentCreateView(ManagerRequiredMixin, CreateView):
    model = Investment
    form_class = InvestmentForm
    template_name = 'investment/investment_form.html'
    success_url = reverse_lazy('investment:round_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


# === 지분 현황 ===
class EquityOverviewView(ManagerRequiredMixin, TemplateView):
    template_name = 'investment/equity_overview.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        investors = Investor.objects.all()
        equity_data = []
        total_share = 0
        for inv in investors:
            share = float(inv.current_share)
            equity_data.append({
                'name': inv.name,
                'share': share,
                'total_invested': int(inv.total_invested),
                'total_distributed': int(inv.total_distributed),
            })
            total_share += share

        founder_share = round(100 - total_share, 3)
        ctx['founder_share'] = founder_share
        ctx['equity_data'] = equity_data
        ctx['total_share'] = total_share

        chart_data = [{'name': '대표/창업자', 'share': founder_share}] if founder_share > 0 else []
        chart_data += [{'name': d['name'], 'share': d['share']} for d in equity_data if d['share'] > 0]
        ctx['chart_json'] = json.dumps(chart_data, ensure_ascii=False)

        ctx['equity_changes'] = EquityChange.objects.select_related('investor', 'related_round')[:20]
        return ctx


# === 배당/분배 ===
class DistributionListView(ManagerRequiredMixin, ListView):
    model = Distribution
    template_name = 'investment/distribution_list.html'
    context_object_name = 'distributions'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['total_paid'] = Distribution.objects.filter(
            status='PAID'
        ).aggregate(total=Sum('amount'))['total'] or 0
        ctx['total_scheduled'] = Distribution.objects.filter(
            status__in=['SCHEDULED', 'PENDING']
        ).aggregate(total=Sum('amount'))['total'] or 0
        return ctx


class DistributionCreateView(ManagerRequiredMixin, CreateView):
    model = Distribution
    form_class = DistributionForm
    template_name = 'investment/distribution_form.html'
    success_url = reverse_lazy('investment:distribution_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class DistributionUpdateView(ManagerRequiredMixin, UpdateView):
    model = Distribution
    form_class = DistributionForm
    template_name = 'investment/distribution_form.html'
    success_url = reverse_lazy('investment:distribution_list')
