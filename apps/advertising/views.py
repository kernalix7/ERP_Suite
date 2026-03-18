from django.db.models import Sum, Count, Q
from django.urls import reverse_lazy
from django.views.generic import (
    TemplateView, ListView, CreateView,
    UpdateView, DetailView,
)
from apps.core.mixins import ManagerRequiredMixin

from .models import (
    AdPlatform, AdCampaign, AdCreative,
    AdPerformance, AdBudget,
)
from .forms import (
    AdPlatformForm, AdCampaignForm, AdCreativeForm,
    AdBudgetForm,
)


class AdvertisingDashboardView(
    ManagerRequiredMixin, TemplateView
):
    template_name = 'advertising/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        active_campaigns = AdCampaign.objects.filter(
            status='ACTIVE', is_active=True
        )
        context['active_campaign_count'] = active_campaigns.count()

        perf_agg = AdPerformance.objects.filter(
            campaign__is_active=True
        ).aggregate(
            total_spent=Sum('cost'),
            total_revenue=Sum('revenue'),
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
        )
        context['total_spent'] = perf_agg['total_spent'] or 0
        context['total_revenue'] = perf_agg['total_revenue'] or 0
        context['total_conversions'] = (
            perf_agg['total_conversions'] or 0
        )

        total_cost = float(perf_agg['total_spent'] or 0)
        context['avg_roas'] = (
            round(float(perf_agg['total_revenue'] or 0)
                  / total_cost * 100, 1)
            if total_cost > 0 else 0
        )

        context['recent_campaigns'] = (
            AdCampaign.objects.select_related('platform')
            .filter(is_active=True)[:5]
        )

        context['platforms'] = (
            AdPlatform.objects.filter(is_active=True)
            .annotate(
                campaign_count=Count(
                    'campaigns',
                    filter=Q(campaigns__is_active=True)
                ),
                total_spent=Sum(
                    'campaigns__performances__cost',
                    filter=Q(
                        campaigns__is_active=True
                    )
                ),
            )
        )

        return context


class AdPlatformListView(
    ManagerRequiredMixin, ListView
):
    model = AdPlatform
    template_name = 'advertising/platform_list.html'
    context_object_name = 'platforms'

    def get_queryset(self):
        return AdPlatform.objects.filter(is_active=True)


class AdPlatformCreateView(
    ManagerRequiredMixin, CreateView
):
    model = AdPlatform
    form_class = AdPlatformForm
    template_name = 'advertising/platform_form.html'
    success_url = reverse_lazy('advertising:platform_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class AdPlatformUpdateView(
    ManagerRequiredMixin, UpdateView
):
    model = AdPlatform
    form_class = AdPlatformForm
    template_name = 'advertising/platform_form.html'
    success_url = reverse_lazy('advertising:platform_list')


class AdCampaignListView(
    ManagerRequiredMixin, ListView
):
    model = AdCampaign
    template_name = 'advertising/campaign_list.html'
    context_object_name = 'campaigns'
    paginate_by = 20

    def get_queryset(self):
        qs = AdCampaign.objects.select_related(
            'platform'
        ).filter(is_active=True)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        platform = self.request.GET.get('platform')
        if platform:
            qs = qs.filter(platform_id=platform)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['platforms'] = AdPlatform.objects.filter(
            is_active=True
        )
        context['status_choices'] = AdCampaign.STATUS_CHOICES
        context['current_status'] = (
            self.request.GET.get('status', '')
        )
        context['current_platform'] = (
            self.request.GET.get('platform', '')
        )
        return context


class AdCampaignCreateView(
    ManagerRequiredMixin, CreateView
):
    model = AdCampaign
    form_class = AdCampaignForm
    template_name = 'advertising/campaign_form.html'
    success_url = reverse_lazy('advertising:campaign_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class AdCampaignDetailView(
    ManagerRequiredMixin, DetailView
):
    model = AdCampaign
    template_name = 'advertising/campaign_detail.html'
    context_object_name = 'campaign'

    def get_queryset(self):
        return AdCampaign.objects.select_related('platform')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        campaign = self.object

        context['creatives'] = campaign.creatives.filter(
            is_active=True
        )

        perf_qs = campaign.performances.filter(is_active=True)
        context['performances'] = perf_qs.order_by('-date')[:30]

        perf_agg = perf_qs.aggregate(
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_cost=Sum('cost'),
            total_revenue=Sum('revenue'),
        )
        context['perf_summary'] = perf_agg

        total_imp = perf_agg['total_impressions'] or 0
        total_clicks = perf_agg['total_clicks'] or 0
        total_cost = float(perf_agg['total_cost'] or 0)
        total_revenue = float(perf_agg['total_revenue'] or 0)

        context['total_ctr'] = (
            round(total_clicks / total_imp * 100, 2)
            if total_imp > 0 else 0
        )
        context['total_roas'] = (
            round(total_revenue / total_cost * 100, 1)
            if total_cost > 0 else 0
        )

        return context


class AdCampaignUpdateView(
    ManagerRequiredMixin, UpdateView
):
    model = AdCampaign
    form_class = AdCampaignForm
    template_name = 'advertising/campaign_form.html'
    success_url = reverse_lazy('advertising:campaign_list')


class AdCreativeListView(
    ManagerRequiredMixin, ListView
):
    model = AdCreative
    template_name = 'advertising/creative_list.html'
    context_object_name = 'creatives'
    paginate_by = 20

    def get_queryset(self):
        return AdCreative.objects.select_related(
            'campaign', 'campaign__platform'
        ).filter(is_active=True)


class AdCreativeCreateView(
    ManagerRequiredMixin, CreateView
):
    model = AdCreative
    form_class = AdCreativeForm
    template_name = 'advertising/creative_form.html'
    success_url = reverse_lazy('advertising:creative_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class AdCreativeUpdateView(
    ManagerRequiredMixin, UpdateView
):
    model = AdCreative
    form_class = AdCreativeForm
    template_name = 'advertising/creative_form.html'
    success_url = reverse_lazy('advertising:creative_list')


class AdPerformanceListView(
    ManagerRequiredMixin, ListView
):
    model = AdPerformance
    template_name = 'advertising/performance_list.html'
    context_object_name = 'performances'
    paginate_by = 30

    def get_queryset(self):
        qs = AdPerformance.objects.select_related(
            'campaign', 'creative'
        ).filter(is_active=True)

        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        campaign = self.request.GET.get('campaign')

        if date_from:
            qs = qs.filter(date__gte=date_from)
        if date_to:
            qs = qs.filter(date__lte=date_to)
        if campaign:
            qs = qs.filter(campaign_id=campaign)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['campaigns'] = AdCampaign.objects.filter(
            is_active=True
        )

        qs = self.get_queryset()
        context['summary'] = qs.aggregate(
            total_impressions=Sum('impressions'),
            total_clicks=Sum('clicks'),
            total_conversions=Sum('conversions'),
            total_cost=Sum('cost'),
            total_revenue=Sum('revenue'),
        )
        return context


class AdBudgetListView(
    ManagerRequiredMixin, ListView
):
    model = AdBudget
    template_name = 'advertising/budget_list.html'
    context_object_name = 'budgets'
    paginate_by = 20

    def get_queryset(self):
        qs = AdBudget.objects.select_related(
            'platform'
        ).filter(is_active=True)

        year = self.request.GET.get('year')
        if year:
            qs = qs.filter(year=year)
        return qs


class AdBudgetCreateView(
    ManagerRequiredMixin, CreateView
):
    model = AdBudget
    form_class = AdBudgetForm
    template_name = 'advertising/budget_form.html'
    success_url = reverse_lazy('advertising:budget_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class AdBudgetUpdateView(
    ManagerRequiredMixin, UpdateView
):
    model = AdBudget
    form_class = AdBudgetForm
    template_name = 'advertising/budget_form.html'
    success_url = reverse_lazy('advertising:budget_list')
