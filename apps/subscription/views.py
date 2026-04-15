from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, Count, DecimalField, Sum, Value, When
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
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
    BillingRecordForm,
    SubscriptionForm,
    SubscriptionItemForm,
    SubscriptionPlanForm,
    UsageRecordForm,
)
from .models import (
    BillingRecord,
    Subscription,
    SubscriptionItem,
    SubscriptionPlan,
    UsageRecord,
)


# ── Plan views ──

class PlanListView(LoginRequiredMixin, ListView):
    model = SubscriptionPlan
    template_name = 'subscription/plan_list.html'
    context_object_name = 'plans'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class PlanCreateView(ManagerRequiredMixin, CreateView):
    model = SubscriptionPlan
    form_class = SubscriptionPlanForm
    template_name = 'subscription/plan_form.html'
    success_url = reverse_lazy('subscription:plan_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class PlanUpdateView(ManagerRequiredMixin, UpdateView):
    model = SubscriptionPlan
    form_class = SubscriptionPlanForm
    template_name = 'subscription/plan_form.html'
    success_url = reverse_lazy('subscription:plan_list')


# ── Subscription views ──

class SubscriptionListView(LoginRequiredMixin, ListView):
    model = Subscription
    template_name = 'subscription/subscription_list.html'
    context_object_name = 'subscriptions'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related('partner', 'plan')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


class SubscriptionCreateView(ManagerRequiredMixin, CreateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name = 'subscription/subscription_form.html'
    success_url = reverse_lazy('subscription:subscription_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)


class SubscriptionDetailView(LoginRequiredMixin, DetailView):
    model = Subscription
    template_name = 'subscription/subscription_detail.html'
    context_object_name = 'subscription'
    slug_field = 'subscription_number'
    slug_url_kwarg = 'subscription_number'

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related('partner', 'plan')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = self.object.items.filter(is_active=True).select_related('product')
        ctx['billing_records'] = self.object.billing_records.filter(is_active=True).order_by('-billing_date')[:10]
        ctx['usage_records'] = self.object.usage_records.filter(is_active=True).order_by('-recorded_date')[:10]
        ctx['item_form'] = SubscriptionItemForm()
        return ctx


class SubscriptionUpdateView(ManagerRequiredMixin, UpdateView):
    model = Subscription
    form_class = SubscriptionForm
    template_name = 'subscription/subscription_form.html'
    slug_field = 'subscription_number'
    slug_url_kwarg = 'subscription_number'

    def get_success_url(self):
        return reverse_lazy(
            'subscription:subscription_detail',
            kwargs={'subscription_number': self.object.subscription_number},
        )


class SubscriptionPauseView(ManagerRequiredMixin, View):
    def post(self, request, subscription_number):
        sub = get_object_or_404(
            Subscription, subscription_number=subscription_number, is_active=True,
        )
        if sub.status == Subscription.Status.ACTIVE:
            sub.status = Subscription.Status.PAUSED
            sub.save(update_fields=['status', 'updated_at'])
        return redirect('subscription:subscription_detail', subscription_number=sub.subscription_number)


class SubscriptionCancelView(ManagerRequiredMixin, View):
    def post(self, request, subscription_number):
        sub = get_object_or_404(
            Subscription, subscription_number=subscription_number, is_active=True,
        )
        if sub.status not in (Subscription.Status.CANCELLED, Subscription.Status.EXPIRED):
            sub.status = Subscription.Status.CANCELLED
            sub.cancel_reason = request.POST.get('cancel_reason', '')
            sub.save(update_fields=['status', 'cancel_reason', 'updated_at'])
        return redirect('subscription:subscription_detail', subscription_number=sub.subscription_number)


class SubscriptionRenewView(ManagerRequiredMixin, View):
    def post(self, request, subscription_number):
        sub = get_object_or_404(
            Subscription, subscription_number=subscription_number, is_active=True,
        )
        if sub.status in (Subscription.Status.PAUSED, Subscription.Status.EXPIRED):
            sub.status = Subscription.Status.ACTIVE
            sub.save(update_fields=['status', 'updated_at'])
        return redirect('subscription:subscription_detail', subscription_number=sub.subscription_number)


class SubscriptionItemCreateView(ManagerRequiredMixin, View):
    def post(self, request, subscription_number):
        sub = get_object_or_404(
            Subscription, subscription_number=subscription_number, is_active=True,
        )
        form = SubscriptionItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.subscription = sub
            item.created_by = request.user
            item.save()
        return redirect('subscription:subscription_detail', subscription_number=sub.subscription_number)


# ── Billing views ──

class BillingRecordListView(LoginRequiredMixin, ListView):
    model = BillingRecord
    template_name = 'subscription/billing_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().filter(is_active=True).select_related(
            'subscription__partner', 'subscription__plan',
        )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs


# ── Usage views ──

class UsageRecordListView(LoginRequiredMixin, ListView):
    model = UsageRecord
    template_name = 'subscription/usage_list.html'
    context_object_name = 'records'
    paginate_by = 20

    def get_queryset(self):
        return super().get_queryset().filter(is_active=True).select_related(
            'subscription__partner',
        )


# ── Dashboard ──

class SubscriptionDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'subscription/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        subs = Subscription.objects.filter(is_active=True)
        ctx['active_count'] = subs.filter(status=Subscription.Status.ACTIVE).count()
        ctx['trial_count'] = subs.filter(status=Subscription.Status.TRIAL).count()
        ctx['cancelled_count'] = subs.filter(status=Subscription.Status.CANCELLED).count()

        mrr_result = subs.filter(status=Subscription.Status.ACTIVE).aggregate(
            mrr=Sum(
                Case(
                    When(plan__billing_cycle='MONTHLY', then='plan__price'),
                    When(plan__billing_cycle='QUARTERLY', then='plan__price' / Value(3)),
                    When(plan__billing_cycle='YEARLY', then='plan__price' / Value(12)),
                    default=Value(0),
                    output_field=DecimalField(max_digits=15, decimal_places=0),
                ),
            ),
        )
        mrr = mrr_result['mrr'] or Decimal('0')
        ctx['mrr'] = int(mrr)
        ctx['arr'] = int(mrr * 12)

        ctx['recent_subscriptions'] = (
            subs.select_related('partner', 'plan').order_by('-created_at')[:10]
        )
        return ctx
