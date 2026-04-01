from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.CustomLogoutView.as_view(), name='logout'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('password/change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
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
]
