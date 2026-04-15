from django.urls import path

from . import views

app_name = 'subscription'

urlpatterns = [
    # Dashboard
    path('', views.SubscriptionDashboardView.as_view(), name='dashboard'),

    # Plans
    path('plans/', views.PlanListView.as_view(), name='plan_list'),
    path('plans/create/', views.PlanCreateView.as_view(), name='plan_create'),
    path('plans/<int:pk>/edit/', views.PlanUpdateView.as_view(), name='plan_update'),

    # Billing & Usage (before catch-all <str:subscription_number>)
    path('billing/', views.BillingRecordListView.as_view(), name='billing_list'),
    path('usage/', views.UsageRecordListView.as_view(), name='usage_list'),

    # Subscriptions
    path('list/', views.SubscriptionListView.as_view(), name='subscription_list'),
    path('create/', views.SubscriptionCreateView.as_view(), name='subscription_create'),
    path('<str:subscription_number>/', views.SubscriptionDetailView.as_view(), name='subscription_detail'),
    path('<str:subscription_number>/edit/', views.SubscriptionUpdateView.as_view(), name='subscription_update'),
    path('<str:subscription_number>/pause/', views.SubscriptionPauseView.as_view(), name='subscription_pause'),
    path('<str:subscription_number>/cancel/', views.SubscriptionCancelView.as_view(), name='subscription_cancel'),
    path('<str:subscription_number>/renew/', views.SubscriptionRenewView.as_view(), name='subscription_renew'),
    path('<str:subscription_number>/item/', views.SubscriptionItemCreateView.as_view(), name='subscription_item_create'),
]
