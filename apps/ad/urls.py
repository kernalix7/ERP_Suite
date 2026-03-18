from django.urls import path

from . import views

app_name = 'ad'

urlpatterns = [
    # 대시보드
    path('', views.ADDashboardView.as_view(), name='dashboard'),

    # 도메인 관리
    path('domains/', views.ADDomainListView.as_view(), name='domain_list'),
    path('domains/create/', views.ADDomainCreateView.as_view(), name='domain_create'),
    path('domains/<int:pk>/', views.ADDomainDetailView.as_view(), name='domain_detail'),
    path('domains/<int:pk>/edit/', views.ADDomainUpdateView.as_view(), name='domain_update'),
    path('domains/<int:pk>/test/', views.ADConnectionTestView.as_view(), name='connection_test'),

    # 그룹 관리
    path('groups/', views.ADGroupListView.as_view(), name='group_list'),
    path('groups/create/', views.ADGroupCreateView.as_view(), name='group_create'),
    path('groups/<int:pk>/edit/', views.ADGroupUpdateView.as_view(), name='group_update'),

    # 사용자 매핑
    path('mappings/', views.ADUserMappingListView.as_view(), name='usermapping_list'),
    path('mappings/create/', views.ADUserMappingCreateView.as_view(), name='usermapping_create'),

    # 동기화
    path('sync/', views.ADManualSyncView.as_view(), name='manual_sync'),
    path('sync/logs/', views.ADSyncLogListView.as_view(), name='synclog_list'),

    # 정책
    path('policies/', views.ADPolicyListView.as_view(), name='policy_list'),
    path('policies/create/', views.ADPolicyCreateView.as_view(), name='policy_create'),
    path('policies/<int:pk>/edit/', views.ADPolicyUpdateView.as_view(), name='policy_update'),
]
