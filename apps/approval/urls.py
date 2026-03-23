from django.urls import path
from . import views

app_name = 'approval'

urlpatterns = [
    path('', views.ApprovalListView.as_view(), name='approval_list'),
    path('create/', views.ApprovalCreateView.as_view(), name='approval_create'),
    path('<int:pk>/edit/', views.ApprovalUpdateView.as_view(), name='approval_update'),
    path('<int:pk>/', views.ApprovalDetailView.as_view(), name='approval_detail'),
    path('<int:pk>/submit/', views.ApprovalSubmitView.as_view(), name='approval_submit'),
    path('<int:pk>/action/', views.ApprovalActionView.as_view(), name='approval_action'),
    path('<int:pk>/step/<int:step_pk>/action/', views.ApprovalStepActionView.as_view(), name='approval_step_action'),
]
