from django.urls import path
from . import views
from apps.core import excel_views

app_name = 'plm'

urlpatterns = [
    # 제품버전
    path('versions/', views.ProductVersionListView.as_view(), name='version_list'),
    path('versions/excel/', excel_views.ProductVersionExcelView.as_view(), name='version_excel'),
    path('versions/create/', views.ProductVersionCreateView.as_view(), name='version_create'),
    path('versions/<int:pk>/', views.ProductVersionDetailView.as_view(), name='version_detail'),

    # BOM 리비전
    path('bom-revisions/', views.BOMRevisionListView.as_view(), name='bomrevision_list'),
    path('bom-revisions/<int:pk>/', views.BOMRevisionDetailView.as_view(), name='bomrevision_detail'),

    # ECN
    path('ecn/', views.ECNListView.as_view(), name='ecn_list'),
    path('ecn/excel/', excel_views.ECNExcelView.as_view(), name='ecn_excel'),
    path('ecn/create/', views.ECNCreateView.as_view(), name='ecn_create'),
    path('ecn/<int:pk>/', views.ECNDetailView.as_view(), name='ecn_detail'),
    path('ecn/<int:pk>/edit/', views.ECNUpdateView.as_view(), name='ecn_update'),

    # 도면
    path('drawings/', views.DrawingListView.as_view(), name='drawing_list'),
    path('drawings/upload/', views.DrawingCreateView.as_view(), name='drawing_create'),
]
