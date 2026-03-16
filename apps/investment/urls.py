from django.urls import path

from . import views

app_name = 'investment'

urlpatterns = [
    path('', views.InvestmentDashboardView.as_view(), name='dashboard'),
    path('investors/', views.InvestorListView.as_view(), name='investor_list'),
    path('investors/create/', views.InvestorCreateView.as_view(), name='investor_create'),
    path('investors/<int:pk>/', views.InvestorDetailView.as_view(), name='investor_detail'),
    path('investors/<int:pk>/edit/', views.InvestorUpdateView.as_view(), name='investor_update'),
    path('rounds/', views.RoundListView.as_view(), name='round_list'),
    path('rounds/create/', views.RoundCreateView.as_view(), name='round_create'),
    path('rounds/<int:pk>/', views.RoundDetailView.as_view(), name='round_detail'),
    path('rounds/<int:pk>/edit/', views.RoundUpdateView.as_view(), name='round_update'),
    path('investments/create/', views.InvestmentCreateView.as_view(), name='investment_create'),
    path('equity/', views.EquityOverviewView.as_view(), name='equity_overview'),
    path('distributions/', views.DistributionListView.as_view(), name='distribution_list'),
    path('distributions/create/', views.DistributionCreateView.as_view(), name='distribution_create'),
    path('distributions/<int:pk>/edit/', views.DistributionUpdateView.as_view(), name='distribution_update'),
]
