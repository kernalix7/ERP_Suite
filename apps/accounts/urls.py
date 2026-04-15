from django.urls import path

from . import views
from . import security_views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('password/change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
    path('password/expired/', security_views.PasswordExpiredView.as_view(), name='password_expired'),
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/create/', views.UserCreateView.as_view(), name='user_create'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_update'),
    path('users/<int:pk>/reset-password/', views.AdminPasswordResetView.as_view(), name='admin_password_reset'),
    path('permission-request/', views.PermissionRequestView.as_view(), name='permission_request'),
    # 권한 그룹 관리
    path('permission-groups/', views.PermissionGroupListView.as_view(), name='permission_group_list'),
    path('permission-groups/create/', views.PermissionGroupCreateView.as_view(), name='permission_group_create'),
    path('permission-groups/<int:pk>/edit/', views.PermissionGroupUpdateView.as_view(), name='permission_group_update'),
    path('permission-groups/<int:pk>/delete/', views.PermissionGroupDeleteView.as_view(), name='permission_group_delete'),
    # 사용자별 권한 관리
    path('users/<int:pk>/permissions/', views.UserPermissionView.as_view(), name='user_permissions'),
    # 2FA
    path('two-factor/setup/', security_views.TwoFactorSetupView.as_view(), name='two_factor_setup'),
    path('two-factor/verify/', security_views.TwoFactorVerifyView.as_view(), name='two_factor_verify'),
    path('two-factor/backup-codes/', security_views.TwoFactorBackupCodesView.as_view(), name='two_factor_backup_codes'),
    path('two-factor/disable/', security_views.TwoFactorDisableView.as_view(), name='two_factor_disable'),
    path('two-factor/regenerate-backup/', security_views.TwoFactorRegenerateBackupView.as_view(), name='two_factor_regenerate_backup'),
    # IP 화이트리스트
    path('ip-whitelist/', security_views.IPWhitelistListView.as_view(), name='ip_whitelist_list'),
    path('ip-whitelist/create/', security_views.IPWhitelistCreateView.as_view(), name='ip_whitelist_create'),
    path('ip-whitelist/<int:pk>/delete/', security_views.IPWhitelistDeleteView.as_view(), name='ip_whitelist_delete'),
    # 세션 관리
    path('sessions/', security_views.ActiveSessionsView.as_view(), name='active_sessions'),
    path('sessions/<int:pk>/terminate/', security_views.TerminateSessionView.as_view(), name='terminate_session'),
    path('sessions/terminate-all/', security_views.TerminateAllSessionsView.as_view(), name='terminate_all_sessions'),
]
