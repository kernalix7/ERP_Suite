from django.urls import path

from . import views
from apps.core import excel_views

app_name = 'advertising'

urlpatterns = [
    path('', views.AdvertisingDashboardView.as_view(), name='dashboard'),
    # Platforms
    path('platforms/', views.AdPlatformListView.as_view(), name='platform_list'),
    path('platforms/create/', views.AdPlatformCreateView.as_view(), name='platform_create'),
    path('platforms/<int:pk>/edit/', views.AdPlatformUpdateView.as_view(), name='platform_update'),
    # Campaigns
    path('campaigns/', views.AdCampaignListView.as_view(), name='campaign_list'),
    path('campaigns/create/', views.AdCampaignCreateView.as_view(), name='campaign_create'),
    path('campaigns/<int:pk>/', views.AdCampaignDetailView.as_view(), name='campaign_detail'),
    path('campaigns/<int:pk>/edit/', views.AdCampaignUpdateView.as_view(), name='campaign_update'),
    # Creatives
    path('creatives/', views.AdCreativeListView.as_view(), name='creative_list'),
    path('creatives/create/', views.AdCreativeCreateView.as_view(), name='creative_create'),
    path('creatives/<int:pk>/edit/', views.AdCreativeUpdateView.as_view(), name='creative_update'),
    # Performance
    path('performance/', views.AdPerformanceListView.as_view(), name='performance_list'),
    # Budgets
    path('budgets/', views.AdBudgetListView.as_view(), name='budget_list'),
    path('budgets/create/', views.AdBudgetCreateView.as_view(), name='budget_create'),
    path('budgets/<int:pk>/edit/', views.AdBudgetUpdateView.as_view(), name='budget_update'),
    # Excel 내보내기
    path('campaigns/excel/', excel_views.AdCampaignExcelView.as_view(), name='campaign_excel'),
    path('performance/excel/', excel_views.AdPerformanceExcelView.as_view(), name='performance_excel'),
    path('budgets/excel/', excel_views.AdBudgetExcelView.as_view(), name='budget_excel'),
]
