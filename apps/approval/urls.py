from django.urls import path
from . import views

app_name = 'approval'

urlpatterns = [
    path('', views.ApprovalListView.as_view(), name='approval_list'),
    path('create/', views.ApprovalCreateView.as_view(), name='approval_create'),
    path('templates/', views.ApprovalLineTemplateListView.as_view(), name='line_template_list'),
    path('templates/create/', views.ApprovalLineTemplateCreateView.as_view(), name='line_template_create'),
    path('delegations/', views.ApprovalDelegationListView.as_view(), name='delegation_list'),
    path('delegations/create/', views.ApprovalDelegationCreateView.as_view(), name='delegation_create'),
    path('delegations/<int:pk>/delete/', views.ApprovalDelegationDeleteView.as_view(), name='delegation_delete'),
    path('<str:slug>/', views.ApprovalDetailView.as_view(), name='approval_detail'),
    path('<str:slug>/edit/', views.ApprovalUpdateView.as_view(), name='approval_update'),
    path('<str:slug>/submit/', views.ApprovalSubmitView.as_view(), name='approval_submit'),
    path('<str:slug>/action/', views.ApprovalActionView.as_view(), name='approval_action'),
    path('<str:slug>/step/<int:step_pk>/action/', views.ApprovalStepActionView.as_view(), name='approval_step_action'),
]
