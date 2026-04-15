from django.urls import path

from . import views

app_name = 'rpa'

urlpatterns = [
    # Dashboard
    path('', views.AutomationDashboardView.as_view(), name='dashboard'),
    # Rules
    path('rules/', views.RuleListView.as_view(), name='rule_list'),
    path('rules/create/', views.RuleCreateView.as_view(), name='rule_create'),
    path('rules/<int:pk>/', views.RuleDetailView.as_view(), name='rule_detail'),
    path('rules/<int:pk>/edit/', views.RuleUpdateView.as_view(), name='rule_update'),
    path('rules/<int:pk>/delete/', views.RuleDeleteView.as_view(), name='rule_delete'),
    path('rules/<int:pk>/toggle/', views.RuleToggleView.as_view(), name='rule_toggle'),
    path('rules/<int:pk>/test/', views.RuleTestView.as_view(), name='rule_test'),
    # Actions (inline)
    path('rules/<int:rule_pk>/actions/create/', views.ActionCreateView.as_view(), name='action_create'),
    path('rules/<int:rule_pk>/actions/<int:pk>/delete/', views.ActionDeleteView.as_view(), name='action_delete'),
    # Conditions (inline)
    path('rules/<int:rule_pk>/conditions/create/', views.ConditionCreateView.as_view(), name='condition_create'),
    path('rules/<int:rule_pk>/conditions/<int:pk>/delete/', views.ConditionDeleteView.as_view(), name='condition_delete'),
    # Logs
    path('logs/', views.LogListView.as_view(), name='log_list'),
    path('logs/<int:pk>/', views.LogDetailView.as_view(), name='log_detail'),
    # Schedules
    path('schedules/', views.ScheduleListView.as_view(), name='schedule_list'),
    path('schedules/create/', views.ScheduleCreateView.as_view(), name='schedule_create'),
    path('schedules/<int:pk>/', views.ScheduleUpdateView.as_view(), name='schedule_update'),
    path('schedules/<int:pk>/delete/', views.ScheduleDeleteView.as_view(), name='schedule_delete'),
]
