from django.urls import path
from . import views

app_name = 'asset'

urlpatterns = [
    path('', views.AssetListView.as_view(), name='asset_list'),
    path('create/', views.AssetCreateView.as_view(), name='asset_create'),
    path('depreciation-run/', views.AssetDepreciationRunView.as_view(), name='depreciation_run'),
    path('categories/', views.AssetCategoryListView.as_view(), name='category_list'),
    path('categories/create/', views.AssetCategoryCreateView.as_view(), name='category_create'),
    path('summary/', views.AssetSummaryView.as_view(), name='summary'),
    path('<str:slug>/', views.AssetDetailView.as_view(), name='asset_detail'),
    path('<str:slug>/edit/', views.AssetUpdateView.as_view(), name='asset_update'),
    path('<str:slug>/dispose/', views.AssetDisposalView.as_view(), name='asset_dispose'),
]
